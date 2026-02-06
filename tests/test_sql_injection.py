"""Test SQL injection protection in SQLiteAdapter."""

import sqlite3
from pathlib import Path

import pytest

from agents.adapters.sqlite_adapter import SQLiteAdapter, _validate_identifier, _validate_select_query


class TestSQLQueryValidation:
    """Test SQL query validation prevents injection."""

    def test_valid_select_allowed(self):
        """Test that basic SELECT queries are allowed."""
        assert _validate_select_query("SELECT * FROM data") == "SELECT * FROM data"

    def test_select_with_where(self):
        """Test SELECT with WHERE clause is allowed."""
        result = _validate_select_query("SELECT id, name FROM users WHERE id > 10")
        assert "SELECT" in result

    def test_insert_blocked(self):
        """Test INSERT statements are rejected."""
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_select_query("SELECT * FROM data; INSERT INTO data VALUES (1)")

    def test_drop_blocked(self):
        """Test DROP statements are rejected."""
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_select_query("SELECT * FROM data; DROP TABLE data")

    def test_update_blocked(self):
        """Test UPDATE statements are rejected."""
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_select_query("SELECT * FROM data; UPDATE data SET col=1")

    def test_delete_blocked(self):
        """Test DELETE statements are rejected."""
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_select_query("SELECT * FROM data; DELETE FROM data")

    def test_attach_blocked(self):
        """Test ATTACH is rejected (not a SELECT query)."""
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_select_query("ATTACH DATABASE '/etc/passwd' AS pwn")

    def test_attach_in_select_blocked(self):
        """Test ATTACH hidden inside a SELECT is also blocked."""
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_select_query("SELECT 1; ATTACH DATABASE '/etc/passwd' AS pwn")

    def test_pragma_blocked(self):
        """Test PRAGMA is rejected (not a SELECT query)."""
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_select_query("PRAGMA table_info(data)")

    def test_non_select_rejected(self):
        """Test non-SELECT queries are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_select_query("INSERT INTO data VALUES (1)")

    def test_case_insensitive_blocking(self):
        """Test that keyword blocking is case-insensitive."""
        with pytest.raises(ValueError, match="disallowed keyword"):
            _validate_select_query("SELECT * FROM data; drop TABLE data")


class TestIdentifierValidation:
    """Test SQL identifier validation."""

    def test_valid_identifier(self):
        """Test valid identifiers are accepted and quoted."""
        assert _validate_identifier("name") == '"name"'
        assert _validate_identifier("col_1") == '"col_1"'
        assert _validate_identifier("_private") == '"_private"'

    def test_invalid_identifier_rejected(self):
        """Test invalid identifiers are rejected."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier("col; DROP TABLE data")

        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier("col name")

        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier("123col")


class TestSQLiteAdapterSafety:
    """Test SQLiteAdapter prevents injection through URI parameters."""

    def test_malicious_query_in_uri_blocked(self, tmp_path: Path):
        """Test that dangerous queries in the URI are blocked."""
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE data (id INTEGER, text TEXT)")
        conn.execute("INSERT INTO data VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="disallowed keyword"):
            SQLiteAdapter(
                f"sqlite://{db_file}?query=SELECT * FROM data; DROP TABLE data",
                str(tmp_path / "output.db"),
            )

    def test_safe_query_works(self, tmp_path: Path):
        """Test that safe queries work correctly."""
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE data (id INTEGER, text TEXT)")
        conn.execute("INSERT INTO data VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        adapter = SQLiteAdapter(
            f"sqlite://{db_file}?query=SELECT * FROM data",
            str(tmp_path / "output.db"),
        )
        units = list(adapter.read_units())
        assert len(units) == 1
        assert units[0]["text"] == "hello"

    def test_write_results_validates_column_names(self, tmp_path: Path):
        """Test that write_results validates column names."""
        adapter = SQLiteAdapter(
            f"sqlite://{tmp_path}/test.db?query=SELECT * FROM data",
            str(tmp_path / "output.db"),
        )

        # Valid columns should work
        adapter.write_results([{"name": "test", "value": "123"}])

        # Invalid column name should raise
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            adapter.write_results([{"name; DROP TABLE results": "test"}])
