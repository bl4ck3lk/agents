"""Data adapters for various input/output formats."""

from pathlib import Path

from agents.adapters.base import DataAdapter
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.json_adapter import JSONAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.sqlite_adapter import SQLiteAdapter
from agents.adapters.text_adapter import TextAdapter


def get_adapter(input_path: str, output_path: str | None = None) -> DataAdapter:
    """Get appropriate adapter based on file extension or URI scheme.

    Args:
        input_path: Path to input file or SQLite URI
        output_path: Optional path to output file

    Returns:
        DataAdapter instance for the detected format
    """
    # Check if it's a SQLite URI
    if input_path.startswith("sqlite://"):
        return SQLiteAdapter(input_path, output_path or "")

    # Otherwise, detect by file extension
    ext = Path(input_path).suffix.lower()

    if ext == ".csv":
        return CSVAdapter(input_path, output_path or "")
    elif ext == ".json":
        return JSONAdapter(input_path, output_path or "")
    elif ext == ".jsonl":
        return JSONLAdapter(input_path, output_path or "")
    elif ext == ".txt":
        return TextAdapter(input_path, output_path or "")
    else:
        raise ValueError(f"Unsupported file format: {ext}")


__all__ = [
    "DataAdapter",
    "CSVAdapter",
    "JSONAdapter",
    "JSONLAdapter",
    "SQLiteAdapter",
    "TextAdapter",
    "get_adapter",
]
