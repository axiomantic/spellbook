"""Tests for database schema and connection management."""

import pytest
import sqlite3
from pathlib import Path


def test_init_db_creates_schema(tmp_path):
    """Test database initialization creates all required tables."""
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    cursor = conn.cursor()

    # Check souls table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='souls'")
    assert cursor.fetchone() is not None

    # Check subagents table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subagents'")
    assert cursor.fetchone() is not None

    # Check decisions table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='decisions'")
    assert cursor.fetchone() is not None

    # Check corrections table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corrections'")
    assert cursor.fetchone() is not None

    # Check heartbeat table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='heartbeat'")
    assert cursor.fetchone() is not None

    conn.close()


def test_wal_mode_enabled(tmp_path):
    """Test that WAL mode is enabled for concurrent access."""
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    result = cursor.fetchone()[0]

    assert result.upper() == "WAL"
    conn.close()


def test_get_db_path_creates_directory():
    """Test that get_db_path creates parent directory if needed."""
    from spellbook_mcp.db import get_db_path

    db_path = get_db_path()

    # Should be ~/.local/spellbook/spellbook.db
    assert db_path.name == "spellbook.db"
    assert db_path.parent.name == "spellbook"
    assert db_path.parent.exists()  # Directory should be created
