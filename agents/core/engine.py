"""Processing engine for batch LLM operations."""

import asyncio
from collections.abc import Iterator
from enum import Enum
from typing import Any

from agents.core.llm_client import LLMClient
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
    ) -> None:
        """
        Initialize processing engine.

        Args:
            llm_client: LLM client for API calls.
            prompt_template: Template for rendering prompts.
            mode: Processing mode (sequential or async).
            batch_size: Batch size for async mode.
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.mode = mode
        self.batch_size = batch_size

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
                yield {**unit, "result": result}
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
                    return {**unit, "result": result}
                except Exception as e:
                    return {**unit, "error": str(e)}

        # Process all units concurrently with semaphore limiting concurrency
        tasks = [process_unit(unit) for unit in units]
        results = await asyncio.gather(*tasks)

        return results
