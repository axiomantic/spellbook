"""Tests for memory MCP tools (memory_recall, memory_forget) and REST event endpoint."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from spellbook_mcp.db import init_db, get_connection, close_all_connections
from spellbook_mcp.memory_store import (
    insert_memory,
    get_memory,
    log_raw_event,
    mark_events_consolidated,
)


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
        # Verify valid ISO 8601 format by parsing
        from datetime import datetime
        datetime.fromisoformat(mem["created_at"])
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
        # Verify valid ISO 8601 format by parsing
        from datetime import datetime
        datetime.fromisoformat(mem_after["accessed_at"])

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


class TestMemoryStoreSchema:
    """Test the MEMORY_STORE_SCHEMA constant."""

    def test_schema_structure(self):
        """MEMORY_STORE_SCHEMA has correct top-level structure."""
        from spellbook_mcp.memory_tools import MEMORY_STORE_SCHEMA

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
        from spellbook_mcp.memory_tools import MEMORY_STORE_SCHEMA

        serialized = json.dumps(MEMORY_STORE_SCHEMA)
        deserialized = json.loads(serialized)
        assert deserialized == MEMORY_STORE_SCHEMA


class TestDoGetUnconsolidated:
    """Test the do_get_unconsolidated function."""

    def _log_events(self, db, count=3, project="test-project"):
        """Helper to log raw events and return their IDs."""
        event_ids = []
        for i in range(count):
            eid = log_raw_event(
                db_path=db,
                session_id="sess-1",
                project=project,
                event_type="tool_use",
                tool_name="Read",
                subject=f"src/file{i}.py",
                summary=f"Read file{i}.py ({i * 10 + 5} lines)",
                tags="python,read",
            )
            event_ids.append(eid)
        return event_ids

    def test_no_events_returns_empty(self, db):
        """No unconsolidated events returns empty result with schema."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated, MEMORY_STORE_SCHEMA

        result = do_get_unconsolidated(db_path=db, namespace="test-project")
        assert result == {
            "events": [],
            "count": 0,
            "consolidation_prompt": "",
            "response_schema": json.dumps(MEMORY_STORE_SCHEMA),
        }

    def test_returns_unconsolidated_events(self, db):
        """Returns unconsolidated events with count, prompt, and schema."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated, MEMORY_STORE_SCHEMA

        event_ids = self._log_events(db, count=2, project="test-project")

        result = do_get_unconsolidated(db_path=db, namespace="test-project")

        assert result["count"] == 2
        assert len(result["events"]) == 2
        # Verify event structure
        assert result["events"][0]["id"] == event_ids[0]
        assert result["events"][0]["session_id"] == "sess-1"
        assert result["events"][0]["project"] == "test-project"
        assert result["events"][0]["event_type"] == "tool_use"
        assert result["events"][0]["tool_name"] == "Read"
        assert result["events"][0]["subject"] == "src/file0.py"
        assert result["events"][0]["summary"] == "Read file0.py (5 lines)"
        assert result["events"][0]["tags"] == "python,read"
        assert isinstance(result["events"][0]["timestamp"], str)

        assert result["events"][1]["id"] == event_ids[1]
        assert result["events"][1]["subject"] == "src/file1.py"
        assert result["events"][1]["summary"] == "Read file1.py (15 lines)"

        # Prompt should match build_consolidation_prompt() exactly
        from spellbook_mcp.memory_consolidation import build_consolidation_prompt
        expected_prompt = build_consolidation_prompt(result["events"])
        assert result["consolidation_prompt"] == expected_prompt

        # Schema should be JSON-serialized MEMORY_STORE_SCHEMA
        assert result["response_schema"] == json.dumps(MEMORY_STORE_SCHEMA)

    def test_namespace_filtering(self, db):
        """Only events matching namespace are returned."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated

        self._log_events(db, count=2, project="project-a")
        self._log_events(db, count=1, project="project-b")

        result = do_get_unconsolidated(db_path=db, namespace="project-a")
        assert result["count"] == 2
        for event in result["events"]:
            assert event["project"] == "project-a"

    def test_empty_namespace_returns_all(self, db):
        """Empty namespace string returns all events."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated

        self._log_events(db, count=2, project="project-a")
        self._log_events(db, count=1, project="project-b")

        result = do_get_unconsolidated(db_path=db, namespace="")
        assert result["count"] == 3

    def test_limit_parameter(self, db):
        """Limit parameter caps number of returned events."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated

        self._log_events(db, count=5, project="test-project")

        result = do_get_unconsolidated(db_path=db, namespace="test-project", limit=2)
        assert result["count"] == 2
        assert len(result["events"]) == 2

    def test_include_consolidated_merges_events(self, db):
        """include_consolidated=True merges recently consolidated events."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated

        # Log and consolidate some events
        consolidated_ids = self._log_events(db, count=2, project="test-project")
        mark_events_consolidated(db, consolidated_ids, "batch-1")

        # Log some unconsolidated events
        unconsolidated_ids = self._log_events(db, count=1, project="test-project")

        result = do_get_unconsolidated(
            db_path=db, namespace="test-project", include_consolidated=True,
        )
        # Should have unconsolidated + recently consolidated
        returned_ids = [e["id"] for e in result["events"]]
        assert unconsolidated_ids[0] in returned_ids
        # Consolidated events should also appear (they were consolidated recently)
        for cid in consolidated_ids:
            assert cid in returned_ids
        assert result["count"] == 3

    def test_include_consolidated_respects_limit(self, db):
        """include_consolidated=True still respects the total limit."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated

        # Log and consolidate events
        consolidated_ids = self._log_events(db, count=3, project="test-project")
        mark_events_consolidated(db, consolidated_ids, "batch-1")

        # Log unconsolidated events
        self._log_events(db, count=3, project="test-project")

        result = do_get_unconsolidated(
            db_path=db, namespace="test-project", include_consolidated=True, limit=4,
        )
        # Should cap at limit=4 total
        assert result["count"] == 4
        assert len(result["events"]) == 4

    def test_include_consolidated_no_duplicates(self, db):
        """include_consolidated=True does not duplicate events."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated

        # All unconsolidated, none consolidated
        event_ids = self._log_events(db, count=3, project="test-project")

        result = do_get_unconsolidated(
            db_path=db, namespace="test-project", include_consolidated=True,
        )
        returned_ids = [e["id"] for e in result["events"]]
        assert len(returned_ids) == len(set(returned_ids))  # No duplicates
        assert result["count"] == 3


class TestDoStoreMemories:
    """Test the do_store_memories function."""

    def _log_events(self, db, count=3, project="test-project"):
        """Helper to log raw events and return their IDs."""
        event_ids = []
        for i in range(count):
            eid = log_raw_event(
                db_path=db,
                session_id="sess-1",
                project=project,
                event_type="tool_use",
                tool_name="Read",
                subject=f"src/file{i}.py",
                summary=f"Read file{i}.py ({i * 10 + 5} lines)",
                tags="python,read",
            )
            event_ids.append(eid)
        return event_ids

    def test_store_valid_memories(self, db):
        """Stores valid memories and returns success with correct counts."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Project uses pytest for testing",
                    "memory_type": "fact",
                    "tags": ["pytest", "testing"],
                    "citations": [{"file_path": "tests/conftest.py"}],
                },
                {
                    "content": "Always run linter before commit",
                    "memory_type": "rule",
                    "tags": ["linting", "workflow"],
                    "citations": [],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 2
        assert result["events_consolidated"] == 0
        assert len(result["memory_ids"]) == 2

        # Verify memories were actually stored with correct content
        mem1 = get_memory(db, result["memory_ids"][0])
        assert mem1["content"] == "Project uses pytest for testing"
        assert mem1["memory_type"] == "fact"
        assert mem1["namespace"] == "test-project"
        meta1 = json.loads(mem1["meta"])
        assert meta1["source"] == "client_llm"
        assert meta1["tags"] == ["pytest", "testing"]

        mem2 = get_memory(db, result["memory_ids"][1])
        assert mem2["content"] == "Always run linter before commit"
        assert mem2["memory_type"] == "rule"
        meta2 = json.loads(mem2["meta"])
        assert meta2["source"] == "client_llm"

    def test_store_bare_list_format(self, db):
        """Accepts bare list format (not wrapped in {"memories": [...]})."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps([
            {
                "content": "Use type hints everywhere",
                "memory_type": "rule",
                "tags": ["typing"],
                "citations": [],
            },
        ])

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1
        assert len(result["memory_ids"]) == 1

        mem = get_memory(db, result["memory_ids"][0])
        assert mem["content"] == "Use type hints everywhere"
        assert mem["memory_type"] == "rule"

    def test_store_invalid_json(self, db):
        """Invalid JSON returns error."""
        from spellbook_mcp.memory_tools import do_store_memories

        result = do_store_memories(
            db_path=db,
            memories_json="not valid json{{{",
            namespace="test-project",
        )
        assert result["status"] == "error"
        assert result["error"].startswith("Invalid JSON: ")

    def test_store_non_object_non_array(self, db):
        """Non-object/non-array JSON returns error."""
        from spellbook_mcp.memory_tools import do_store_memories

        result = do_store_memories(
            db_path=db,
            memories_json='"just a string"',
            namespace="test-project",
        )
        assert result["status"] == "error"
        assert result["error"] == "Expected JSON object or array"

    def test_store_empty_content_rejected(self, db):
        """Memories with empty content are rejected."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {"content": "", "memory_type": "fact", "tags": [], "citations": []},
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "error"
        assert result["error"] == "No valid memories found. Each memory must have non-empty 'content'."

    def test_store_invalid_memory_type_defaults_to_fact(self, db):
        """Invalid memory_type is silently corrected to 'fact'."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Some memory with bad type",
                    "memory_type": "invalid_type",
                    "tags": ["test"],
                    "citations": [],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1

        mem = get_memory(db, result["memory_ids"][0])
        assert mem["memory_type"] == "fact"

    def test_store_tags_capped_at_20(self, db):
        """Tags list is capped at 20 items."""
        from spellbook_mcp.memory_tools import do_store_memories

        too_many_tags = [f"tag{i}" for i in range(25)]
        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Memory with too many tags",
                    "memory_type": "fact",
                    "tags": too_many_tags,
                    "citations": [],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1

        mem = get_memory(db, result["memory_ids"][0])
        meta = json.loads(mem["meta"])
        assert len(meta["tags"]) == 20
        assert meta["tags"] == [f"tag{i}" for i in range(20)]

    def test_store_marks_events_consolidated(self, db):
        """Providing event_ids_str marks those events as consolidated."""
        from spellbook_mcp.memory_tools import do_store_memories

        event_ids = self._log_events(db, count=3, project="test-project")

        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Synthesized memory from events",
                    "memory_type": "fact",
                    "tags": ["synthesis"],
                    "citations": [],
                },
            ]
        })

        event_ids_str = ",".join(str(eid) for eid in event_ids)
        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            event_ids_str=event_ids_str,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["events_consolidated"] == 3

        # Verify events are marked consolidated in DB
        conn = get_connection(db)
        for eid in event_ids:
            cursor = conn.execute(
                "SELECT consolidated, batch_id FROM raw_events WHERE id = ?", (eid,)
            )
            row = cursor.fetchone()
            assert row[0] == 1  # consolidated = 1
            assert row[1] is not None  # batch_id assigned

    def test_store_computes_bibliographic_coupling(self, db):
        """New memories get bibliographic coupling links computed."""
        from spellbook_mcp.memory_tools import do_store_memories

        # Insert an existing memory citing a file
        existing_id = insert_memory(
            db_path=db,
            content="Existing memory about auth module",
            memory_type="fact",
            namespace="test-project",
            tags=["auth"],
            citations=[{"file_path": "src/auth.py", "line_range": "1-50", "snippet": "class Auth:"}],
        )

        # Store a new memory citing the same file
        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Auth module needs refactoring",
                    "memory_type": "decision",
                    "tags": ["auth", "refactor"],
                    "citations": [{"file_path": "src/auth.py"}],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "success"
        new_id = result["memory_ids"][0]

        # Verify bibliographic link was created
        conn = get_connection(db)
        a, b = (existing_id, new_id) if existing_id < new_id else (new_id, existing_id)
        cursor = conn.execute(
            "SELECT link_type, weight FROM memory_links "
            "WHERE memory_a = ? AND memory_b = ?",
            (a, b),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "bibliographic"
        assert row[1] == 1.0  # Both cite only src/auth.py, Jaccard = 1.0

    def test_store_dedup_via_content_hash(self, db):
        """Duplicate content returns existing memory ID (dedup)."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Duplicate content test",
                    "memory_type": "fact",
                    "tags": [],
                    "citations": [],
                },
            ]
        })

        result1 = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        result2 = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )

        assert result1["status"] == "success"
        assert result2["status"] == "success"
        # Same memory ID returned due to content hash dedup
        assert result1["memory_ids"][0] == result2["memory_ids"][0]

    def test_store_with_source_meta(self, db):
        """Stored memories have extra_meta={"source": "client_llm"}."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Memory with source tracking",
                    "memory_type": "fact",
                    "tags": ["meta"],
                    "citations": [],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        mem = get_memory(db, result["memory_ids"][0])
        meta = json.loads(mem["meta"])
        assert meta["source"] == "client_llm"
        assert meta["tags"] == ["meta"]

    def test_store_whitespace_only_content_accepted(self, db):
        """Whitespace-only content passes parse_llm_response (truthy string) and is stored."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {"content": "   ", "memory_type": "fact", "tags": [], "citations": []},
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        # Whitespace-only is truthy in Python, so parse_llm_response accepts it
        assert result["status"] == "success"
        assert result["memories_created"] == 1
        assert len(result["memory_ids"]) == 1
        mem = get_memory(db, result["memory_ids"][0])
        assert mem["content"] == "   "
        assert mem["memory_type"] == "fact"

    def test_store_missing_content_field_rejected(self, db):
        """Memories missing 'content' key entirely are rejected."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {"memory_type": "fact", "tags": ["test"], "citations": []},
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "error"
        assert result["error"] == "No valid memories found. Each memory must have non-empty 'content'."

    def test_store_partial_valid_memories(self, db):
        """Mix of valid and invalid memories: only valid ones are stored."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {"memory_type": "fact", "tags": []},  # Missing content -> skipped
                {"content": "", "memory_type": "fact"},  # Empty content -> skipped
                {"content": "Valid memory here", "memory_type": "rule", "tags": ["good"]},
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1
        assert len(result["memory_ids"]) == 1
        mem = get_memory(db, result["memory_ids"][0])
        assert mem["content"] == "Valid memory here"
        assert mem["memory_type"] == "rule"


    def test_store_ignores_invalid_event_ids(self, db):
        """Non-integer event IDs in event_ids_str are silently ignored."""
        from spellbook_mcp.memory_tools import do_store_memories

        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Memory with bad event ids",
                    "memory_type": "fact",
                    "tags": [],
                    "citations": [],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            event_ids_str="abc,def,,",
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["events_consolidated"] == 0



class TestTwoToolPatternEndToEnd:
    """Test the full get_unconsolidated -> parse -> store_memories flow."""

    def _log_events(self, db, count=3, project="test-project"):
        """Helper to log raw events and return their IDs."""
        event_ids = []
        for i in range(count):
            eid = log_raw_event(
                db_path=db,
                session_id="sess-1",
                project=project,
                event_type="tool_use",
                tool_name="Read",
                subject=f"src/file{i}.py",
                summary=f"Read file{i}.py ({i * 10 + 5} lines)",
                tags="python,read",
            )
            event_ids.append(eid)
        return event_ids

    def test_full_flow_get_parse_store(self, db):
        """Full two-tool pattern: get events, construct memories, store them."""
        from spellbook_mcp.memory_tools import (
            do_get_unconsolidated,
            do_store_memories,
            MEMORY_STORE_SCHEMA,
        )

        # Step 1: Log some raw events
        event_ids = self._log_events(db, count=3, project="test-project")

        # Step 2: Get unconsolidated events (simulates client calling memory_get_unconsolidated)
        get_result = do_get_unconsolidated(db_path=db, namespace="test-project")
        assert get_result["count"] == 3
        assert len(get_result["events"]) == 3
        assert get_result["consolidation_prompt"] != ""
        assert get_result["response_schema"] == json.dumps(MEMORY_STORE_SCHEMA)

        # Step 3: Client "synthesizes" memories from the events (simulating LLM output)
        # In real usage, the client LLM would parse the prompt and produce this JSON
        synthesized_memories = json.dumps({
            "memories": [
                {
                    "content": "Project reads file0.py, file1.py, and file2.py as part of initial codebase exploration",
                    "memory_type": "fact",
                    "tags": ["python", "exploration", "read"],
                    "citations": [
                        {"file_path": "src/file0.py"},
                        {"file_path": "src/file1.py"},
                        {"file_path": "src/file2.py"},
                    ],
                },
            ]
        })

        # Step 4: Store the synthesized memories and mark events consolidated
        event_ids_str = ",".join(str(eid) for eid in event_ids)
        store_result = do_store_memories(
            db_path=db,
            memories_json=synthesized_memories,
            event_ids_str=event_ids_str,
            namespace="test-project",
        )
        assert store_result["status"] == "success"
        assert store_result["memories_created"] == 1
        assert store_result["events_consolidated"] == 3
        assert len(store_result["memory_ids"]) == 1

        # Step 5: Verify events are now consolidated
        get_result_after = do_get_unconsolidated(db_path=db, namespace="test-project")
        assert get_result_after["count"] == 0
        assert get_result_after["events"] == []
        assert get_result_after["consolidation_prompt"] == ""

        # Step 6: Verify the stored memory has correct content and meta
        mem = get_memory(db, store_result["memory_ids"][0])
        assert mem["content"] == (
            "Project reads file0.py, file1.py, and file2.py as part of initial codebase exploration"
        )
        assert mem["memory_type"] == "fact"
        assert mem["namespace"] == "test-project"
        meta = json.loads(mem["meta"])
        assert meta["source"] == "client_llm"
        assert meta["tags"] == ["python", "exploration", "read"]

        # Step 7: Verify citations were stored
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT file_path FROM memory_citations WHERE memory_id = ? ORDER BY file_path",
            (store_result["memory_ids"][0],),
        )
        citation_paths = [row[0] for row in cursor.fetchall()]
        assert citation_paths == ["src/file0.py", "src/file1.py", "src/file2.py"]

        # Step 8: Verify events are marked with batch_id in DB
        for eid in event_ids:
            cursor = conn.execute(
                "SELECT consolidated, batch_id FROM raw_events WHERE id = ?", (eid,)
            )
            row = cursor.fetchone()
            assert row[0] == 1
            assert row[1] is not None

    def test_get_then_store_with_include_consolidated(self, db):
        """After storing, include_consolidated=True still shows recently consolidated events."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated, do_store_memories

        # Log and consolidate via store
        event_ids = self._log_events(db, count=2, project="test-project")
        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Consolidated memory from first batch",
                    "memory_type": "fact",
                    "tags": ["batch1"],
                    "citations": [],
                },
            ]
        })
        do_store_memories(
            db_path=db,
            memories_json=memories_json,
            event_ids_str=",".join(str(eid) for eid in event_ids),
            namespace="test-project",
        )

        # Log new unconsolidated events
        new_ids = self._log_events(db, count=1, project="test-project")

        # Without include_consolidated, only new events
        result_without = do_get_unconsolidated(db_path=db, namespace="test-project")
        assert result_without["count"] == 1
        assert result_without["events"][0]["id"] == new_ids[0]

        # With include_consolidated, should get both new and recently consolidated
        result_with = do_get_unconsolidated(
            db_path=db, namespace="test-project", include_consolidated=True,
        )
        returned_ids = {e["id"] for e in result_with["events"]}
        assert new_ids[0] in returned_ids
        for eid in event_ids:
            assert eid in returned_ids
        assert result_with["count"] == 3

    def test_store_multiple_memories_from_single_batch(self, db):
        """Client produces multiple memories from a single get_unconsolidated call."""
        from spellbook_mcp.memory_tools import do_get_unconsolidated, do_store_memories

        event_ids = self._log_events(db, count=4, project="test-project")

        # Client produces 2 memories from 4 events
        memories_json = json.dumps({
            "memories": [
                {
                    "content": "Files 0 and 1 are related to data processing",
                    "memory_type": "fact",
                    "tags": ["data"],
                    "citations": [{"file_path": "src/file0.py"}, {"file_path": "src/file1.py"}],
                },
                {
                    "content": "Files 2 and 3 handle API endpoints",
                    "memory_type": "fact",
                    "tags": ["api"],
                    "citations": [{"file_path": "src/file2.py"}, {"file_path": "src/file3.py"}],
                },
            ]
        })

        result = do_store_memories(
            db_path=db,
            memories_json=memories_json,
            event_ids_str=",".join(str(eid) for eid in event_ids),
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 2
        assert result["events_consolidated"] == 4
        assert len(result["memory_ids"]) == 2

        # Verify both memories are retrievable
        mem1 = get_memory(db, result["memory_ids"][0])
        assert mem1["content"] == "Files 0 and 1 are related to data processing"
        mem2 = get_memory(db, result["memory_ids"][1])
        assert mem2["content"] == "Files 2 and 3 handle API endpoints"

        # No unconsolidated events remain
        remaining = do_get_unconsolidated(db_path=db, namespace="test-project")
        assert remaining["count"] == 0


class TestMemoryToolsServerRegistration:
    """Test that memory_get_unconsolidated and memory_store_memories are registered as MCP tools in server.py."""

    def test_memory_consolidate_docstring_updated(self):
        """memory_consolidate docstring references heuristic strategies, not LLM."""
        from spellbook_mcp import server

        docstring = server.memory_consolidate.fn.__doc__
        assert "heuristic strategies" in docstring, (
            "memory_consolidate docstring should reference 'heuristic strategies'"
        )
        assert "LLM" not in docstring, (
            "memory_consolidate docstring should not reference 'LLM'"
        )

    def test_memory_get_unconsolidated_is_registered(self):
        """memory_get_unconsolidated is registered as a tool on the server module."""
        from spellbook_mcp import server

        assert hasattr(server, "memory_get_unconsolidated"), (
            "memory_get_unconsolidated not found on server module"
        )
        assert callable(server.memory_get_unconsolidated.fn), (
            "memory_get_unconsolidated.fn is not callable"
        )

    def test_memory_store_memories_is_registered(self):
        """memory_store_memories is registered as a tool on the server module."""
        from spellbook_mcp import server

        assert hasattr(server, "memory_store_memories"), (
            "memory_store_memories not found on server module"
        )
        assert callable(server.memory_store_memories.fn), (
            "memory_store_memories.fn is not callable"
        )

    def test_server_imports_do_get_unconsolidated(self):
        """do_get_unconsolidated is imported in server module."""
        from spellbook_mcp import server

        assert hasattr(server, "do_get_unconsolidated"), (
            "do_get_unconsolidated not imported in server"
        )

    def test_server_imports_do_store_memories(self):
        """do_store_memories is imported in server module."""
        from spellbook_mcp import server

        assert hasattr(server, "do_store_memories"), (
            "do_store_memories not imported in server"
        )

    @pytest.mark.asyncio
    async def test_memory_get_unconsolidated_delegates_to_do_function(self, db):
        """memory_get_unconsolidated delegates to do_get_unconsolidated with correct args."""
        from spellbook_mcp import server
        from spellbook_mcp.memory_tools import MEMORY_STORE_SCHEMA
        from unittest.mock import patch

        mock_ctx = MagicMock()
        mock_ctx.list_roots = AsyncMock(return_value=[])

        with patch.object(server, "get_db_path", return_value=db), \
             patch.object(server, "get_project_path_from_context", new_callable=AsyncMock, return_value=None) as mock_get_path, \
             patch.object(server, "do_get_unconsolidated") as mock_do:
            mock_do.return_value = {
                "events": [],
                "count": 0,
                "consolidation_prompt": "",
                "response_schema": json.dumps(MEMORY_STORE_SCHEMA),
            }
            # With explicit namespace, should NOT call get_project_path_from_context
            result = await server.memory_get_unconsolidated.fn(
                ctx=mock_ctx,
                namespace="test-ns",
                limit=25,
                include_consolidated=True,
            )

            mock_do.assert_called_once_with(
                db_path=db,
                namespace="test-ns",
                limit=25,
                include_consolidated=True,
            )
            assert result == {
                "events": [],
                "count": 0,
                "consolidation_prompt": "",
                "response_schema": json.dumps(MEMORY_STORE_SCHEMA),
            }

    @pytest.mark.asyncio
    async def test_memory_get_unconsolidated_auto_detects_namespace(self, db):
        """memory_get_unconsolidated auto-detects namespace from context when empty."""
        from spellbook_mcp import server
        from spellbook_mcp.path_utils import encode_cwd
        from unittest.mock import patch

        mock_ctx = MagicMock()

        fake_project_path = "/Users/test/myproject"
        expected_namespace = encode_cwd(fake_project_path)

        with patch.object(server, "get_db_path", return_value=db), \
             patch.object(server, "get_project_path_from_context", new_callable=AsyncMock, return_value=fake_project_path), \
             patch.object(server, "do_get_unconsolidated") as mock_do:
            mock_do.return_value = {"events": [], "count": 0, "consolidation_prompt": "", "response_schema": "{}"}

            result = await server.memory_get_unconsolidated.fn(
                ctx=mock_ctx,
                namespace="",
                limit=50,
                include_consolidated=False,
            )

            mock_do.assert_called_once_with(
                db_path=db,
                namespace=expected_namespace,
                limit=50,
                include_consolidated=False,
            )

    @pytest.mark.asyncio
    async def test_memory_get_unconsolidated_returns_error_when_no_namespace(self, db):
        """memory_get_unconsolidated returns error when namespace empty and context fails."""
        from spellbook_mcp import server
        from unittest.mock import patch

        mock_ctx = MagicMock()

        with patch.object(server, "get_db_path", return_value=db), \
             patch.object(server, "get_project_path_from_context", new_callable=AsyncMock, return_value=None):
            result = await server.memory_get_unconsolidated.fn(
                ctx=mock_ctx,
                namespace="",
                limit=50,
                include_consolidated=False,
            )

            assert result == {
                "error": "Could not determine project namespace",
                "events": [],
            }

    @pytest.mark.asyncio
    async def test_memory_store_memories_delegates_to_do_function(self, db):
        """memory_store_memories delegates to do_store_memories with correct args."""
        from spellbook_mcp import server
        from unittest.mock import patch

        mock_ctx = MagicMock()

        with patch.object(server, "get_db_path", return_value=db), \
             patch.object(server, "get_project_path_from_context", new_callable=AsyncMock, return_value=None), \
             patch.object(server, "do_store_memories") as mock_do:
            mock_do.return_value = {
                "status": "success",
                "memories_created": 1,
                "events_consolidated": 2,
                "memory_ids": ["mem-1"],
            }

            result = await server.memory_store_memories.fn(
                ctx=mock_ctx,
                memories='{"memories": [{"content": "test"}]}',
                event_ids="1,2",
                namespace="test-ns",
            )

            mock_do.assert_called_once_with(
                db_path=db,
                memories_json='{"memories": [{"content": "test"}]}',
                event_ids_str="1,2",
                namespace="test-ns",
                branch="",
            )
            assert result == {
                "status": "success",
                "memories_created": 1,
                "events_consolidated": 2,
                "memory_ids": ["mem-1"],
            }

    @pytest.mark.asyncio
    async def test_memory_store_memories_auto_detects_namespace(self, db):
        """memory_store_memories auto-detects namespace from context when empty."""
        from spellbook_mcp import server
        from spellbook_mcp.path_utils import encode_cwd
        from unittest.mock import patch

        mock_ctx = MagicMock()
        fake_project_path = "/Users/test/myproject"
        expected_namespace = encode_cwd(fake_project_path)

        with patch.object(server, "get_db_path", return_value=db), \
             patch.object(server, "get_project_path_from_context", new_callable=AsyncMock, return_value=fake_project_path), \
             patch.object(server, "get_current_branch", return_value="main"), \
             patch.object(server, "do_store_memories") as mock_do:
            mock_do.return_value = {
                "status": "success",
                "memories_created": 0,
                "events_consolidated": 0,
                "memory_ids": [],
            }

            await server.memory_store_memories.fn(
                ctx=mock_ctx,
                memories="[]",
                event_ids="",
                namespace="",
            )

            mock_do.assert_called_once_with(
                db_path=db,
                memories_json="[]",
                event_ids_str="",
                namespace=expected_namespace,
                branch="main",
            )

    @pytest.mark.asyncio
    async def test_memory_store_memories_returns_error_when_no_namespace(self, db):
        """memory_store_memories returns error when namespace empty and context fails."""
        from spellbook_mcp import server
        from unittest.mock import patch

        mock_ctx = MagicMock()

        with patch.object(server, "get_db_path", return_value=db), \
             patch.object(server, "get_project_path_from_context", new_callable=AsyncMock, return_value=None):
            result = await server.memory_store_memories.fn(
                ctx=mock_ctx,
                memories='{"memories": []}',
                event_ids="",
                namespace="",
            )

            assert result == {
                "error": "Could not determine project namespace",
            }
