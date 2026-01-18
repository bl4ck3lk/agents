"""Integration tests for circuit breaker."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from agents.cli import cli
from agents.core.llm_client import FatalLLMError, LLMResponse, UsageMetadata


def make_success_response(content: str) -> LLMResponse:
    """Create a success LLMResponse with mock usage data."""
    return LLMResponse(
        content=content,
        usage=UsageMetadata(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )


def test_process_with_circuit_breaker_trip(tmp_path: Path) -> None:
    """Test full flow when circuit breaker trips."""
    # Create test input
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text('{"text": "hello"}\n' * 10)

    runner = CliRunner()

    with patch("agents.cli.LLMClient") as mock_client_class:
        mock_client = Mock()
        # Fail all requests with fatal error
        mock_client.complete_with_usage.side_effect = FatalLLMError(Exception("Invalid API key"))
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "process",
                str(input_file),
                str(output_file),
                "--prompt",
                "Test {text}",
                "--api-key",
                "test-key",
                "--circuit-breaker",
                "3",
                "--mode",
                "sequential",
            ],
            input="a\n",  # Abort when prompted
        )

    assert "Circuit breaker triggered" in result.output
    assert "3 consecutive failures" in result.output


def test_process_circuit_breaker_continue_then_succeed(tmp_path: Path) -> None:
    """Test circuit breaker continue option works."""
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text(
        '{"text": "item1"}\n{"text": "item2"}\n{"text": "item3"}\n{"text": "item4"}\n'
    )

    runner = CliRunner()

    with patch("agents.cli.LLMClient") as mock_client_class:
        mock_client = Mock()
        # First 2 fail (trip at 2), then succeed after user continues
        mock_client.complete_with_usage.side_effect = [
            FatalLLMError(Exception("err1")),
            FatalLLMError(Exception("err2")),
            make_success_response("Success 3"),
            make_success_response("Success 4"),
        ]
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "process",
                str(input_file),
                str(output_file),
                "--prompt",
                "Test {text}",
                "--api-key",
                "test-key",
                "--circuit-breaker",
                "2",
                "--mode",
                "sequential",
            ],
            input="c\n",  # Continue when prompted
        )

    assert "Circuit breaker triggered" in result.output
    assert "Resuming processing" in result.output
    assert "Processed" in result.output


def test_process_circuit_breaker_inspect_then_abort(tmp_path: Path) -> None:
    """Test circuit breaker inspect option shows details."""
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text('{"text": "hello"}\n{"text": "world"}\n')

    runner = CliRunner()

    with patch("agents.cli.LLMClient") as mock_client_class:
        mock_client = Mock()
        mock_client.complete_with_usage.side_effect = FatalLLMError(Exception("Detailed error message"))
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "process",
                str(input_file),
                str(output_file),
                "--prompt",
                "Test {text}",
                "--api-key",
                "test-key",
                "--circuit-breaker",
                "2",
                "--mode",
                "sequential",
            ],
            input="i\na\n",  # Inspect, then Abort
        )

    assert "Circuit breaker triggered" in result.output
    assert "Full Error Details" in result.output
    assert "Detailed error message" in result.output
    assert "Aborted" in result.output


def test_process_circuit_breaker_disabled(tmp_path: Path) -> None:
    """Test circuit breaker is disabled when threshold is 0."""
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text('{"text": "1"}\n{"text": "2"}\n{"text": "3"}\n')

    runner = CliRunner()

    with patch("agents.cli.LLMClient") as mock_client_class:
        mock_client = Mock()
        # All fail, but circuit breaker is disabled
        mock_client.complete_with_usage.side_effect = FatalLLMError(Exception("err"))
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            [
                "process",
                str(input_file),
                str(output_file),
                "--prompt",
                "Test {text}",
                "--api-key",
                "test-key",
                "--circuit-breaker",
                "0",  # Disabled
                "--mode",
                "sequential",
            ],
        )

    # Should complete without prompting (no circuit breaker trip)
    assert "Circuit breaker triggered" not in result.output
    assert "Completed with errors" in result.output
    assert "3 failed" in result.output
