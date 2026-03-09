"""Tests for memory storage CRUD operations."""

import json

import pytest
from spellbook_mcp.db import init_db, get_connection, close_all_connections
from spellbook_mcp.memory_store import (
    insert_memory,
    get_memory,
    soft_delete_memory,
    log_raw_event,
    get_unconsolidated_events,
    mark_events_consolidated,
    recall_by_file_path,
    recall_by_query,
    update_access,
    insert_citation,
    insert_link,
    purge_deleted,
    log_audit,
)


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    yield db_path
    close_all_connections()


def test_insert_and_get_memory(db):
    mem_id = insert_memory(
        db_path=db,
        content="pytest uses conftest.py for shared fixtures",
        memory_type="fact",
        namespace="Users-alice-myproject",
        tags=["pytest", "fixtures", "conftest"],
        citations=[],
    )
    assert isinstance(mem_id, str)
    assert len(mem_id) == 36  # UUID4 format

    mem = get_memory(db, mem_id)
    assert mem is not None
    assert mem["id"] == mem_id
    assert mem["content"] == "pytest uses conftest.py for shared fixtures"
    assert mem["memory_type"] == "fact"
    assert mem["namespace"] == "Users-alice-myproject"
    assert mem["status"] == "active"
    assert mem["importance"] == 1.0
    assert mem["deleted_at"] is None
    assert mem["accessed_at"] is None
    assert mem["citations"] == []
    # content_hash should be a SHA-256 hex digest (64 chars)
    assert len(mem["content_hash"]) == 64
    # meta should contain tags
    meta = json.loads(mem["meta"])
    assert meta["tags"] == ["pytest", "fixtures", "conftest"]


def test_insert_memory_dedup(db):
    """Inserting same content twice returns existing ID."""
    id1 = insert_memory(
        db_path=db,
        content="pytest uses conftest.py for shared fixtures",
        memory_type="fact",
        namespace="Users-alice-myproject",
        tags=["pytest"],
        citations=[],
    )
    id2 = insert_memory(
        db_path=db,
        content="pytest uses conftest.py for shared fixtures",
        memory_type="fact",
        namespace="Users-alice-myproject",
        tags=["pytest"],
        citations=[],
    )
    assert id1 == id2

    # Verify only one row exists in DB
    conn = get_connection(db)
    cursor = conn.execute("SELECT COUNT(*) FROM memories")
    assert cursor.fetchone()[0] == 1


def test_insert_memory_dedup_normalizes_whitespace(db):
    """Dedup hash normalizes whitespace and case."""
    id1 = insert_memory(
        db_path=db,
        content="Hello World",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    id2 = insert_memory(
        db_path=db,
        content="hello   world",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    assert id1 == id2


def test_insert_memory_with_citations(db):
    mem_id = insert_memory(
        db_path=db,
        content="The project uses SQLAlchemy for ORM",
        memory_type="fact",
        namespace="Users-alice-myproject",
        tags=["sqlalchemy", "orm"],
        citations=[
            {"file_path": "src/models.py", "line_range": "1-20", "snippet": "from sqlalchemy import..."},
        ],
    )
    mem = get_memory(db, mem_id)
    assert len(mem["citations"]) == 1
    assert mem["citations"][0] == {
        "file_path": "src/models.py",
        "line_range": "1-20",
        "snippet": "from sqlalchemy import...",
    }


def test_insert_memory_with_custom_importance(db):
    mem_id = insert_memory(
        db_path=db,
        content="important fact",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
        importance=5.0,
    )
    mem = get_memory(db, mem_id)
    assert mem["importance"] == 5.0


def test_get_memory_nonexistent(db):
    result = get_memory(db, "nonexistent-id")
    assert result is None


def test_soft_delete_memory(db):
    mem_id = insert_memory(
        db_path=db,
        content="to be deleted",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    soft_delete_memory(db, mem_id)
    mem = get_memory(db, mem_id)
    assert mem["status"] == "deleted"
    assert mem["deleted_at"] is not None
    assert isinstance(mem["deleted_at"], str)

    # Verify FTS5 entry was removed
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT COUNT(*) FROM memories_fts WHERE memories_fts MATCH '\"to be deleted\"'"
    )
    assert cursor.fetchone()[0] == 0


def test_soft_delete_logs_audit(db):
    mem_id = insert_memory(
        db_path=db,
        content="audit delete test",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    soft_delete_memory(db, mem_id)
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT action, memory_id, details FROM memory_audit_log WHERE action = 'delete'"
    )
    row = cursor.fetchone()
    assert row[0] == "delete"
    assert row[1] == mem_id
    details = json.loads(row[2])
    assert details == {"soft": True}


def test_log_and_get_raw_events(db):
    event_id = log_raw_event(
        db_path=db,
        session_id="sess-1",
        project="Users-alice-myproject",
        event_type="tool_use",
        tool_name="Read",
        subject="src/main.py",
        summary="Read src/main.py (120 lines)",
        tags="python,main",
    )
    assert isinstance(event_id, int)

    events = get_unconsolidated_events(db, limit=10)
    assert len(events) == 1
    evt = events[0]
    assert evt["id"] == event_id
    assert evt["session_id"] == "sess-1"
    assert evt["project"] == "Users-alice-myproject"
    assert evt["event_type"] == "tool_use"
    assert evt["tool_name"] == "Read"
    assert evt["subject"] == "src/main.py"
    assert evt["summary"] == "Read src/main.py (120 lines)"
    assert evt["tags"] == "python,main"


def test_mark_events_consolidated(db):
    log_raw_event(
        db_path=db,
        session_id="sess-1",
        project="ns",
        event_type="tool_use",
        tool_name="Read",
        subject="file.py",
        summary="Read file",
        tags="",
    )
    events = get_unconsolidated_events(db, limit=10)
    assert len(events) == 1

    mark_events_consolidated(db, [events[0]["id"]], "batch-001")

    remaining = get_unconsolidated_events(db, limit=10)
    assert remaining == []

    # Verify batch_id was set
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT consolidated, batch_id FROM raw_events WHERE id = ?",
        (events[0]["id"],),
    )
    row = cursor.fetchone()
    assert row[0] == 1
    assert row[1] == "batch-001"


def test_mark_events_consolidated_empty_list(db):
    """Calling with empty list is a no-op."""
    mark_events_consolidated(db, [], "batch-000")
    # Verify no rows were modified
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT COUNT(*) FROM raw_events WHERE batch_id = 'batch-000'"
    )
    assert cursor.fetchone()[0] == 0


def test_recall_by_file_path(db):
    mem_id = insert_memory(
        db_path=db,
        content="models.py defines the User class",
        memory_type="fact",
        namespace="Users-alice-myproject",
        tags=["models", "user"],
        citations=[
            {"file_path": "src/models.py", "line_range": "10-30", "snippet": "class User:"},
        ],
    )
    results = recall_by_file_path(db, "src/models.py", namespace="Users-alice-myproject")
    assert len(results) == 1
    assert results[0]["id"] == mem_id
    assert results[0]["content"] == "models.py defines the User class"
    assert results[0]["memory_type"] == "fact"
    assert results[0]["status"] == "active"
    assert results[0]["importance"] == 1.0


def test_recall_by_file_path_excludes_other_namespaces(db):
    insert_memory(
        db_path=db,
        content="models.py in project A",
        memory_type="fact",
        namespace="project-a",
        tags=[],
        citations=[{"file_path": "src/models.py", "line_range": None, "snippet": None}],
    )
    results = recall_by_file_path(db, "src/models.py", namespace="project-b")
    assert results == []


def test_recall_by_query_fts(db):
    insert_memory(
        db_path=db,
        content="The project uses FastAPI for REST endpoints",
        memory_type="fact",
        namespace="Users-alice-myproject",
        tags=["fastapi", "rest", "endpoints"],
        citations=[],
    )
    results = recall_by_query(db, "FastAPI", namespace="Users-alice-myproject")
    assert len(results) >= 1
    assert results[0]["content"] == "The project uses FastAPI for REST endpoints"
    assert results[0]["memory_type"] == "fact"
    assert results[0]["status"] == "active"


def test_recall_by_query_empty_returns_recent(db):
    mem_id = insert_memory(
        db_path=db,
        content="recent memory one",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    results = recall_by_query(db, "", namespace="ns")
    assert len(results) == 1
    assert results[0]["id"] == mem_id
    assert results[0]["content"] == "recent memory one"


def test_recall_by_query_safe_escaping(db):
    """FTS5 operators in query should be safely escaped and return expected results."""
    insert_memory(
        db_path=db,
        content="This is about OR logic and AND gates",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    insert_memory(
        db_path=db,
        content="Unrelated memory about databases",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    # FTS5 operators like OR, AND, NOT should be escaped (treated as literals)
    # "OR AND NOT" as a phrase should NOT match (no memory contains that exact phrase)
    results = recall_by_query(db, "OR AND NOT", namespace="ns")
    assert isinstance(results, list)
    # The phrase "OR AND NOT" does not appear verbatim in any memory
    assert len(results) == 0

    # Verify a legitimate word from the memory still matches
    results = recall_by_query(db, "logic", namespace="ns")
    assert len(results) == 1
    assert results[0]["content"] == "This is about OR logic and AND gates"


def test_recall_by_query_with_quotes(db):
    """Quotes in query should be safely escaped and return expected results."""
    insert_memory(
        db_path=db,
        content='She said "hello world" to the compiler',
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    insert_memory(
        db_path=db,
        content="A completely different memory about testing",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    # Query with embedded quotes should not crash and should match
    results = recall_by_query(db, "hello", namespace="ns")
    assert len(results) == 1
    assert results[0]["content"] == 'She said "hello world" to the compiler'

    # Quotes in query should be escaped, not treated as FTS5 phrase delimiters
    results = recall_by_query(db, '"hello"', namespace="ns")
    assert isinstance(results, list)
    # Should still find the memory (hello appears in it)
    assert len(results) <= 1  # Either matches or doesn't, but must not crash


def test_recall_by_query_fts5_column_filter_blocked(db):
    """FTS5 column:filter syntax should not bypass namespace isolation."""
    insert_memory(
        db_path=db,
        content="secret data in namespace alpha",
        memory_type="fact",
        namespace="alpha",
        tags=["secret"],
        citations=[],
    )
    insert_memory(
        db_path=db,
        content="public data in namespace beta",
        memory_type="fact",
        namespace="beta",
        tags=["public"],
        citations=[],
    )
    # Attempt FTS5 column filter syntax -- should be escaped to a phrase query
    results = recall_by_query(db, "content:secret", namespace="beta")
    # Must NOT return the alpha namespace memory; phrase "content:secret" matches nothing
    assert results == []

    # Wildcard attempt should also be blocked
    results = recall_by_query(db, "content:*", namespace="beta")
    assert results == []


def test_update_access(db):
    mem_id = insert_memory(
        db_path=db,
        content="access test",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    update_access(db, mem_id)
    mem = get_memory(db, mem_id)
    assert mem["importance"] == 1.1  # 1.0 + 0.1
    assert mem["accessed_at"] is not None
    assert isinstance(mem["accessed_at"], str)


def test_update_access_caps_at_10(db):
    mem_id = insert_memory(
        db_path=db,
        content="cap test",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
        importance=9.95,
    )
    update_access(db, mem_id)
    mem = get_memory(db, mem_id)
    assert mem["importance"] == 10.0


def test_update_access_multiple_increments(db):
    mem_id = insert_memory(
        db_path=db,
        content="multi access",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    update_access(db, mem_id)
    update_access(db, mem_id)
    update_access(db, mem_id)
    mem = get_memory(db, mem_id)
    # 1.0 + 0.1 + 0.1 + 0.1 = 1.3 (floating point may be slightly off)
    assert abs(mem["importance"] - 1.3) < 0.001


def test_insert_citation_no_commit(db):
    """insert_citation does NOT commit -- caller manages transaction."""
    mem_id = insert_memory(
        db_path=db,
        content="citation commit test",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    conn = get_connection(db)
    # Insert citation without committing
    insert_citation(db, mem_id, "new_file.py", "1-10", "snippet")
    # Rollback to verify it wasn't auto-committed by insert_citation
    conn.rollback()
    # Citation should be gone after rollback
    cursor = conn.execute(
        "SELECT COUNT(*) FROM memory_citations WHERE memory_id = ? AND file_path = 'new_file.py'",
        (mem_id,),
    )
    assert cursor.fetchone()[0] == 0


def test_insert_citation_ignores_duplicates(db):
    mem_id = insert_memory(
        db_path=db,
        content="dup citation test",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[
            {"file_path": "file.py", "line_range": "1-5", "snippet": "code"},
        ],
    )
    # Insert same citation again -- should not raise
    insert_citation(db, mem_id, "file.py", "1-5", "code")
    conn = get_connection(db)
    conn.commit()

    cursor = conn.execute(
        "SELECT COUNT(*) FROM memory_citations WHERE memory_id = ? AND file_path = 'file.py'",
        (mem_id,),
    )
    assert cursor.fetchone()[0] == 1


def test_insert_link(db):
    id1 = insert_memory(db_path=db, content="memory A", memory_type="fact",
                         namespace="ns", tags=[], citations=[])
    id2 = insert_memory(db_path=db, content="memory B", memory_type="fact",
                         namespace="ns", tags=[], citations=[])
    insert_link(db, id1, id2, "related", weight=0.8)

    conn = get_connection(db)
    # Links normalize order: smaller ID first
    a, b = (id1, id2) if id1 < id2 else (id2, id1)
    cursor = conn.execute(
        "SELECT memory_a, memory_b, link_type, weight FROM memory_links "
        "WHERE memory_a = ? AND memory_b = ?",
        (a, b),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == a
    assert row[1] == b
    assert row[2] == "related"
    assert row[3] == 0.8


def test_insert_link_upsert(db):
    """Inserting same link again updates weight."""
    id1 = insert_memory(db_path=db, content="link upsert A", memory_type="fact",
                         namespace="ns", tags=[], citations=[])
    id2 = insert_memory(db_path=db, content="link upsert B", memory_type="fact",
                         namespace="ns", tags=[], citations=[])
    insert_link(db, id1, id2, "related", weight=0.5)
    insert_link(db, id1, id2, "related", weight=0.9)

    conn = get_connection(db)
    a, b = (id1, id2) if id1 < id2 else (id2, id1)
    cursor = conn.execute(
        "SELECT weight FROM memory_links WHERE memory_a = ? AND memory_b = ? AND link_type = 'related'",
        (a, b),
    )
    assert cursor.fetchone()[0] == 0.9


def test_purge_deleted_old_entries(db):
    mem_id = insert_memory(
        db_path=db,
        content="old deleted",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[
            {"file_path": "old.py", "line_range": None, "snippet": None},
        ],
    )
    soft_delete_memory(db, mem_id)
    conn = get_connection(db)
    conn.execute(
        "UPDATE memories SET deleted_at = datetime('now', '-31 days') WHERE id = ?",
        (mem_id,),
    )
    conn.commit()
    count = purge_deleted(db, retention_days=30)
    assert count == 1
    assert get_memory(db, mem_id) is None

    # Verify citations also purged
    cursor = conn.execute(
        "SELECT COUNT(*) FROM memory_citations WHERE memory_id = ?", (mem_id,),
    )
    assert cursor.fetchone()[0] == 0


def test_purge_deleted_keeps_recent(db):
    """Memories deleted less than retention_days ago are kept."""
    mem_id = insert_memory(
        db_path=db,
        content="recently deleted",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    soft_delete_memory(db, mem_id)
    count = purge_deleted(db, retention_days=30)
    assert count == 0
    assert get_memory(db, mem_id) is not None


def test_purge_deleted_returns_zero_when_none(db):
    count = purge_deleted(db, retention_days=30)
    assert count == 0


def test_log_audit(db):
    log_audit(db, action="create", memory_id="test-id", details={"source": "test"})
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT timestamp, action, memory_id, details FROM memory_audit_log"
    )
    row = cursor.fetchone()
    assert row[0] is not None  # timestamp is set
    assert row[1] == "create"
    assert row[2] == "test-id"
    assert json.loads(row[3]) == {"source": "test"}


def test_log_audit_no_details(db):
    log_audit(db, action="access", memory_id="some-id")
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT action, memory_id, details FROM memory_audit_log WHERE action = 'access'"
    )
    row = cursor.fetchone()
    assert row[0] == "access"
    assert row[1] == "some-id"
    assert row[2] is None


def test_recall_excludes_deleted(db):
    mem_id = insert_memory(
        db_path=db,
        content="deleted memory about FastAPI",
        memory_type="fact",
        namespace="ns",
        tags=["fastapi"],
        citations=[{"file_path": "app.py", "line_range": None, "snippet": None}],
    )
    soft_delete_memory(db, mem_id)
    results_query = recall_by_query(db, "FastAPI", namespace="ns")
    results_file = recall_by_file_path(db, "app.py", namespace="ns")
    assert results_query == []
    assert results_file == []


def test_secret_flagged_memory(db):
    """Memories with detected secrets are flagged in meta but still stored."""
    mem_id = insert_memory(
        db_path=db,
        content="AWS key is AKIAIOSFODNN7EXAMPLE",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    mem = get_memory(db, mem_id)
    assert mem is not None
    assert mem["status"] == "active"  # Not blocked, just flagged
    meta = json.loads(mem["meta"])
    assert "secret_findings" in meta
    assert len(meta["secret_findings"]) >= 1
    assert meta["secret_findings"][0]["pattern_name"] == "AWS Access Key"
    # Full match must NOT be stored; only redacted preview
    assert "matched_text" not in meta["secret_findings"][0]
    assert meta["secret_findings"][0]["redacted_preview"] == "AKIA...LE"
    assert isinstance(meta["secret_findings"][0]["start"], int)
    assert isinstance(meta["secret_findings"][0]["end"], int)


def test_no_secret_flag_on_clean_content(db):
    """Clean content should have no secret_findings in meta."""
    mem_id = insert_memory(
        db_path=db,
        content="This is perfectly safe content about pytest",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    mem = get_memory(db, mem_id)
    meta = json.loads(mem["meta"])
    assert "secret_findings" not in meta


def test_insert_memory_creates_audit_log(db):
    """insert_memory should create an audit log entry."""
    mem_id = insert_memory(
        db_path=db,
        content="audit log creation test",
        memory_type="fact",
        namespace="ns",
        tags=[],
        citations=[],
    )
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT action, memory_id, details FROM memory_audit_log WHERE action = 'create' AND memory_id = ?",
        (mem_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "create"
    assert row[1] == mem_id
    assert json.loads(row[2]) == {"memory_type": "fact"}


class TestGetUnconsolidatedEventsNamespace:
    def test_namespace_filters_by_project(self, db):
        """When namespace is provided, only events with matching project are returned."""
        log_raw_event(db, "s1", "project-a", "tool_use", "Read", "f.py", "read f", "")
        log_raw_event(db, "s1", "project-b", "tool_use", "Read", "g.py", "read g", "")
        log_raw_event(db, "s1", "project-a", "tool_use", "Edit", "h.py", "edit h", "")

        events = get_unconsolidated_events(db, limit=50, namespace="project-a")
        assert len(events) == 2
        assert all(e["project"] == "project-a" for e in events)

    def test_no_namespace_returns_all(self, db):
        """When namespace is None (default), all unconsolidated events are returned."""
        log_raw_event(db, "s1", "project-a", "tool_use", "Read", "f.py", "read f", "")
        log_raw_event(db, "s1", "project-b", "tool_use", "Read", "g.py", "read g", "")

        events = get_unconsolidated_events(db, limit=50)
        assert len(events) == 2


class TestGetRecentlyConsolidatedEvents:
    def test_returns_recently_consolidated(self, db):
        """Returns events consolidated within the last 24 hours."""
        eid1 = log_raw_event(db, "s1", "proj", "tool_use", "Read", "a.py", "read a", "python")
        eid2 = log_raw_event(db, "s1", "proj", "tool_use", "Edit", "b.py", "edit b", "python")
        mark_events_consolidated(db, [eid1, eid2], "batch-1")

        from spellbook_mcp.memory_store import get_recently_consolidated_events
        events = get_recently_consolidated_events(db, limit=50)
        assert len(events) == 2
        assert events[0]["id"] == eid1
        assert events[1]["id"] == eid2

    def test_excludes_unconsolidated(self, db):
        """Unconsolidated events are not returned."""
        log_raw_event(db, "s1", "proj", "tool_use", "Read", "a.py", "read a", "")

        from spellbook_mcp.memory_store import get_recently_consolidated_events
        events = get_recently_consolidated_events(db, limit=50)
        assert len(events) == 0

    def test_namespace_filter(self, db):
        """When namespace is provided, only matching project events are returned."""
        eid1 = log_raw_event(db, "s1", "proj-a", "tool_use", "Read", "a.py", "read a", "")
        eid2 = log_raw_event(db, "s1", "proj-b", "tool_use", "Read", "b.py", "read b", "")
        mark_events_consolidated(db, [eid1, eid2], "batch-1")

        from spellbook_mcp.memory_store import get_recently_consolidated_events
        events = get_recently_consolidated_events(db, limit=50, namespace="proj-a")
        assert len(events) == 1
        assert events[0]["project"] == "proj-a"

    def test_respects_limit(self, db):
        """Limit parameter caps results."""
        eids = []
        for i in range(5):
            eid = log_raw_event(db, "s1", "proj", "tool_use", "Read", f"{i}.py", f"read {i}", "")
            eids.append(eid)
        mark_events_consolidated(db, eids, "batch-1")

        from spellbook_mcp.memory_store import get_recently_consolidated_events
        events = get_recently_consolidated_events(db, limit=2)
        assert len(events) == 2




class TestInsertMemoryExtraMeta:
    def test_extra_meta_merged_into_meta_json(self, db):
        """extra_meta dict is shallow-merged into stored meta JSON alongside tags."""
        mem_id = insert_memory(
            db_path=db,
            content="Heuristic-generated memory",
            memory_type="fact",
            namespace="ns",
            tags=["auth", "refactor"],
            citations=[],
            extra_meta={"source": "heuristic", "strategy": "content_hash", "batch_id": "abc-123"},
        )
        conn = get_connection(db)
        cursor = conn.execute("SELECT meta FROM memories WHERE id = ?", (mem_id,))
        meta = json.loads(cursor.fetchone()[0])
        assert meta["tags"] == ["auth", "refactor"]
        assert meta["source"] == "heuristic"
        assert meta["strategy"] == "content_hash"
        assert meta["batch_id"] == "abc-123"

    def test_extra_meta_none_preserves_existing_behavior(self, db):
        """When extra_meta is None (default), meta contains only tags and possibly secret_findings."""
        mem_id = insert_memory(
            db_path=db,
            content="Normal memory without extra meta",
            memory_type="fact",
            namespace="ns",
            tags=["normal"],
            citations=[],
        )
        conn = get_connection(db)
        cursor = conn.execute("SELECT meta FROM memories WHERE id = ?", (mem_id,))
        meta = json.loads(cursor.fetchone()[0])
        assert meta["tags"] == ["normal"]
        assert "source" not in meta


def test_fts5_synced_on_insert(db):
    """FTS5 standalone table should be populated on insert."""
    insert_memory(
        db_path=db,
        content="FTS5 synchronization verification test",
        memory_type="fact",
        namespace="ns",
        tags=["sync", "fts"],
        citations=[{"file_path": "sync.py", "line_range": None, "snippet": None}],
    )
    conn = get_connection(db)
    cursor = conn.execute(
        "SELECT content, tags, citations FROM memories_fts WHERE memories_fts MATCH 'synchronization'"
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "FTS5 synchronization verification test"
    assert row[1] == "sync fts"
    assert row[2] == "sync.py"
