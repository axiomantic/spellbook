"""Tests for memory_branches junction table schema."""

import sqlite3

import pytest

from spellbook_mcp.db import close_all_connections, get_connection, init_db


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database with schema initialized."""
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path
    close_all_connections()


def test_memory_branches_table_exists(db_path):
    """memory_branches table should be created by init_db."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_branches'"
    )
    assert cursor.fetchone() is not None, "memory_branches table should exist"


def test_memory_branches_schema(db_path):
    """memory_branches should have correct columns and types."""
    conn = get_connection(db_path)
    cursor = conn.execute("PRAGMA table_info(memory_branches)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns == {
        "memory_id": "TEXT",
        "branch_name": "TEXT",
        "association_type": "TEXT",
        "created_at": "TEXT",
    }


def test_memory_branches_primary_key(db_path):
    """memory_branches PK should be (memory_id, branch_name) -- rejects duplicates."""
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO memory_branches (memory_id, branch_name, association_type, created_at) "
        "VALUES ('mem1', 'main', 'origin', '2026-01-01T00:00:00')"
    )
    # Duplicate (same memory_id + branch_name) should fail regardless of association_type
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO memory_branches (memory_id, branch_name, association_type, created_at) "
            "VALUES ('mem1', 'main', 'ancestor', '2026-01-01T00:00:00')"
        )


def test_memory_branches_allows_different_branches_same_memory(db_path):
    """Same memory_id with different branch_name should be allowed (M:N)."""
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO memory_branches (memory_id, branch_name, association_type, created_at) "
        "VALUES ('mem1', 'main', 'origin', '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO memory_branches (memory_id, branch_name, association_type, created_at) "
        "VALUES ('mem1', 'feature-x', 'ancestor', '2026-01-01T00:00:00')"
    )
    cursor = conn.execute(
        "SELECT branch_name, association_type FROM memory_branches "
        "WHERE memory_id = 'mem1' ORDER BY branch_name"
    )
    rows = cursor.fetchall()
    assert rows == [("feature-x", "ancestor"), ("main", "origin")]


def test_memory_branches_indexes(db_path):
    """memory_branches should have indexes on branch_name, memory_id, and association_type."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='memory_branches'"
    )
    index_names = {row[0] for row in cursor.fetchall()}
    assert "idx_memory_branches_branch" in index_names
    assert "idx_memory_branches_memory" in index_names
    assert "idx_memory_branches_type" in index_names


def test_memory_branches_default_association_type(db_path):
    """association_type should default to 'origin'."""
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO memory_branches (memory_id, branch_name, created_at) "
        "VALUES ('mem1', 'main', '2026-01-01T00:00:00')"
    )
    cursor = conn.execute(
        "SELECT association_type FROM memory_branches WHERE memory_id = 'mem1'"
    )
    assert cursor.fetchone()[0] == "origin"


def test_memory_branches_default_created_at(db_path):
    """created_at should default to current datetime when not provided."""
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO memory_branches (memory_id, branch_name, association_type) "
        "VALUES ('mem1', 'main', 'origin')"
    )
    cursor = conn.execute(
        "SELECT created_at FROM memory_branches WHERE memory_id = 'mem1'"
    )
    created_at = cursor.fetchone()[0]
    # Should be a non-empty datetime string (SQLite datetime('now') format)
    assert created_at is not None
    assert len(created_at) >= 19  # "YYYY-MM-DD HH:MM:SS" is 19 chars


def test_memory_branches_not_null_constraints(db_path):
    """memory_id and branch_name should be NOT NULL."""
    conn = get_connection(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO memory_branches (memory_id, branch_name) "
            "VALUES (NULL, 'main')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO memory_branches (memory_id, branch_name) "
            "VALUES ('mem1', NULL)"
        )
