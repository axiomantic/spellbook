"""Tests for memory MCP tools (memory_recall, memory_forget) and REST event endpoint."""

import json

import pytest

from spellbook_mcp.db import init_db, get_connection, close_all_connections
from spellbook_mcp.memory_store import insert_memory, get_memory


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


class TestMemoryRecallTool:
    """Test the do_memory_recall function directly."""

    def test_recall_by_query(self, db):
        """FTS5 query returns matching memories with correct structure."""
        mem_id = insert_memory(
            db_path=db,
            content="Project uses FastAPI for REST",
            memory_type="fact",
            namespace="Users-alice-myproject",
            tags=["fastapi", "rest"],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_recall

        result = do_memory_recall(
            db_path=db,
            query="fastapi",
            namespace="Users-alice-myproject",
            limit=5,
        )
        assert result["query"] == "fastapi"
        assert result["namespace"] == "Users-alice-myproject"
        assert result["count"] == 1
        assert len(result["memories"]) == 1
        mem = result["memories"][0]
        assert mem["id"] == mem_id
        assert mem["content"] == "Project uses FastAPI for REST"
        assert mem["memory_type"] == "fact"
        assert mem["status"] == "active"
        assert mem["importance"] == 1.0  # query-time snapshot (DB bumped after)
        assert isinstance(mem["created_at"], str)  # ISO timestamp, server-generated
        assert "T" in mem["created_at"]  # valid ISO format
        # accessed_at in returned dict is query-time snapshot (None for new memory)
        # update_access happens after results are fetched
        assert mem["accessed_at"] is None

        # But the DB was updated by update_access
        db_mem = get_memory(db, mem_id)
        assert db_mem["importance"] == 1.1
        assert isinstance(db_mem["accessed_at"], str)

    def test_recall_empty_query_returns_recent(self, db):
        """Empty query returns recent+important memories."""
        mem_id = insert_memory(
            db_path=db,
            content="Some important fact",
            memory_type="fact",
            namespace="ns",
            tags=[],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_recall

        result = do_memory_recall(db_path=db, query="", namespace="ns", limit=5)
        assert result["query"] == ""
        assert result["namespace"] == "ns"
        assert result["count"] == 1
        assert len(result["memories"]) == 1
        mem = result["memories"][0]
        assert mem["id"] == mem_id
        assert mem["content"] == "Some important fact"
        assert mem["memory_type"] == "fact"
        assert mem["status"] == "active"

    def test_recall_by_file_path(self, db):
        """file_path parameter routes to recall_by_file_path."""
        mem_id = insert_memory(
            db_path=db,
            content="Module handles auth",
            memory_type="fact",
            namespace="ns",
            tags=["auth"],
            citations=[{"file_path": "src/auth.py", "line_range": "1-50", "snippet": "class Auth:"}],
        )
        from spellbook_mcp.memory_tools import do_memory_recall

        result = do_memory_recall(
            db_path=db, query="", namespace="ns", limit=5, file_path="src/auth.py"
        )
        assert result["count"] == 1
        assert result["namespace"] == "ns"
        assert len(result["memories"]) == 1
        assert result["memories"][0]["id"] == mem_id
        assert result["memories"][0]["content"] == "Module handles auth"

    def test_recall_updates_access(self, db):
        """Recall bumps importance by 0.1 and sets accessed_at."""
        mem_id = insert_memory(
            db_path=db,
            content="Access tracking test",
            memory_type="fact",
            namespace="ns",
            tags=["tracking"],
            citations=[],
        )
        # Verify initial state: importance=1.0, accessed_at=None
        mem_before = get_memory(db, mem_id)
        assert mem_before["importance"] == 1.0
        assert mem_before["accessed_at"] is None

        from spellbook_mcp.memory_tools import do_memory_recall

        do_memory_recall(db_path=db, query="tracking", namespace="ns", limit=5)

        mem_after = get_memory(db, mem_id)
        assert mem_after["importance"] == 1.1
        assert isinstance(mem_after["accessed_at"], str)  # ISO timestamp, server-generated
        assert "T" in mem_after["accessed_at"]  # valid ISO format

    def test_recall_namespace_scoping(self, db):
        """Memories from different namespace are not returned."""
        insert_memory(
            db_path=db,
            content="Project A memory",
            memory_type="fact",
            namespace="project-a",
            tags=["shared"],
            citations=[],
        )
        insert_memory(
            db_path=db,
            content="Project B memory",
            memory_type="fact",
            namespace="project-b",
            tags=["shared"],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_recall

        result = do_memory_recall(
            db_path=db, query="memory", namespace="project-a", limit=10
        )
        assert result["count"] == 1
        assert result["memories"][0]["content"] == "Project A memory"

    def test_recall_respects_limit(self, db):
        """Limit parameter caps number of returned memories."""
        for i in range(5):
            insert_memory(
                db_path=db,
                content=f"Memory number {i} about testing",
                memory_type="fact",
                namespace="ns",
                tags=["testing"],
                citations=[],
            )
        from spellbook_mcp.memory_tools import do_memory_recall

        result = do_memory_recall(db_path=db, query="testing", namespace="ns", limit=2)
        assert result["count"] == 2
        assert len(result["memories"]) == 2

    def test_recall_no_results(self, db):
        """Query with no matches returns empty list."""
        from spellbook_mcp.memory_tools import do_memory_recall

        result = do_memory_recall(
            db_path=db, query="nonexistent", namespace="ns", limit=5
        )
        assert result == {
            "memories": [],
            "count": 0,
            "query": "nonexistent",
            "namespace": "ns",
        }


class TestMemoryForgetTool:
    """Test the do_memory_forget function directly."""

    def test_forget_existing(self, db):
        """Soft-deleting an existing memory marks it deleted with a message."""
        mem_id = insert_memory(
            db_path=db,
            content="To be forgotten content here",
            memory_type="fact",
            namespace="ns",
            tags=[],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_forget

        result = do_memory_forget(db_path=db, memory_id=mem_id)
        assert result["status"] == "deleted"
        assert result["memory_id"] == mem_id
        assert "To be forgotten content here" in result["message"]
        assert "30 days" in result["message"]

        # Verify actual DB state changed
        mem = get_memory(db, mem_id)
        assert mem["status"] == "deleted"
        assert mem["deleted_at"] is not None

    def test_forget_nonexistent(self, db):
        """Forgetting a nonexistent memory returns not_found."""
        from spellbook_mcp.memory_tools import do_memory_forget

        result = do_memory_forget(db_path=db, memory_id="nonexistent-id")
        assert result == {"status": "not_found", "memory_id": "nonexistent-id"}

    def test_forget_excludes_from_recall(self, db):
        """Forgotten memories are excluded from subsequent recall."""
        mem_id = insert_memory(
            db_path=db,
            content="Will be forgotten soon",
            memory_type="fact",
            namespace="ns",
            tags=["forgettable"],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_forget, do_memory_recall

        do_memory_forget(db_path=db, memory_id=mem_id)

        # FTS5 query should not return deleted memory
        result = do_memory_recall(db_path=db, query="forgettable", namespace="ns", limit=5)
        assert result["count"] == 0
        assert result["memories"] == []


class TestEventLogging:
    """Test the event logging function used by the REST endpoint."""

    def test_log_event(self, db):
        """Logging an event returns status and positive event_id."""
        from spellbook_mcp.memory_tools import do_log_event

        result = do_log_event(
            db_path=db,
            session_id="sess-1",
            project="Users-alice-myproject",
            tool_name="Read",
            subject="src/main.py",
            summary="Read src/main.py (45 lines)",
        )
        assert result["status"] == "logged"
        assert isinstance(result["event_id"], int)  # auto-increment ID, server-generated
        assert result["event_id"] > 0

        # Verify event was actually persisted
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT session_id, project, event_type, tool_name, subject, summary, tags "
            "FROM raw_events WHERE id = ?",
            (result["event_id"],),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "sess-1"
        assert row[1] == "Users-alice-myproject"
        assert row[2] == "tool_use"  # default event_type
        assert row[3] == "Read"
        assert row[4] == "src/main.py"
        assert row[5] == "Read src/main.py (45 lines)"
        assert row[6] == ""  # default empty tags

    def test_log_event_with_tags_and_event_type(self, db):
        """Custom tags and event_type are persisted."""
        from spellbook_mcp.memory_tools import do_log_event

        result = do_log_event(
            db_path=db,
            session_id="sess-2",
            project="Users-bob-proj",
            tool_name="Edit",
            subject="src/app.py",
            summary="Edited src/app.py line 10",
            tags="python,edit",
            event_type="file_edit",
        )
        assert result["status"] == "logged"
        assert result["event_id"] > 0

        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT event_type, tags FROM raw_events WHERE id = ?",
            (result["event_id"],),
        )
        row = cursor.fetchone()
        assert row[0] == "file_edit"
        assert row[1] == "python,edit"
