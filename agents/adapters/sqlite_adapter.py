"""SQLite database adapter."""

import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agents.adapters.base import DataAdapter


class SQLiteAdapter(DataAdapter):
    """Adapter for SQLite databases."""

    def __init__(self, input_uri: str, output_path: str) -> None:
        """
        Initialize SQLite adapter.

        Args:
            input_uri: SQLite URI with query (sqlite://path?query=SELECT...)
            output_path: Path to output file.
        """
        parsed = urlparse(input_uri)
        self.db_path = parsed.path
        query_params = parse_qs(parsed.query)
        self.query = query_params.get("query", ["SELECT * FROM data"])[0]
        self.output_path = Path(output_path)

    def read_units(self):
        """Read database rows as data units."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(self.query)

        for row in cursor:
            yield {key: str(row[key]) for key in row.keys()}

        conn.close()

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Write results to SQLite database."""
        if not results:
            return

        # For simplicity, write to a new table
        conn = sqlite3.connect(self.output_path)

        # Create table from first result
        columns = list(results[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        create_sql = f"CREATE TABLE IF NOT EXISTS results ({', '.join(f'{col} TEXT' for col in columns)})"
        insert_sql = f"INSERT INTO results VALUES ({placeholders})"

        conn.execute(create_sql)

        for result in results:
            conn.execute(insert_sql, [result[col] for col in columns])

        conn.commit()
        conn.close()

    def get_schema(self) -> dict[str, Any]:
        """Get SQLite schema information."""
        return {"type": "sqlite", "query": self.query}
