"""Data adapters for various input/output formats."""

import os
from pathlib import Path

from agents.adapters.base import DataAdapter
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.json_adapter import JSONAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.sqlite_adapter import SQLiteAdapter
from agents.adapters.text_adapter import TextAdapter


def _validate_path(file_path: str, allowed_dirs: list[str] | None = None) -> str:
    """Validate a file path to prevent path traversal attacks.

    Args:
        file_path: The file path to validate.
        allowed_dirs: Optional list of allowed parent directories.
            If None, just resolves and checks for traversal patterns.

    Returns:
        The resolved, validated path.

    Raises:
        ValueError: If the path contains traversal sequences or is outside allowed dirs.
    """
    resolved = os.path.realpath(file_path)

    if allowed_dirs and not any(resolved.startswith(os.path.realpath(d)) for d in allowed_dirs):
        raise ValueError(f"Path is outside allowed directories: {file_path}")

    return resolved


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

    # Validate paths to prevent path traversal
    _validate_path(input_path)
    if output_path:
        _validate_path(output_path)

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
