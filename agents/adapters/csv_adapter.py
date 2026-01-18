"""CSV data adapter."""

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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

    def read_units(self) -> Iterator[dict[str, Any]]:
        """Read CSV rows as data units."""
        with open(self.input_path, newline="") as f:
            reader = csv.DictReader(f)
            self._columns = list(reader.fieldnames or [])
            for row in reader:
                yield dict(row)

    def write_results(self, results: list[dict[str, Any]]) -> None:
        """Write results to CSV file."""
        if not results:
            return

        # Ensure columns are loaded
        if not self._columns:
            self.get_schema()

        fieldnames = self._columns or list(results[0].keys())

        # Filter results to only include original CSV fields
        filtered_results = []
        for result in results:
            filtered_result = {key: result.get(key, "") for key in fieldnames}
            filtered_results.append(filtered_result)

        with open(self.output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_results)

    def get_schema(self) -> dict[str, Any]:
        """Get CSV schema information."""
        # Read columns if not already loaded
        if not self._columns:
            with open(self.input_path, newline="") as f:
                reader = csv.DictReader(f)
                self._columns = list(reader.fieldnames or [])

        return {"type": "csv", "columns": self._columns}
