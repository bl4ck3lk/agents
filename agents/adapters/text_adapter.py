"""Text file adapter."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agents.adapters.base import DataAdapter


class TextAdapter(DataAdapter):
    """Adapter for plain text files (line-by-line)."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize text adapter.

        Args:
            input_path: Path to input text file.
            output_path: Path to output text file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    def read_units(self) -> Iterator[dict[str, Any]]:
        """Read text lines as data units."""
        with open(self.input_path) as f:
            for line_number, line in enumerate(f, start=1):
                yield {"line_number": line_number, "content": line.rstrip("\n")}

    def write_results(self, results: list[dict[str, Any]]) -> None:
        """Write results to text file."""
        with open(self.output_path, "w") as f:
            for result in results:
                # Write the 'result' field if it exists, otherwise write content
                output_line = result.get("result", result.get("content", ""))
                f.write(output_line + "\n")

    def get_schema(self) -> dict[str, Any]:
        """Get text file schema information."""
        return {"type": "text"}
