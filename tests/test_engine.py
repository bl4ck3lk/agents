"""Tests for processing engine."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from agents.core.circuit_breaker import CircuitBreakerTripped
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import FatalLLMError, LLMClient, LLMResponse, UsageMetadata
from agents.core.prompt import PromptTemplate


def make_llm_response(prompt: str) -> LLMResponse:
    """Create an LLMResponse with mock usage data."""
    return LLMResponse(
        content=f"Result: {prompt}",
        usage=UsageMetadata(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )


@pytest.fixture
def mock_llm_client() -> Mock:
    """Mock LLM client."""
    client = Mock(spec=LLMClient)
    client.complete_with_usage.side_effect = make_llm_response
    return client


@pytest.fixture
def mock_async_llm_client() -> Mock:
    """Mock async LLM client."""
    client = Mock(spec=LLMClient)

    async def async_complete(prompt: str) -> LLMResponse:
        await asyncio.sleep(0.01)  # Simulate async delay
        return make_llm_response(prompt)

    client.complete_with_usage_async = AsyncMock(side_effect=async_complete)
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
    assert results[0]["text"] == "hello"
    assert results[0]["result"] == "Result: Process: hello"
    assert "_usage" in results[0]  # Usage tracking
    assert results[1]["text"] == "world"
    assert results[1]["result"] == "Result: Process: world"
    assert mock_llm_client.complete_with_usage.call_count == 2


def test_processing_with_error_handling(mock_llm_client: Mock) -> None:
    """Test processing handles errors gracefully."""
    mock_llm_client.complete_with_usage.side_effect = [
        LLMResponse(content="Success", usage=UsageMetadata(10, 20, 30)),
        Exception("API error"),
        LLMResponse(content="Success again", usage=UsageMetadata(10, 20, 30)),
    ]

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL, post_process=False
    )

    units = [{"text": "one"}, {"text": "two"}, {"text": "three"}]
    results = list(engine.process(units))

    assert len(results) == 3
    assert results[0]["text"] == "one"
    assert results[0]["result"] == "Success"
    assert "_error" in results[1]
    assert results[2]["text"] == "three"
    assert results[2]["result"] == "Success again"


def test_async_processing(mock_async_llm_client: Mock) -> None:
    """Test async processing mode."""
    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=2, post_process=False
    )

    units = [{"text": "hello"}, {"text": "world"}, {"text": "async"}]
    results = list(engine.process(units))

    assert len(results) == 3
    assert results[0]["text"] == "hello"
    assert results[0]["result"] == "Result: Process: hello"
    assert "_usage" in results[0]
    assert results[1]["text"] == "world"
    assert results[1]["result"] == "Result: Process: world"
    assert results[2]["text"] == "async"
    assert results[2]["result"] == "Result: Process: async"
    assert mock_async_llm_client.complete_with_usage_async.call_count == 3


def test_async_processing_with_error_handling(mock_async_llm_client: Mock) -> None:
    """Test async processing handles errors gracefully."""

    async def async_complete_with_errors(prompt: str) -> LLMResponse:
        if "two" in prompt:
            raise Exception("API error")
        await asyncio.sleep(0.01)
        return make_llm_response(prompt)

    mock_async_llm_client.complete_with_usage_async = AsyncMock(side_effect=async_complete_with_errors)

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        mock_async_llm_client, template, mode=ProcessingMode.ASYNC, batch_size=2, post_process=False
    )

    units = [{"text": "one"}, {"text": "two"}, {"text": "three"}]
    results = list(engine.process(units))

    assert len(results) == 3
    # Async results may come back in any order, so check by text field
    results_by_text = {r["text"]: r for r in results}
    assert results_by_text["one"]["text"] == "one"
    assert results_by_text["one"]["result"] == "Result: Process: one"
    assert "_error" in results_by_text["two"]
    assert results_by_text["three"]["text"] == "three"
    assert results_by_text["three"]["result"] == "Result: Process: three"


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
    mock_llm_client.complete_with_usage.side_effect = FatalLLMError(Exception("Permission denied"))

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
    mock_llm_client.complete_with_usage.side_effect = [
        FatalLLMError(Exception("err1")),
        FatalLLMError(Exception("err2")),
        LLMResponse(content="Success", usage=UsageMetadata(10, 20, 30)),
        LLMResponse(content="Success", usage=UsageMetadata(10, 20, 30)),
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
    assert "_error" in results[0]
    assert "_error" in results[1]
    assert results[2]["result"] == "Success"
    assert results[3]["result"] == "Success"


def test_engine_circuit_breaker_disabled_when_zero(mock_llm_client: Mock) -> None:
    """Test circuit breaker is disabled when threshold is 0."""
    mock_llm_client.complete_with_usage.side_effect = FatalLLMError(Exception("err"))

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
    assert all("_error" in r for r in results)


def test_async_circuit_breaker_cancels_pending_tasks() -> None:
    """Test async processing cancels pending tasks when circuit breaker trips."""
    call_count = 0

    async def failing_complete(prompt: str) -> LLMResponse:
        nonlocal call_count
        call_count += 1
        # Add delay to simulate real API call - gives time for tasks to queue
        await asyncio.sleep(0.05)
        raise FatalLLMError(Exception("API error"))

    client = Mock(spec=LLMClient)
    client.complete_with_usage_async = AsyncMock(side_effect=failing_complete)

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(
        client,
        template,
        mode=ProcessingMode.ASYNC,
        batch_size=5,  # Allow 5 concurrent
        circuit_breaker_threshold=3,  # Trip after 3 failures
        post_process=False,
    )

    # Create 20 units - many more than threshold
    units = [{"text": f"item{i}"} for i in range(20)]
    results = []

    with pytest.raises(CircuitBreakerTripped):
        for result in engine.process(units):
            results.append(result)

    # With concurrent processing, multiple failures may be recorded before we check.
    # We should get at least 1 result before tripping.
    assert len(results) >= 1

    # Critical: should NOT have made all 20 API calls
    # The first batch of 5 starts, but pending tasks (waiting on semaphore)
    # should be cancelled when breaker trips.
    # Allow for the first batch plus some that may have started, but not all 20.
    assert call_count <= 10, f"Expected <=10 API calls but made {call_count}"
    # Verify cancellation worked - should be way less than 20
    assert call_count < 20, f"Cancellation failed: made all {call_count} API calls"
