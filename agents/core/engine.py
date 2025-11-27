"""Processing engine for batch LLM operations."""

import asyncio
from collections.abc import Iterator
from enum import Enum
from typing import Any

from agents.core.llm_client import LLMClient
from agents.core.postprocessor import PostProcessor
from agents.core.prompt import PromptTemplate


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
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.mode = mode
        self.batch_size = batch_size
        self.post_process = post_process
        self.merge_results = merge_results
        self.include_raw_result = include_raw_result
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

    def _process_sequential(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units sequentially."""
        for unit in units:
            try:
                prompt = self.prompt_template.render(unit)
                result = self.llm_client.complete(prompt)
                processed_result = {**unit, "result": result}

                # Apply post-processing if enabled
                if self.post_processor:
                    processed_result = self.post_processor.process_result(
                        processed_result,
                        merge=self.merge_results,
                        include_raw=self.include_raw_result,
                    )

                yield processed_result
            except Exception as e:
                yield {**unit, "error": str(e)}

    def _process_async(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units asynchronously using batch processing."""
        # Create new event loop for async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self._process_async_batch(units))
            yield from results
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _process_async_batch(self, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Process units asynchronously with concurrency control.

        Args:
            units: List of data units to process.

        Returns:
            List of processed results.
        """
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.batch_size)

        async def process_unit(unit: dict[str, Any]) -> dict[str, Any]:
            """Process a single unit with semaphore control."""
            async with semaphore:
                try:
                    prompt = self.prompt_template.render(unit)
                    result = await self.llm_client.complete_async(prompt)
                    processed_result = {**unit, "result": result}

                    # Apply post-processing if enabled
                    if self.post_processor:
                        processed_result = self.post_processor.process_result(
                            processed_result,
                            merge=self.merge_results,
                            include_raw=self.include_raw_result,
                        )

                    return processed_result
                except Exception as e:
                    return {**unit, "error": str(e)}

        # Process all units concurrently with semaphore limiting concurrency
        tasks = [process_unit(unit) for unit in units]
        results = await asyncio.gather(*tasks)

        return results
