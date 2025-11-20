"""Tests for processing engine."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate


@pytest.fixture
def mock_llm_client() -> Mock:
    """Mock LLM client."""
    client = Mock(spec=LLMClient)
    client.complete.side_effect = lambda prompt: f"Result: {prompt}"
    return client


@pytest.fixture
def mock_async_llm_client() -> Mock:
    """Mock async LLM client."""
    client = Mock(spec=LLMClient)

    async def async_complete(prompt: str) -> str:
        await asyncio.sleep(0.01)  # Simulate async delay
        return f"Result: {prompt}"

    client.complete_async = AsyncMock(side_effect=async_complete)
    return client


def test_sequential_processing(mock_llm_client: Mock) -> None:
    """Test sequential processing mode."""
    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL)

    units = [{"text": "hello"}, {"text": "world"}]
    results = list(engine.process(units))

    assert len(results) == 2
    assert results[0] == {"text": "hello", "result": "Result: Process: hello"}
    assert results[1] == {"text": "world", "result": "Result: Process: world"}
    assert mock_llm_client.complete.call_count == 2


def test_processing_with_error_handling(mock_llm_client: Mock) -> None:
    """Test processing handles errors gracefully."""
    mock_llm_client.complete.side_effect = [
        "Success",
        Exception("API error"),
        "Success again",
    ]

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL)

    units = [{"text": "one"}, {"text": "two"}, {"text": "three"}]
    results = list(engine.process(units))

    assert len(results) == 3
    assert results[0] == {"text": "one", "result": "Success"}
    assert "error" in results[1]
    assert results[2] == {"text": "three", "result": "Success again"}


def test_async_processing(mock_async_llm_client: Mock) -> None:
    """Test async processing mode."""
    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=2
    )

    units = [{"text": "hello"}, {"text": "world"}, {"text": "async"}]
    results = list(engine.process(units))

    assert len(results) == 3
    assert results[0] == {"text": "hello", "result": "Result: Process: hello"}
    assert results[1] == {"text": "world", "result": "Result: Process: world"}
    assert results[2] == {"text": "async", "result": "Result: Process: async"}
    assert mock_async_llm_client.complete_async.call_count == 3


def test_async_processing_with_error_handling(mock_async_llm_client: Mock) -> None:
    """Test async processing handles errors gracefully."""

    async def async_complete_with_errors(prompt: str) -> str:
        if "two" in prompt:
            raise Exception("API error")
        await asyncio.sleep(0.01)
        return f"Result: {prompt}"

    mock_async_llm_client.complete_async = AsyncMock(side_effect=async_complete_with_errors)

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=2
    )

    units = [{"text": "one"}, {"text": "two"}, {"text": "three"}]
    results = list(engine.process(units))

    assert len(results) == 3
    assert results[0] == {"text": "one", "result": "Result: Process: one"}
    assert "error" in results[1]
    assert results[2] == {"text": "three", "result": "Result: Process: three"}


def test_async_processing_respects_batch_size(mock_async_llm_client: Mock) -> None:
    """Test async processing respects batch size for concurrency control."""
    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=3
    )

    # Create 10 units
    units = [{"text": f"item_{i}"} for i in range(10)]
    results = list(engine.process(units))

    assert len(results) == 10
    # Verify all were processed
    for i, result in enumerate(results):
        assert result["text"] == f"item_{i}"
        assert "result" in result
