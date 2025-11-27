"""Processing engine for batch LLM operations."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from enum import Enum
from typing import Any

from agents.core.llm_client import LLMClient
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
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.mode = mode
        self.batch_size = batch_size
        self.post_process = post_process
        self.merge_results = merge_results
        self.include_raw_result = include_raw_result
        self.parse_error_retries = parse_error_retries
        self.post_processor = PostProcessor() if post_process else None

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
            Processed result dict.
        """
        last_result: dict[str, Any] | None = None
        attempts = 1 + self.parse_error_retries  # 1 initial + retries

        for attempt in range(attempts):
            try:
                prompt = self.prompt_template.render(unit)
                result = self.llm_client.complete(prompt)
                processed_result: dict[str, Any] = {**unit, "result": result}

                # Apply post-processing if enabled
                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                # Check if parse error occurred
                if PARSE_ERROR_KEY not in processed_result:
                    return processed_result

                # Parse error - save result and retry
                last_result = processed_result
                if attempt < attempts - 1:
                    continue  # Retry

            except Exception as e:
                return {**unit, "error": str(e)}

        # All retries exhausted, return last result with retry info
        if last_result:
            last_result["_retries_exhausted"] = True
            last_result["_attempts"] = attempts
            return last_result

        return {**unit, "error": "Unknown processing error"}

    def _process_sequential(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units sequentially."""
        for unit in units:
            yield self._process_single_unit(unit)

    def _process_async(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units asynchronously using batch processing with incremental results."""
        # Create new event loop for async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Use async generator to yield results as they complete
            async_gen = self._process_async_incremental(units)
            while True:
                try:
                    result = loop.run_until_complete(async_gen.__anext__())
                    yield result
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _process_single_unit_async(self, unit: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single unit asynchronously with retry logic for parse errors.

        Args:
            unit: Data unit to process.

        Returns:
            Processed result dict.
        """
        last_result: dict[str, Any] | None = None
        attempts = 1 + self.parse_error_retries  # 1 initial + retries

        for attempt in range(attempts):
            try:
                prompt = self.prompt_template.render(unit)
                result = await self.llm_client.complete_async(prompt)
                processed_result: dict[str, Any] = {**unit, "result": result}

                # Apply post-processing if enabled
                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                # Check if parse error occurred
                if PARSE_ERROR_KEY not in processed_result:
                    return processed_result

                # Parse error - save result and retry
                last_result = processed_result
                if attempt < attempts - 1:
                    continue  # Retry

            except Exception as e:
                return {**unit, "error": str(e)}

        # All retries exhausted, return last result with retry info
        if last_result:
            last_result["_retries_exhausted"] = True
            last_result["_attempts"] = attempts
            return last_result

        return {**unit, "error": "Unknown processing error"}

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
                return await self._process_single_unit_async(unit)

        # Create all tasks
        tasks = [asyncio.create_task(process_unit(unit)) for unit in units]

        # Yield results as they complete
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result
