"""Tests for processing engine."""

from unittest.mock import Mock

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
