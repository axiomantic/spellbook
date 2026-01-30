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


def test_init_db_creates_skill_outcomes_table(tmp_path):
    """Test database initialization creates skill_outcomes table with correct schema."""
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    cursor = conn.cursor()

    # Check skill_outcomes table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='skill_outcomes'")
    assert cursor.fetchone() is not None

    # Check all columns exist with correct types
    cursor.execute("PRAGMA table_info(skill_outcomes)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "id" in columns
    assert "skill_name" in columns
    assert "skill_version" in columns
    assert "session_id" in columns
    assert "project_encoded" in columns
    assert "start_time" in columns
    assert "end_time" in columns
    assert "duration_seconds" in columns
    assert "outcome" in columns
    assert "tokens_used" in columns
    assert "corrections" in columns
    assert "retries" in columns
    assert "created_at" in columns

    conn.close()


def test_init_db_creates_telemetry_config_table(tmp_path):
    """Test database initialization creates telemetry_config table."""
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    cursor = conn.cursor()

    # Check telemetry_config table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telemetry_config'")
    assert cursor.fetchone() is not None

    # Check columns
    cursor.execute("PRAGMA table_info(telemetry_config)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "id" in columns
    assert "enabled" in columns
    assert "endpoint_url" in columns
    assert "last_sync" in columns
    assert "updated_at" in columns

    conn.close()


def test_init_db_creates_skill_outcomes_indices(tmp_path):
    """Test skill_outcomes table has required indices."""
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))
    cursor = conn.cursor()

    cursor.execute("PRAGMA index_list(skill_outcomes)")
    indices = [row[1] for row in cursor.fetchall()]

    assert any("skill_name" in idx or "name" in idx for idx in indices)
    assert any("project" in idx for idx in indices)
    assert any("time" in idx for idx in indices)

    conn.close()
