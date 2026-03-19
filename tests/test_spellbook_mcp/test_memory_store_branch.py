"""Tests for branch support in memory_store operations."""

import pytest

from spellbook.core.db import close_all_connections, get_connection, init_db
from spellbook.memory.store import (
    get_recently_consolidated_events,
    get_unconsolidated_events,
    insert_memory,
    log_raw_event,
    mark_events_consolidated,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database with schema initialized."""
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path
    close_all_connections()


class TestLogRawEventBranch:
    def test_log_event_with_branch(self, db_path):
        """log_raw_event should store branch in raw_events table."""
        event_id = log_raw_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            event_type="tool_use",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
            tags="read,python",
            branch="feature-x",
        )
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM raw_events WHERE id = ?", (event_id,)
        )
        assert cursor.fetchone()[0] == "feature-x"

    def test_log_event_without_branch_defaults_empty(self, db_path):
        """log_raw_event without branch should store empty string."""
        event_id = log_raw_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            event_type="tool_use",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
            tags="read",
        )
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM raw_events WHERE id = ?", (event_id,)
        )
        assert cursor.fetchone()[0] == ""


class TestEventRetrievalBranch:
    def test_get_unconsolidated_events_includes_branch(self, db_path):
        """get_unconsolidated_events should return branch field."""
        log_raw_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            event_type="tool_use",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
            tags="read",
            branch="feature-x",
        )
        events = get_unconsolidated_events(db_path, limit=10)
        assert len(events) == 1
        assert events[0]["branch"] == "feature-x"

    def test_get_unconsolidated_events_branch_empty_when_not_set(self, db_path):
        """Events without branch should return empty string."""
        log_raw_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            event_type="tool_use",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
            tags="read",
        )
        events = get_unconsolidated_events(db_path, limit=10)
        assert events[0]["branch"] == ""

    def test_get_recently_consolidated_includes_branch(self, db_path):
        """get_recently_consolidated_events should return branch field."""
        event_id = log_raw_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            event_type="tool_use",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
            tags="read",
            branch="main",
        )
        mark_events_consolidated(db_path, [event_id], "batch1")
        events = get_recently_consolidated_events(db_path, limit=10)
        assert len(events) == 1
        assert events[0]["branch"] == "main"


class TestInsertMemoryJunction:
    def test_insert_memory_populates_junction_table(self, db_path):
        """insert_memory with branch should create origin association in memory_branches."""
        mem_id = insert_memory(
            db_path=db_path,
            content="Test memory for junction",
            memory_type="fact",
            namespace="test-project",
            tags=["test"],
            citations=[],
            branch="feature-x",
        )
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT memory_id, branch_name, association_type "
            "FROM memory_branches WHERE memory_id = ?",
            (mem_id,),
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == mem_id
        assert rows[0][1] == "feature-x"
        assert rows[0][2] == "origin"

    def test_insert_memory_no_branch_no_junction(self, db_path):
        """insert_memory without branch should NOT create junction table entry."""
        mem_id = insert_memory(
            db_path=db_path,
            content="Test memory no branch",
            memory_type="fact",
            namespace="test-project",
            tags=["test"],
            citations=[],
        )
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_branches WHERE memory_id = ?",
            (mem_id,),
        )
        assert cursor.fetchone()[0] == 0

    def test_insert_memory_dedup_no_duplicate_junction(self, db_path):
        """Deduplicating insert should not create a second junction entry."""
        mem_id_1 = insert_memory(
            db_path=db_path,
            content="Exact same content",
            memory_type="fact",
            namespace="test-project",
            tags=["test"],
            citations=[],
            branch="main",
        )
        mem_id_2 = insert_memory(
            db_path=db_path,
            content="Exact same content",
            memory_type="fact",
            namespace="test-project",
            tags=["test"],
            citations=[],
            branch="main",
        )
        assert mem_id_1 == mem_id_2
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_branches WHERE memory_id = ?",
            (mem_id_1,),
        )
        assert cursor.fetchone()[0] == 1

    def test_insert_memory_empty_string_branch_no_junction(self, db_path):
        """insert_memory with explicit empty string branch should NOT create junction entry."""
        mem_id = insert_memory(
            db_path=db_path,
            content="Explicit empty branch",
            memory_type="fact",
            namespace="test-project",
            tags=[],
            citations=[],
            branch="",
        )
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_branches WHERE memory_id = ?",
            (mem_id,),
        )
        assert cursor.fetchone()[0] == 0
