"""SQLite database adapter."""

import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agents.adapters.base import DataAdapter

# Pattern to validate SQL identifiers (column/table names)
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate and quote a SQL identifier to prevent injection.

    Args:
        name: The identifier to validate.

    Returns:
        The quoted identifier safe for use in SQL.

    Raises:
        ValueError: If the identifier contains unsafe characters.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def _validate_select_query(query: str) -> str:
    """Validate that a query is a read-only SELECT statement.

    Args:
        query: The SQL query to validate.

    Returns:
        The validated query.

    Raises:
        ValueError: If the query is not a safe SELECT statement.
    """
    stripped = query.strip().rstrip(";").strip()
    # Must start with SELECT (case-insensitive)
    if not re.match(r"^\s*SELECT\s", stripped, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed")
    # Block dangerous keywords that could modify data
    dangerous_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "ATTACH",
        "DETACH",
        "PRAGMA",
    ]
    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", stripped, re.IGNORECASE):
            raise ValueError(f"Query contains disallowed keyword: {keyword}")
    return stripped


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
        raw_query = query_params.get("query", ["SELECT * FROM data"])[0]
        self.query = _validate_select_query(raw_query)
        self.output_path = Path(output_path)

    def read_units(self) -> Iterator[dict[str, Any]]:
        """Read database rows as data units."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(self.query)

        for row in cursor:
            yield {key: str(row[key]) for key in row.keys()}  # noqa: SIM118 - sqlite3.Row needs .keys()
        conn.close()

    def write_results(self, results: list[dict[str, Any]]) -> None:
        """Write results to SQLite database."""
        if not results:
            return

        # For simplicity, write to a new table
        conn = sqlite3.connect(self.output_path)

        # Create table from first result - validate column names to prevent injection
        columns = list(results[0].keys())
        quoted_columns = [_validate_identifier(col) for col in columns]
        placeholders = ", ".join(["?" for _ in columns])
        create_sql = f"CREATE TABLE IF NOT EXISTS results ({', '.join(f'{qcol} TEXT' for qcol in quoted_columns)})"
        insert_sql = f"INSERT INTO results VALUES ({placeholders})"

        conn.execute(create_sql)

        for result in results:
            conn.execute(insert_sql, [result[col] for col in columns])

        conn.commit()
        conn.close()

    def get_schema(self) -> dict[str, Any]:
        """Get SQLite schema information."""
        return {"type": "sqlite", "query": self.query}
