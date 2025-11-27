"""Tests for incremental writer."""

import json
import tempfile
from pathlib import Path

import pytest

from agents.utils.incremental_writer import IncrementalWriter


@pytest.fixture
def temp_checkpoint_dir():
    """Create temporary checkpoint directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_get_failed_indices_returns_empty_for_new_job(temp_checkpoint_dir: Path) -> None:
    """Test get_failed_indices returns empty set for new job."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)
    assert writer.get_failed_indices() == set()


def test_get_failed_indices_finds_errors(temp_checkpoint_dir: Path) -> None:
    """Test get_failed_indices returns indices of items with errors."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)

    writer.write_result({"_idx": 0, "text": "ok", "result": "success"})
    writer.write_result({"_idx": 1, "text": "bad", "error": "API error"})
    writer.write_result({"_idx": 2, "text": "ok2", "result": "success"})
    writer.write_result({"_idx": 3, "text": "parse_fail", "parse_error": "Invalid JSON"})

    failed = writer.get_failed_indices()

    assert failed == {1, 3}


def test_read_all_results_deduplicates_by_idx(temp_checkpoint_dir: Path) -> None:
    """Test read_all_results keeps latest result per _idx."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)

    # First run: some failures
    writer.write_result({"_idx": 0, "text": "a", "result": "ok"})
    writer.write_result({"_idx": 1, "text": "b", "error": "failed"})
    writer.write_result({"_idx": 2, "text": "c", "result": "ok"})

    # Retry run: idx 1 succeeds
    writer.write_result({"_idx": 1, "text": "b", "result": "now ok"})

    results = writer.read_all_results()

    assert len(results) == 3
    assert results[0] == {"_idx": 0, "text": "a", "result": "ok"}
    assert results[1] == {"_idx": 1, "text": "b", "result": "now ok"}  # Updated!
    assert results[2] == {"_idx": 2, "text": "c", "result": "ok"}


def test_read_all_results_handles_multiple_retries(temp_checkpoint_dir: Path) -> None:
    """Test deduplication works with multiple retry attempts."""
    writer = IncrementalWriter("test_job", temp_checkpoint_dir)

    # Original
    writer.write_result({"_idx": 5, "error": "first failure"})
    # First retry
    writer.write_result({"_idx": 5, "error": "second failure"})
    # Second retry
    writer.write_result({"_idx": 5, "result": "finally worked"})

    results = writer.read_all_results()

    assert len(results) == 1
    assert results[0] == {"_idx": 5, "result": "finally worked"}
