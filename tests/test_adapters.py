"""Tests for data adapters."""

import csv
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agents.adapters.base import DataAdapter
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.sqlite_adapter import SQLiteAdapter
from agents.adapters.text_adapter import TextAdapter


class MockAdapter(DataAdapter):
    """Mock adapter for testing."""

    def __init__(self, units: list[dict[str, str]]) -> None:
        self._units = units
        self.results: list[dict[str, str]] = []

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read mock data units."""
        yield from self._units

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Store results."""
        self.results = results

    def get_schema(self) -> dict[str, Any]:
        """Get schema."""
        return {"type": "mock"}


def test_adapter_interface() -> None:
    """Test adapter implements required interface."""
    units = [{"id": "1", "text": "hello"}, {"id": "2", "text": "world"}]
    adapter = MockAdapter(units)

    # Test read_units
    read_units = list(adapter.read_units())
    assert read_units == units

    # Test write_results
    results = [{"id": "1", "result": "hola"}, {"id": "2", "result": "mundo"}]
    adapter.write_results(results)
    assert adapter.results == results

    # Test get_schema
    schema = adapter.get_schema()
    assert schema == {"type": "mock"}


def test_csv_adapter_read(tmp_path: Path) -> None:
    """Test CSV adapter reads data correctly."""
    # Create sample CSV
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,text\n1,hello\n2,world\n")

    adapter = CSVAdapter(str(csv_file), str(tmp_path / "output.csv"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": "1", "text": "hello"}
    assert units[1] == {"id": "2", "text": "world"}


def test_csv_adapter_write(tmp_path: Path) -> None:
    """Test CSV adapter writes results correctly."""
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "output.csv"
    input_file.write_text("id,text\n1,hello\n2,world\n")

    adapter = CSVAdapter(str(input_file), str(output_file))
    results = [
        {"id": "1", "text": "hello", "result": "hola"},
        {"id": "2", "text": "world", "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output
    with open(output_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0] == {"id": "1", "text": "hello", "result": "hola"}
    assert rows[1] == {"id": "2", "text": "world", "result": "mundo"}


def test_csv_adapter_get_schema(tmp_path: Path) -> None:
    """Test CSV adapter returns schema."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,text,category\n1,hello,greeting\n")

    adapter = CSVAdapter(str(csv_file), str(tmp_path / "output.csv"))
    schema = adapter.get_schema()

    assert schema["columns"] == ["id", "text", "category"]
    assert schema["type"] == "csv"


def test_jsonl_adapter_read(tmp_path: Path) -> None:
    """Test JSONL adapter reads data correctly."""
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text('{"id": "1", "text": "hello"}\n{"id": "2", "text": "world"}\n')

    adapter = JSONLAdapter(str(jsonl_file), str(tmp_path / "output.jsonl"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": "1", "text": "hello"}
    assert units[1] == {"id": "2", "text": "world"}


def test_jsonl_adapter_write(tmp_path: Path) -> None:
    """Test JSONL adapter writes results correctly."""
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text('{"id": "1"}\n{"id": "2"}\n')

    adapter = JSONLAdapter(str(input_file), str(output_file))
    results = [
        {"id": "1", "result": "hola"},
        {"id": "2", "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"id": "1", "result": "hola"}
    assert json.loads(lines[1]) == {"id": "2", "result": "mundo"}


def test_text_adapter_read(tmp_path: Path) -> None:
    """Test text adapter reads lines correctly."""
    text_file = tmp_path / "test.txt"
    text_file.write_text("hello\nworld\n")

    adapter = TextAdapter(str(text_file), str(tmp_path / "output.txt"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"line_number": 1, "content": "hello"}
    assert units[1] == {"line_number": 2, "content": "world"}


def test_text_adapter_write(tmp_path: Path) -> None:
    """Test text adapter writes results correctly."""
    input_file = tmp_path / "input.txt"
    output_file = tmp_path / "output.txt"
    input_file.write_text("hello\nworld\n")

    adapter = TextAdapter(str(input_file), str(output_file))
    results = [
        {"line_number": 1, "content": "hello", "result": "hola"},
        {"line_number": 2, "content": "world", "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output - should write just the result field
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert lines[0] == "hola"
    assert lines[1] == "mundo"


def test_sqlite_adapter_read(tmp_path: Path) -> None:
    """Test SQLite adapter reads data correctly."""
    db_file = tmp_path / "test.db"

    # Create test database
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE words (id INTEGER, word TEXT)")
    conn.execute("INSERT INTO words VALUES (1, 'hello'), (2, 'world')")
    conn.commit()
    conn.close()

    adapter = SQLiteAdapter(
        f"sqlite://{db_file}?query=SELECT * FROM words", str(tmp_path / "output.db")
    )
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": "1", "word": "hello"}
    assert units[1] == {"id": "2", "word": "world"}


def test_json_adapter_read_array(tmp_path: Path) -> None:
    """Test JSON adapter reads array correctly."""
    from agents.adapters.json_adapter import JSONAdapter

    json_file = tmp_path / "test.json"
    json_file.write_text('[{"id": 1, "text": "hello"}, {"id": 2, "text": "world"}]')

    adapter = JSONAdapter(str(json_file), str(tmp_path / "output.json"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": 1, "text": "hello"}
    assert units[1] == {"id": 2, "text": "world"}


def test_json_adapter_read_single_object(tmp_path: Path) -> None:
    """Test JSON adapter reads single object correctly."""
    from agents.adapters.json_adapter import JSONAdapter

    json_file = tmp_path / "test.json"
    json_file.write_text('{"id": 1, "text": "hello"}')

    adapter = JSONAdapter(str(json_file), str(tmp_path / "output.json"))
    units = list(adapter.read_units())

    assert len(units) == 1
    assert units[0] == {"id": 1, "text": "hello"}


def test_json_adapter_write_array(tmp_path: Path) -> None:
    """Test JSON adapter writes results as array."""
    from agents.adapters.json_adapter import JSONAdapter

    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    input_file.write_text('[{"id": 1}, {"id": 2}]')

    adapter = JSONAdapter(str(input_file), str(output_file))
    results = [
        {"id": 1, "result": "hola"},
        {"id": 2, "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output
    output_data = json.loads(output_file.read_text())
    assert len(output_data) == 2
    assert output_data[0] == {"id": 1, "result": "hola"}
    assert output_data[1] == {"id": 2, "result": "mundo"}


def test_json_adapter_get_schema(tmp_path: Path) -> None:
    """Test JSON adapter returns schema."""
    from agents.adapters.json_adapter import JSONAdapter

    json_file = tmp_path / "test.json"
    json_file.write_text('[{"id": 1, "text": "hello"}]')

    adapter = JSONAdapter(str(json_file), str(tmp_path / "output.json"))
    schema = adapter.get_schema()

    assert schema["type"] == "json"
    assert schema["format"] == "array"
