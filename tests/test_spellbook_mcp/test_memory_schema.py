"""Tests for memory system schema tables."""

import pytest
from spellbook_mcp.db import init_db, get_connection, close_all_connections


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    close_all_connections()


def test_memories_table_exists(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
    )
    assert cursor.fetchone() is not None


def test_memories_table_columns(db):
    cursor = db.cursor()
    cursor.execute("PRAGMA table_info(memories)")
    columns = {row[1] for row in cursor.fetchall()}
    expected = {
        "id", "content", "memory_type", "namespace", "importance",
        "created_at", "accessed_at", "status", "deleted_at",
        "content_hash", "meta",
    }
    assert expected.issubset(columns)


def test_memory_citations_table_exists(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_citations'"
    )
    assert cursor.fetchone() is not None


def test_memory_citations_file_index(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_citations_file'"
    )
    assert cursor.fetchone() is not None


def test_memory_links_table_exists(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_links'"
    )
    assert cursor.fetchone() is not None


def test_raw_events_table_exists(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='raw_events'"
    )
    assert cursor.fetchone() is not None


def test_memory_audit_log_table_exists(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_audit_log'"
    )
    assert cursor.fetchone() is not None


def test_memories_fts_table_exists(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
    )
    assert cursor.fetchone() is not None


def test_memories_fts_insert_and_search(db):
    """FTS5 standalone table can be inserted into and searched."""
    cursor = db.cursor()
    # Insert a memory first (needed for rowid lookup)
    cursor.execute(
        "INSERT INTO memories (id, content, memory_type, namespace, importance, "
        "created_at, status, content_hash, meta) VALUES "
        "(?, ?, ?, ?, ?, datetime('now'), 'active', ?, '{}')",
        ("test-id-1", "pytest uses conftest.py for fixtures", "fact",
         "Users-alice-myproject", 1.0, "abc123"),
    )
    # Get the rowid reliably (not last_insert_rowid which can be fragile)
    cursor.execute("SELECT rowid FROM memories WHERE id = ?", ("test-id-1",))
    mem_rowid = cursor.fetchone()[0]
    # Insert into FTS5 (standalone table -- must be kept in sync manually)
    cursor.execute(
        "INSERT INTO memories_fts (rowid, content, tags, citations) VALUES "
        "(?, ?, ?, ?)",
        (mem_rowid, "pytest uses conftest.py for fixtures", "pytest fixtures conftest", "conftest.py"),
    )
    db.commit()
    # Search
    cursor.execute(
        "SELECT content FROM memories_fts WHERE memories_fts MATCH 'pytest'"
    )
    results = cursor.fetchall()
    assert len(results) == 1
    assert "pytest" in results[0][0]


def test_schema_idempotent(tmp_path):
    """Calling init_db twice does not raise."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # Should not raise
    close_all_connections()
