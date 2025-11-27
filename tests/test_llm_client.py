"""Tests for LLM client."""

from unittest.mock import Mock, patch

import pytest
from openai import AuthenticationError, OpenAI, PermissionDeniedError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from agents.core.llm_client import FATAL_ERRORS, RETRYABLE_ERRORS, FatalLLMError, LLMClient


@pytest.fixture
def mock_openai_client() -> Mock:
    """Mock OpenAI client."""
    client = Mock(spec=OpenAI)
    return client


def test_llm_client_initialization() -> None:
    """Test LLM client initializes correctly."""
    client = LLMClient(api_key="test-key", model="gpt-4o-mini")
    assert client.model == "gpt-4o-mini"


def test_llm_client_completion(mock_openai_client: Mock) -> None:
    """Test LLM client generates completions."""
    # Mock response
    mock_response = ChatCompletion(
        id="test",
        model="gpt-4o-mini",
        object="chat.completion",
        created=1234567890,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="Hello!"),
                finish_reason="stop",
            )
        ],
    )
    mock_openai_client.chat.completions.create.return_value = mock_response

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="test-key", model="gpt-4o-mini")
        response = client.complete("Test prompt")

    assert response == "Hello!"
    mock_openai_client.chat.completions.create.assert_called_once()


def test_llm_client_retries_on_rate_limit(mock_openai_client: Mock) -> None:
    """Test client retries on rate limit errors."""
    # First two calls fail, third succeeds
    mock_response = ChatCompletion(
        id="test",
        model="gpt-4o-mini",
        object="chat.completion",
        created=1234567890,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="Success!"),
                finish_reason="stop",
            )
        ],
    )

    mock_openai_client.chat.completions.create.side_effect = [
        RateLimitError("Rate limit", response=Mock(), body=None),
        RateLimitError("Rate limit", response=Mock(), body=None),
        mock_response,
    ]

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="test-key", model="gpt-4o-mini", max_retries=3)
        response = client.complete("Test")

    assert response == "Success!"
    assert mock_openai_client.chat.completions.create.call_count == 3


def test_fatal_errors_defined() -> None:
    """Test FATAL_ERRORS tuple is defined."""
    assert AuthenticationError in FATAL_ERRORS
    assert PermissionDeniedError in FATAL_ERRORS


def test_retryable_errors_defined() -> None:
    """Test RETRYABLE_ERRORS tuple is defined."""
    assert RateLimitError in RETRYABLE_ERRORS


def test_llm_client_raises_fatal_error_without_retry(mock_openai_client: Mock) -> None:
    """Test fatal errors are raised immediately without retry."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_openai_client.chat.completions.create.side_effect = AuthenticationError(
        "Invalid API key", response=mock_response, body=None
    )

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="bad-key", model="gpt-4o-mini")
        with pytest.raises(FatalLLMError) as exc_info:
            client.complete("Test")

    # Should only be called once - no retries for fatal errors
    assert mock_openai_client.chat.completions.create.call_count == 1
    assert "AuthenticationError" in str(exc_info.value)


def test_llm_client_uses_max_retries_param(mock_openai_client: Mock) -> None:
    """Test client respects max_retries parameter."""
    mock_openai_client.chat.completions.create.side_effect = RateLimitError(
        "Rate limit", response=Mock(), body=None
    )

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="test-key", model="gpt-4o-mini", max_retries=5)
        with pytest.raises(Exception):  # Will fail after 5 retries
            client.complete("Test")

    assert mock_openai_client.chat.completions.create.call_count == 5
