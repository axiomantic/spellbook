"""Tests for spellbook.core.db module.

Verifies that all public exports from spellbook_mcp.db exist in spellbook.core.db.
"""

import inspect
import sqlite3

import pytest


class TestCoreDbImports:
    """Test that spellbook.core.db is importable and has all expected exports."""

    def test_import_get_connection(self):
        from spellbook.core.db import get_connection

        assert callable(get_connection)

    def test_import_get_db_path(self):
        from spellbook.core.db import get_db_path

        assert callable(get_db_path)

    def test_import_init_db(self):
        from spellbook.core.db import init_db

        assert callable(init_db)

    def test_import_close_all_connections(self):
        from spellbook.core.db import close_all_connections

        assert callable(close_all_connections)

    def test_all_public_exports_match(self):
        """Every public function in spellbook_mcp.db must exist in spellbook.core.db."""
        import spellbook_mcp.db as old_mod
        import spellbook.core.db as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.core.db: {missing}"


class TestCoreDbFunctionality:
    """Test that spellbook.core.db functions work correctly."""

    def test_get_connection_returns_connection(self, tmp_path):
        from spellbook.core.db import get_connection, close_all_connections

        db_file = str(tmp_path / "test.db")
        try:
            conn = get_connection(db_file)
            assert isinstance(conn, sqlite3.Connection)
            # Verify WAL mode is enabled
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0] == "wal"
        finally:
            close_all_connections()

    def test_init_db_creates_tables(self, tmp_path):
        from spellbook.core.db import get_connection, init_db, close_all_connections

        db_file = str(tmp_path / "test.db")
        try:
            init_db(db_file)
            conn = get_connection(db_file)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "souls" in tables
            assert "memories" in tables
        finally:
            close_all_connections()
