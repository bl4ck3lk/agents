"""Processing engine for batch LLM operations."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from enum import Enum
from typing import Any

from agents.core.circuit_breaker import CircuitBreaker, CircuitBreakerTripped
from agents.core.llm_client import FatalLLMError, LLMClient, LLMResponse
from agents.core.postprocessor import PostProcessor
from agents.core.prompt import PromptTemplate

# Key used to indicate parse failure in results
PARSE_ERROR_KEY = "parse_error"


class ProcessingMode(str, Enum):
    """Processing mode for engine."""

    SEQUENTIAL = "sequential"
    ASYNC = "async"


class ProcessingEngine:
    """Engine for processing data units with LLM."""

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_template: PromptTemplate,
        mode: ProcessingMode = ProcessingMode.SEQUENTIAL,
        batch_size: int = 10,
        post_process: bool = True,
        merge_results: bool = True,
        include_raw_result: bool = False,
        parse_error_retries: int = 2,
        circuit_breaker_threshold: int = 5,
    ) -> None:
        """
        Initialize processing engine.

        Args:
            llm_client: LLM client for API calls.
            prompt_template: Template for rendering prompts.
            mode: Processing mode (sequential or async).
            batch_size: Batch size for async mode.
            post_process: Whether to post-process LLM output to extract JSON.
            merge_results: Whether to merge parsed JSON fields into root.
            include_raw_result: Whether to include raw LLM output in result.
            parse_error_retries: Number of retries when JSON parsing fails.
            circuit_breaker_threshold: Number of consecutive fatal errors before tripping. 0 to disable.
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.mode = mode
        self.batch_size = batch_size
        self.post_process = post_process
        self.merge_results = merge_results
        self.include_raw_result = include_raw_result
        self.parse_error_retries = parse_error_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.post_processor = PostProcessor() if post_process else None

        # Initialize circuit breaker (disabled if threshold is 0)
        self._circuit_breaker: CircuitBreaker | None = None
        if circuit_breaker_threshold > 0:
            self._circuit_breaker = CircuitBreaker(threshold=circuit_breaker_threshold)

    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker has tripped and raise if so."""
        if self._circuit_breaker and self._circuit_breaker.is_tripped():
            raise CircuitBreakerTripped(self._circuit_breaker.get_status())

    def _record_fatal_error(self, error: Exception, unit: dict[str, Any]) -> None:
        """Record a fatal error in the circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.record_failure(error, unit)

    def _record_success(self) -> None:
        """Record a success, resetting the circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.record_success()

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.reset()

    def process(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """
        Process data units with LLM.

        Args:
            units: List of data units to process.

        Yields:
            Processed results with original data + result field.
        """
        if self.mode == ProcessingMode.SEQUENTIAL:
            yield from self._process_sequential(units)
        else:
            yield from self._process_async(units)

    def _process_single_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single unit with retry logic for parse errors.

        Args:
            unit: Data unit to process.

        Returns:
            Processed result dict with _usage field containing token counts.
        """
        last_result: dict[str, Any] | None = None
        attempts = 1 + self.parse_error_retries  # 1 initial + retries
        total_usage = {"input": 0, "output": 0}

        for attempt in range(attempts):
            try:
                prompt = self.prompt_template.render(unit)
                llm_response: LLMResponse = self.llm_client.complete_with_usage(prompt)
                result = llm_response.content

                # Accumulate token usage across retries
                if llm_response.usage:
                    total_usage["input"] += llm_response.usage.prompt_tokens
                    total_usage["output"] += llm_response.usage.completion_tokens

                processed_result: dict[str, Any] = {**unit, "result": result}

                # Apply post-processing if enabled
                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                # Add usage to result
                processed_result["_usage"] = total_usage

                # Check if parse error occurred
                if PARSE_ERROR_KEY not in processed_result:
                    return processed_result

                # Parse error - save result and retry
                last_result = processed_result
                if attempt < attempts - 1:
                    continue  # Retry

            except FatalLLMError:
                raise  # Re-raise for circuit breaker handling
            except Exception as e:
                error_result = {**unit, "_error": str(e)}
                if total_usage["input"] > 0 or total_usage["output"] > 0:
                    error_result["_usage"] = total_usage
                return error_result

        # All retries exhausted, return last result with retry info
        if last_result:
            last_result["_retries_exhausted"] = True
            last_result["_attempts"] = attempts
            return last_result

        return {**unit, "_error": "Unknown processing error"}

    def _process_sequential(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units sequentially."""
        for unit in units:
            try:
                result = self._process_single_unit(unit)
                if "_error" not in result:
                    self._record_success()
                yield result
            except FatalLLMError as e:
                self._record_fatal_error(e.original_error, unit)
                yield {**unit, "_error": str(e)}
                self._check_circuit_breaker()

    def _process_async(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units asynchronously using batch processing with incremental results.

        When called from a synchronous context (e.g., CLI), creates a new event loop.
        For use within an existing event loop (e.g., FastAPI), use process_async() instead.
        """
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # We're inside an existing event loop - can't use run_until_complete.
            # Callers in async context should use process_async() instead.
            raise RuntimeError(
                "Cannot use sync _process_async() inside an existing event loop. "
                "Use process_async() for async contexts."
            )

        # Create new event loop for sync-to-async bridging (CLI usage)
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            async_gen = self._process_async_incremental(units)
            while True:
                try:
                    result = new_loop.run_until_complete(async_gen.__anext__())
                    yield result
                except StopAsyncIteration:
                    break
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)

    async def process_async(self, units: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
        """Process data units asynchronously, compatible with existing event loops.

        Use this method when running within an async context (e.g., FastAPI).

        Args:
            units: List of data units to process.

        Yields:
            Processed results as they complete.
        """
        if self.mode == ProcessingMode.SEQUENTIAL:
            for unit in units:
                try:
                    result = await self._process_single_unit_async(unit)
                    if "_error" not in result:
                        self._record_success()
                    yield result
                except FatalLLMError as e:
                    self._record_fatal_error(e.original_error, unit)
                    yield {**unit, "_error": str(e)}
                    self._check_circuit_breaker()
        else:
            async for result in self._process_async_incremental(units):
                yield result

    async def _process_single_unit_async(self, unit: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single unit asynchronously with retry logic for parse errors.

        Args:
            unit: Data unit to process.

        Returns:
            Processed result dict with _usage field containing token counts.
        """
        last_result: dict[str, Any] | None = None
        attempts = 1 + self.parse_error_retries  # 1 initial + retries
        total_usage = {"input": 0, "output": 0}

        for attempt in range(attempts):
            try:
                prompt = self.prompt_template.render(unit)
                llm_response: LLMResponse = await self.llm_client.complete_with_usage_async(prompt)
                result = llm_response.content

                # Accumulate token usage across retries
                if llm_response.usage:
                    total_usage["input"] += llm_response.usage.prompt_tokens
                    total_usage["output"] += llm_response.usage.completion_tokens

                processed_result: dict[str, Any] = {**unit, "result": result}

                # Apply post-processing if enabled
                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                # Add usage to result
                processed_result["_usage"] = total_usage

                # Check if parse error occurred
                if PARSE_ERROR_KEY not in processed_result:
                    return processed_result

                # Parse error - save result and retry
                last_result = processed_result
                if attempt < attempts - 1:
                    continue  # Retry

            except FatalLLMError:
                raise  # Re-raise for circuit breaker handling
            except Exception as e:
                error_result = {**unit, "_error": str(e)}
                if total_usage["input"] > 0 or total_usage["output"] > 0:
                    error_result["_usage"] = total_usage
                return error_result

        # All retries exhausted, return last result with retry info
        if last_result:
            last_result["_retries_exhausted"] = True
            last_result["_attempts"] = attempts
            return last_result

        return {**unit, "_error": "Unknown processing error"}

    async def _process_async_incremental(
        self, units: list[dict[str, Any]]
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Process units asynchronously and yield results as they complete.

        Args:
            units: List of data units to process.

        Yields:
            Processed results as they complete.
        """
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.batch_size)

        async def process_unit(unit: dict[str, Any]) -> dict[str, Any]:
            """Process a single unit with semaphore control."""
            async with semaphore:
                try:
                    result = await self._process_single_unit_async(unit)
                    if "_error" not in result:
                        self._record_success()
                    return result
                except FatalLLMError as e:
                    self._record_fatal_error(e.original_error, unit)
                    return {**unit, "_error": str(e)}

        # Create all tasks
        tasks = [asyncio.create_task(process_unit(unit)) for unit in units]

        try:
            # Yield results as they complete
            for coro in asyncio.as_completed(tasks):
                result = await coro
                yield result
                # Check circuit breaker after each result
                self._check_circuit_breaker()
        except CircuitBreakerTripped:
            # Cancel all pending tasks to stop further API calls
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Wait for cancelled tasks to finish (suppress CancelledError)
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
