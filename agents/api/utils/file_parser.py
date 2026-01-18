"""File parsing utilities for metadata extraction."""

import csv
import json
import os
import tempfile
from typing import Any

from agents.storage import StorageClient


class FileMetadata:
    """Metadata extracted from an uploaded file."""

    def __init__(
        self,
        row_count: int,
        columns: list[str],
        preview_rows: list[dict[str, Any]],
        file_type: str,
    ) -> None:
        self.row_count = row_count
        self.columns = columns
        self.preview_rows = preview_rows
        self.file_type = file_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "columns": self.columns,
            "preview_rows": self.preview_rows,
            "file_type": self.file_type,
        }


async def parse_file_metadata(
    storage_key: str,
    storage: StorageClient,
    preview_limit: int = 5,
) -> FileMetadata:
    """
    Parse an uploaded file and extract metadata.

    Args:
        storage_key: S3 key of the uploaded file
        storage: StorageClient instance
        preview_limit: Maximum number of rows to include in preview

    Returns:
        FileMetadata with row_count, columns, and preview_rows
    """
    # Detect file type from extension
    ext = os.path.splitext(storage_key)[1].lower()

    # Download file to temp location
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await storage.download_file_to_path(storage_key, tmp_path)

        if ext == ".csv":
            return _parse_csv(tmp_path, preview_limit)
        elif ext == ".json":
            return _parse_json(tmp_path, preview_limit)
        elif ext == ".jsonl":
            return _parse_jsonl(tmp_path, preview_limit)
        elif ext == ".txt":
            return _parse_text(tmp_path, preview_limit)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _parse_csv(file_path: str, preview_limit: int) -> FileMetadata:
    """Parse CSV file and extract metadata."""
    columns: list[str] = []
    preview_rows: list[dict[str, Any]] = []
    row_count = 0

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])

        for row in reader:
            row_count += 1
            if len(preview_rows) < preview_limit:
                preview_rows.append(dict(row))

    return FileMetadata(
        row_count=row_count,
        columns=columns,
        preview_rows=preview_rows,
        file_type="csv",
    )


def _parse_json(file_path: str, preview_limit: int) -> FileMetadata:
    """Parse JSON file and extract metadata."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        # JSON array of objects
        row_count = len(data)
        preview_rows = data[:preview_limit]
        # Extract columns from first object
        columns = list(data[0].keys()) if data and isinstance(data[0], dict) else []
    elif isinstance(data, dict):
        # Single object
        row_count = 1
        preview_rows = [data]
        columns = list(data.keys())
    else:
        raise ValueError("JSON file must contain an array or object")

    return FileMetadata(
        row_count=row_count,
        columns=columns,
        preview_rows=preview_rows,
        file_type="json",
    )


def _parse_jsonl(file_path: str, preview_limit: int) -> FileMetadata:
    """Parse JSONL file and extract metadata."""
    preview_rows: list[dict[str, Any]] = []
    columns: list[str] = []
    row_count = 0

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            row_count += 1
            obj = json.loads(line)

            if len(preview_rows) < preview_limit:
                preview_rows.append(obj)

            # Extract columns from first row
            if not columns and isinstance(obj, dict):
                columns = list(obj.keys())

    return FileMetadata(
        row_count=row_count,
        columns=columns,
        preview_rows=preview_rows,
        file_type="jsonl",
    )


def _parse_text(file_path: str, preview_limit: int) -> FileMetadata:
    """Parse text file (one line per unit) and extract metadata."""
    preview_rows: list[dict[str, Any]] = []
    row_count = 0

    with open(file_path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            content = line.rstrip("\n")
            row_count += 1

            if len(preview_rows) < preview_limit:
                preview_rows.append({
                    "line_number": line_number,
                    "content": content,
                })

    # Text files always have these columns
    columns = ["line_number", "content"]

    return FileMetadata(
        row_count=row_count,
        columns=columns,
        preview_rows=preview_rows,
        file_type="txt",
    )
