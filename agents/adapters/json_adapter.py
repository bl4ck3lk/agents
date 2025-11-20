"""JSON adapter for reading and writing JSON files."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agents.adapters.base import DataAdapter


class JSONAdapter(DataAdapter):
    """Adapter for JSON files (both arrays and single objects)."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize JSON adapter.

        Args:
            input_path: Path to input JSON file.
            output_path: Path to output JSON file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self._format: str | None = None

    def read_units(self) -> Iterator[dict[str, Any]]:
        """
        Read data units from JSON file.

        Yields:
            Data units as dictionaries.
        """
        with open(self.input_path) as f:
            data = json.load(f)

        if isinstance(data, list):
            self._format = "array"
            yield from data
        elif isinstance(data, dict):
            self._format = "object"
            yield data
        else:
            raise ValueError(f"Unsupported JSON format: expected array or object, got {type(data)}")

    def write_results(self, results: list[dict[str, Any]]) -> None:
        """
        Write results to JSON file.

        Args:
            results: List of result dictionaries to write.
        """
        with open(self.output_path, "w") as f:
            json.dump(results, f, indent=2)

    def get_schema(self) -> dict[str, Any]:
        """
        Get schema information for JSON file.

        Returns:
            Schema dictionary with type and format.
        """
        # Detect format if not already determined
        if self._format is None:
            with open(self.input_path) as f:
                data = json.load(f)

            if isinstance(data, list):
                self._format = "array"
            elif isinstance(data, dict):
                self._format = "object"
            else:
                self._format = "unknown"

        return {
            "type": "json",
            "format": self._format,
        }
