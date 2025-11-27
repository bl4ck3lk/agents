"""Tests for progress tracking."""

from pathlib import Path

from agents.utils.progress import ProgressTracker


def test_progress_tracker_initialization(tmp_path: Path) -> None:
    """Test progress tracker initializes correctly."""
    tracker = ProgressTracker(total=100, checkpoint_dir=str(tmp_path))
    assert tracker.total == 100
    assert tracker.processed == 0


def test_progress_tracker_update(tmp_path: Path) -> None:
    """Test progress tracker updates."""
    tracker = ProgressTracker(total=10, checkpoint_dir=str(tmp_path))

    tracker.update(1)
    assert tracker.processed == 1

    tracker.update(5)
    assert tracker.processed == 6


def test_progress_tracker_save_checkpoint(tmp_path: Path) -> None:
    """Test saving checkpoint."""
    tracker = ProgressTracker(total=100, checkpoint_dir=str(tmp_path), job_id="test-job")

    tracker.update(50)
    tracker.increment_failed()
    tracker.save_checkpoint()

    checkpoint_file = tmp_path / ".progress_test-job.json"
    assert checkpoint_file.exists()

    # Verify checkpoint data
    import json

    with open(checkpoint_file) as f:
        data = json.load(f)

    assert data["processed"] == 50
    assert data["total"] == 100
    assert data["failed"] == 1


def test_progress_tracker_load_checkpoint(tmp_path: Path) -> None:
    """Test loading checkpoint."""
    # Create checkpoint
    tracker1 = ProgressTracker(total=100, checkpoint_dir=str(tmp_path), job_id="test-job")
    tracker1.update(50)
    tracker1.save_checkpoint()

    # Load checkpoint
    tracker2 = ProgressTracker.load_checkpoint(str(tmp_path), "test-job")

    assert tracker2.processed == 50
    assert tracker2.total == 100
