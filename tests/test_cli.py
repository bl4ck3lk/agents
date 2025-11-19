"""Tests for CLI interface."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agents.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner."""
    return CliRunner()


def test_cli_help(runner: CliRunner) -> None:
    """Test CLI help message."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "agents" in result.output.lower()


def test_cli_version(runner: CliRunner) -> None:
    """Test CLI version command."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
