"""Processing engine for batch LLM operations."""

from enum import Enum
from typing import Any, Iterator

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
            raise NotImplementedError("Async mode not yet implemented")

    def _process_sequential(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units sequentially."""
        for unit in units:
            try:
                prompt = self.prompt_template.render(unit)
                result = self.llm_client.complete(prompt)
                yield {**unit, "result": result}
            except Exception as e:
                yield {**unit, "error": str(e)}
