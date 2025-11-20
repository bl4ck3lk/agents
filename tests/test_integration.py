"""Integration tests."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from agents.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create sample CSV file."""
    csv_file = tmp_path / "input.csv"
    csv_file.write_text("word\nhello\nworld\n")
    return csv_file


@pytest.fixture
def mock_openai_response() -> Mock:
    """Mock OpenAI response."""
    mock = Mock()
    mock.choices = [Mock(message=Mock(content='{"es": "hola"}'))]
    return mock


def test_process_csv_with_prompt(
    runner: CliRunner, sample_csv: Path, tmp_path: Path, mock_openai_response: Mock
) -> None:
    """Test processing CSV file with prompt."""
    output_file = tmp_path / "output.csv"

    with patch("agents.core.llm_client.OpenAI") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_openai_response

        result = runner.invoke(
            cli,
            [
                "process",
                str(sample_csv),
                str(output_file),
                "--prompt",
                "Translate {word}",
                "--api-key",
                "test-key",
            ],
        )

    assert result.exit_code == 0
    assert output_file.exists()
