"""Tests for data adapters."""

from typing import Iterator

import pytest

from agents.adapters.base import DataAdapter


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

    def get_schema(self) -> dict[str, str]:
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
