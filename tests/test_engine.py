"""Tests for processing engine."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from agents.core.circuit_breaker import CircuitBreakerTripped
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import FatalLLMError, LLMClient
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
    engine = ProcessingEngine(
        mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL, post_process=False
    )

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
    engine = ProcessingEngine(
        mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL, post_process=False
    )

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
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=2, post_process=False
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
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=2, post_process=False
    )

    units = [{"text": "one"}, {"text": "two"}, {"text": "three"}]
    results = list(engine.process(units))

    assert len(results) == 3
    # Async results may come back in any order, so check by text field
    results_by_text = {r["text"]: r for r in results}
    assert results_by_text["one"] == {"text": "one", "result": "Result: Process: one"}
    assert "error" in results_by_text["two"]
    assert results_by_text["three"] == {"text": "three", "result": "Result: Process: three"}


def test_async_processing_respects_batch_size(mock_async_llm_client: Mock) -> None:
    """Test async processing respects batch size for concurrency control."""
    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=3, post_process=False
    )

    # Create 10 units
    units = [{"text": f"item_{i}"} for i in range(10)]
    results = list(engine.process(units))

    assert len(results) == 10
    # Verify all were processed
    for i, result in enumerate(results):
        assert result["text"] == f"item_{i}"
        assert "result" in result


def test_engine_tracks_fatal_errors_in_circuit_breaker(mock_llm_client: Mock) -> None:
    """Test engine counts fatal errors toward circuit breaker."""
    mock_llm_client.complete.side_effect = FatalLLMError(Exception("Permission denied"))

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client,
        template,
        mode=ProcessingMode.SEQUENTIAL,
        circuit_breaker_threshold=3,
        post_process=False,
    )

    units = [{"text": f"item{i}"} for i in range(5)]
    results = []

    with pytest.raises(CircuitBreakerTripped) as exc_info:
        for result in engine.process(units):
            results.append(result)

    # Should have processed 3 items before tripping
    assert len(results) == 3
    assert exc_info.value.status["consecutive_failures"] == 3


def test_engine_resets_circuit_breaker_on_success(mock_llm_client: Mock) -> None:
    """Test circuit breaker resets after successful processing."""
    mock_llm_client.complete.side_effect = [
        FatalLLMError(Exception("err1")),
        FatalLLMError(Exception("err2")),
        "Success",
        "Success",
    ]

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client,
        template,
        mode=ProcessingMode.SEQUENTIAL,
        circuit_breaker_threshold=3,
        post_process=False,
    )

    units = [{"text": f"item{i}"} for i in range(4)]
    results = list(engine.process(units))

    # All 4 should process (breaker never trips because success resets counter)
    assert len(results) == 4
    assert "error" in results[0]
    assert "error" in results[1]
    assert results[2]["result"] == "Success"
    assert results[3]["result"] == "Success"


def test_engine_circuit_breaker_disabled_when_zero(mock_llm_client: Mock) -> None:
    """Test circuit breaker is disabled when threshold is 0."""
    mock_llm_client.complete.side_effect = FatalLLMError(Exception("err"))

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client,
        template,
        mode=ProcessingMode.SEQUENTIAL,
        circuit_breaker_threshold=0,  # Disabled
        post_process=False,
    )

    units = [{"text": f"item{i}"} for i in range(10)]
    results = list(engine.process(units))

    # All 10 should process (no circuit breaker)
    assert len(results) == 10
    assert all("error" in r for r in results)
