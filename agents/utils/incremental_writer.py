"""Incremental result writer for crash recovery."""

import json
from pathlib import Path
from typing import Any

# Keys that indicate a failed result
FAILURE_KEYS = {"error", "parse_error"}

# Key that indicates retries were exhausted
RETRIES_EXHAUSTED_KEY = "_retries_exhausted"


class IncrementalWriter:
    """Writes results incrementally to JSONL for crash recovery.

    Each result is appended immediately to a JSONL file, ensuring
    that processed results survive crashes. Results include an _idx
    field for ordering and deduplication on resume.
    """

    def __init__(self, job_id: str, checkpoint_dir: str | Path) -> None:
        """
        Initialize incremental writer.

        Args:
            job_id: Unique job identifier.
            checkpoint_dir: Directory for checkpoint files.
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.checkpoint_dir / f".results_{job_id}.jsonl"

    def write_result(self, result: dict[str, Any]) -> None:
        """
        Append single result to JSONL file.

        Args:
            result: Result dictionary (should include _idx field).
        """
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def get_completed_indices(self) -> set[int]:
        """
        Read JSONL and return set of completed _idx values.

        Returns:
            Set of indices that have been processed.
        """
        completed: set[int] = set()
        if not self.path.exists():
            return completed

        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    idx = data.get("_idx")
                    if idx is not None:
                        completed.add(idx)
                except json.JSONDecodeError:
                    # Skip malformed lines (e.g., partial writes from crash)
                    continue

        return completed

    def read_all_results(self) -> list[dict[str, Any]]:
        """
        Read all results from JSONL, sorted by _idx.

        Returns:
            List of results sorted by _idx.
        """
        results: list[dict[str, Any]] = []
        if not self.path.exists():
            return results

        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

        # Sort by _idx, with fallback for missing _idx
        return sorted(results, key=lambda x: x.get("_idx", float("inf")))

    def exists(self) -> bool:
        """Check if results file exists."""
        return self.path.exists()

    def count(self) -> int:
        """Count number of results in file."""
        return len(self.get_completed_indices())

    def get_failures(self) -> list[dict[str, Any]]:
        """
        Get all failed results (parse errors, errors, retries exhausted).

        Returns:
            List of failed result dicts.
        """
        failures: list[dict[str, Any]] = []
        if not self.path.exists():
            return failures

        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Check for any failure indicators
                    has_failure_key = any(key in data for key in FAILURE_KEYS)
                    retries_exhausted = data.get(RETRIES_EXHAUSTED_KEY, False)
                    if has_failure_key or retries_exhausted:
                        failures.append(data)
                except json.JSONDecodeError:
                    continue

        return sorted(failures, key=lambda x: x.get("_idx", float("inf")))

    def write_failures_file(self, output_dir: str | Path | None = None) -> Path | None:
        """
        Write failed items to a separate file for review.

        Args:
            output_dir: Directory to write failures file. Defaults to checkpoint_dir.

        Returns:
            Path to failures file, or None if no failures.
        """
        failures = self.get_failures()
        if not failures:
            return None

        out_dir = Path(output_dir) if output_dir else self.checkpoint_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # Extract job_id from results file name
        job_id = self.path.stem.replace(".results_", "").replace("results_", "")
        failures_path = out_dir / f"failures_{job_id}.jsonl"

        with open(failures_path, "w", encoding="utf-8") as f:
            for failure in failures:
                f.write(json.dumps(failure, ensure_ascii=False) + "\n")

        return failures_path
