"""JSONL (JSON Lines) data adapter."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agents.adapters.base import DataAdapter


class JSONLAdapter(DataAdapter):
    """Adapter for JSONL (JSON Lines) files."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize JSONL adapter.

        Args:
            input_path: Path to input JSONL file.
            output_path: Path to output JSONL file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    def read_units(self) -> Iterator[dict[str, Any]]:
        """Read JSONL lines as data units."""
        with open(self.input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def write_results(self, results: list[dict[str, Any]]) -> None:
        """Write results to JSONL file.

        Encoding must be utf-8 to handle non-ASCII characters
        """
        with open(self.output_path, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def get_schema(self) -> dict[str, Any]:
        """Get JSONL schema information."""
        return {"type": "jsonl"}
