"""Tests for memory MCP tools (memory_recall, memory_forget) and REST event endpoint."""

import json

import pytest

from spellbook.core.db import init_db, get_connection, close_all_connections
from spellbook.memory.store import (
    insert_memory,
    get_memory,
)
from tests._memory_marker import requires_memory_tools

pytestmark = requires_memory_tools


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


class TestMemoryRecallTool:
    """Test the do_memory_recall function directly (file-based)."""

    def test_recall_by_query(self, tmp_path, monkeypatch):
        """Query returns matching memories with correct structure."""
        from spellbook.memory.tools import do_memory_recall, do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        do_memory_store(
            content="Project uses FastAPI for REST endpoints with OpenAPI documentation",
            type="project",
            kind="fact",
            tags=["fastapi", "rest"],
            namespace="Users-alice-myproject",
        )

        result = do_memory_recall(
            query="fastapi",
            namespace="Users-alice-myproject",
            limit=5,
        )
        assert result["query"] == "fastapi"
        assert result["namespace"] == "Users-alice-myproject"
        assert result["count"] == 1
        assert len(result["memories"]) == 1
        mem = result["memories"][0]
        assert "FastAPI" in mem["content"]
        assert mem["type"] == "project"
        assert mem["kind"] == "fact"
        assert "fastapi" in mem["tags"]
        assert isinstance(mem["score"], float)
        assert mem["score"] > 0.0

    def test_recall_empty_query_returns_all(self, tmp_path, monkeypatch):
        """Empty query returns all memories."""
        from spellbook.memory.tools import do_memory_recall, do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        do_memory_store(
            content="Some important fact about the project architecture design",
            type="project",
            namespace="ns",
        )

        result = do_memory_recall(query="", namespace="ns", limit=5)
        assert result["query"] == ""
        assert result["namespace"] == "ns"
        assert result["count"] == 1
        assert len(result["memories"]) == 1
        assert "important fact" in result["memories"][0]["content"]

    def test_recall_by_file_path(self, tmp_path, monkeypatch):
        """file_path parameter filters by citation."""
        from spellbook.memory.tools import do_memory_recall, do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        do_memory_store(
            content="Module handles authentication and authorization for the API",
            type="project",
            kind="fact",
            tags=["auth"],
            citations=[{"file": "src/auth.py"}],
            namespace="ns",
        )

        result = do_memory_recall(
            query="", namespace="ns", limit=5, file_path="src/auth.py"
        )
        assert result["count"] == 1
        assert result["namespace"] == "ns"
        assert "authentication" in result["memories"][0]["content"]

    def test_recall_respects_limit(self, tmp_path, monkeypatch):
        """Limit parameter caps number of returned memories."""
        from spellbook.memory.tools import do_memory_recall, do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        for i in range(5):
            do_memory_store(
                content=f"Memory number {i} about testing framework integration patterns",
                type="project",
                tags=["testing"],
                namespace="ns",
            )

        result = do_memory_recall(query="testing", namespace="ns", limit=2)
        assert result["count"] == 2
        assert len(result["memories"]) == 2

    def test_recall_no_results(self, tmp_path, monkeypatch):
        """Query with no matches returns empty list."""
        from spellbook.memory.tools import do_memory_recall

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        result = do_memory_recall(
            query="nonexistent", namespace="ns", limit=5
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
        from spellbook.memory.tools import do_memory_forget

        result = do_memory_forget(db_path=db, memory_id=mem_id)
        assert result["status"] == "deleted"
        assert result["memory_id"] == mem_id
        assert result["message"] == (
            "Memory soft-deleted. Will be purged after 30 days. "
            "Content preview: To be forgotten content here..."
        )

        # Verify actual DB state changed
        mem = get_memory(db, mem_id)
        assert mem["status"] == "deleted"
        assert mem["deleted_at"] is not None

    def test_forget_nonexistent(self, db):
        """Forgetting a nonexistent memory returns not_found."""
        from spellbook.memory.tools import do_memory_forget

        result = do_memory_forget(db_path=db, memory_id="nonexistent-id")
        assert result == {"status": "not_found", "memory_id": "nonexistent-id"}

    def test_forget_excludes_from_recall(self, tmp_path, monkeypatch):
        """Forgotten memories are excluded from subsequent recall."""
        from spellbook.memory.tools import do_memory_forget, do_memory_recall, do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        store_result = do_memory_store(
            content="Will be forgotten soon with enough words for slug generation here",
            type="project",
            kind="fact",
            tags=["forgettable"],
            namespace="ns",
        )

        do_memory_forget(memory_id_or_query=store_result["path"], namespace="ns")

        result = do_memory_recall(query="forgettable", namespace="ns", limit=5)
        assert result["count"] == 0
        assert result["memories"] == []


class TestEventLogging:
    """Test the event logging function used by the REST endpoint."""

    def test_log_event(self, db):
        """Logging an event returns status and positive event_id."""
        from spellbook.memory.tools import do_log_event

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
        from spellbook.memory.tools import do_log_event

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


class TestMemoryStoreSchema:
    """Test the MEMORY_STORE_SCHEMA constant."""

    def test_schema_structure(self):
        """MEMORY_STORE_SCHEMA has correct top-level structure."""
        from spellbook.memory.tools import MEMORY_STORE_SCHEMA

        assert MEMORY_STORE_SCHEMA == {
            "type": "object",
            "required": ["memories"],
            "properties": {
                "memories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["content"],
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The synthesized memory content. Non-empty.",
                            },
                            "memory_type": {
                                "type": "string",
                                "enum": ["fact", "rule", "antipattern", "preference", "decision"],
                                "default": "fact",
                                "description": "Category of the memory.",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 20,
                                "description": "Keywords for retrieval. Max 20.",
                            },
                            "citations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["file_path"],
                                    "properties": {
                                        "file_path": {"type": "string"},
                                        "line_range": {"type": "string"},
                                        "snippet": {"type": "string"},
                                    },
                                },
                                "description": "Source file references.",
                            },
                        },
                    },
                },
            },
        }

    def test_schema_is_valid_json_serializable(self):
        """Schema can be JSON-serialized (needed for response_schema field)."""
        from spellbook.memory.tools import MEMORY_STORE_SCHEMA

        serialized = json.dumps(MEMORY_STORE_SCHEMA)
        deserialized = json.loads(serialized)
        assert deserialized == MEMORY_STORE_SCHEMA
