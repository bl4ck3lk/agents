"""CSV data adapter."""

import csv
from collections.abc import Iterator
from pathlib import Path

from agents.adapters.base import DataAdapter


class CSVAdapter(DataAdapter):
    """Adapter for CSV files."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize CSV adapter.

        Args:
            input_path: Path to input CSV file.
            output_path: Path to output CSV file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self._columns: list[str] = []

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read CSV rows as data units."""
        with open(self.input_path, newline="") as f:
            reader = csv.DictReader(f)
            self._columns = reader.fieldnames or []
            for row in reader:
                yield dict(row)

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Write results to CSV file."""
        if not results:
            return

        # Get all unique keys from results
        fieldnames = list(results[0].keys())

        with open(self.output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    def get_schema(self) -> dict[str, str]:
        """Get CSV schema information."""
        # Read columns if not already loaded
        if not self._columns:
            with open(self.input_path, newline="") as f:
                reader = csv.DictReader(f)
                self._columns = reader.fieldnames or []

        return {"type": "csv", "columns": self._columns}
