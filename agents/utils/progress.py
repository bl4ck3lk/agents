"""Progress tracking and checkpointing."""

import json
from pathlib import Path
from typing import Any


class ProgressTracker:
    """Track processing progress and save checkpoints."""

    def __init__(
        self,
        total: int,
        checkpoint_dir: str,
        job_id: str = "default",
        checkpoint_interval: int = 100,
    ) -> None:
        """
        Initialize progress tracker.

        Args:
            total: Total number of units to process.
            checkpoint_dir: Directory for checkpoint files.
            job_id: Unique job identifier.
            checkpoint_interval: Save checkpoint every N units.
        """
        self.total = total
        self.processed = 0
        self.failed = 0
        self.checkpoint_dir = Path(checkpoint_dir)
        self.job_id = job_id
        self.checkpoint_interval = checkpoint_interval

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def update(self, count: int = 1) -> None:
        """
        Update processed count.

        Args:
            count: Number of units processed.
        """
        self.processed += count

        if self.processed % self.checkpoint_interval == 0:
            self.save_checkpoint()

    def increment_failed(self) -> None:
        """Increment failed count."""
        self.failed += 1

    def save_checkpoint(self) -> None:
        """Save checkpoint to file."""
        checkpoint_file = self.checkpoint_dir / f".progress_{self.job_id}.json"
        data = {
            "processed": self.processed,
            "total": self.total,
            "failed": self.failed,
            "job_id": self.job_id,
        }

        with open(checkpoint_file, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_checkpoint(cls, checkpoint_dir: str, job_id: str) -> "ProgressTracker":
        """
        Load progress from checkpoint file.

        Args:
            checkpoint_dir: Directory containing checkpoint.
            job_id: Job identifier.

        Returns:
            Restored progress tracker.
        """
        checkpoint_file = Path(checkpoint_dir) / f".progress_{job_id}.json"

        with open(checkpoint_file) as f:
            data = json.load(f)

        tracker = cls(total=data["total"], checkpoint_dir=checkpoint_dir, job_id=data["job_id"])
        tracker.processed = data["processed"]
        tracker.failed = data.get("failed", 0)

        return tracker

    def get_progress(self) -> dict[str, Any]:
        """Get current progress stats."""
        percentage = (self.processed / self.total * 100) if self.total > 0 else 0
        return {
            "processed": self.processed,
            "total": self.total,
            "failed": self.failed,
            "percentage": round(percentage, 1),
        }
