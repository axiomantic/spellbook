"""Tests for /api/memory/bridge-content REST endpoint.

Tests the endpoint handler that receives auto-memory content from the bridge
hook, stores dual events (brief-summary for consolidation + full-content for
audit), and triggers consolidation when the threshold is met.
"""

import pytest
import tripwire

from spellbook.core.db import init_db, close_all_connections
from spellbook.memory.store import (
    get_unconsolidated_events,
    log_raw_event,
    mark_events_consolidated,
)
from spellbook.memory.tools import do_log_event
from spellbook.memory.consolidation import should_consolidate, EVENT_THRESHOLD


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


class TestBridgeContentDBLogic:
    """Tests for the DB-level operations the endpoint performs."""

    def test_brief_summary_event_stored_unconsolidated(self, db):
        """Brief-summary event (auto_memory_bridge) stays unconsolidated for pipeline."""
        result = do_log_event(
            db_path=db,
            session_id="sess-123",
            project="Users-alice-project",
            tool_name="auto_memory_bridge",
            subject="/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md",
            summary="MEMORY.md updated: 47 lines, sections: Key Architecture, Conventions",
            tags="auto-memory,bridge,memory",
            event_type="auto_memory_bridge",
            branch="main",
        )
        assert result == {"status": "logged", "event_id": result["event_id"]}
        assert result["event_id"] > 0

        events = get_unconsolidated_events(db, limit=10)
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "auto_memory_bridge"
        assert event["tool_name"] == "auto_memory_bridge"
        assert event["summary"] == "MEMORY.md updated: 47 lines, sections: Key Architecture, Conventions"
        assert event["project"] == "Users-alice-project"
        assert event["branch"] == "main"

    def test_full_content_event_excluded_from_consolidation(self, db):
        """Full-content event marked consolidated=1 immediately, skips pipeline."""
        event_id = log_raw_event(
            db_path=db,
            session_id="sess-123",
            project="Users-alice-project",
            event_type="auto_memory_content",
            tool_name="auto_memory_bridge",
            subject="/path/MEMORY.md",
            summary="# Full content here\n- fact 1\n- fact 2",
            tags="auto-memory,content,memory",
            branch="main",
        )
        mark_events_consolidated(db, [event_id], "bridge-immediate")

        events = get_unconsolidated_events(db, limit=10)
        unconsolidated_ids = [e["id"] for e in events]
        assert event_id not in unconsolidated_ids

    def test_consolidation_threshold_triggers(self, db):
        """should_consolidate returns True when EVENT_THRESHOLD events exist."""
        for i in range(EVENT_THRESHOLD):
            do_log_event(
                db_path=db,
                session_id="sess-123",
                project="Users-alice-project",
                tool_name="auto_memory_bridge",
                subject=f"/path/file_{i}.md",
                summary=f"event {i}",
                tags="auto-memory,bridge",
                event_type="auto_memory_bridge",
                branch="main",
            )
        assert should_consolidate(db) is True

    def test_below_threshold_no_consolidation(self, db):
        """should_consolidate returns False below threshold."""
        do_log_event(
            db_path=db,
            session_id="sess-123",
            project="Users-alice-project",
            tool_name="auto_memory_bridge",
            subject="/path/file.md",
            summary="single event",
            tags="auto-memory,bridge",
            event_type="auto_memory_bridge",
            branch="main",
        )
        assert should_consolidate(db) is False


class TestBridgeContentEndpointHTTP:
    """Tests exercising the actual HTTP endpoint via Starlette TestClient."""

    @pytest.fixture
    def client(self, db, monkeypatch):
        """Create a TestClient wired to the endpoint with a test DB."""
        from starlette.testclient import TestClient
        from spellbook.mcp import server
        import spellbook.mcp.routes as routes_mod

        monkeypatch.setattr(routes_mod, "get_db_path", lambda: db)
        app = server.mcp.http_app(transport="http")
        yield TestClient(app, raise_server_exceptions=False)

    def test_rejects_missing_content(self, client):
        """POST without content field returns 400 with error listing missing field."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={"session_id": "s1", "project": "p1"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "content" in body["error"]

    def test_rejects_missing_session_id(self, client):
        """POST without session_id returns 400."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={"project": "p1", "content": "hello"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "session_id" in body["error"]

    def test_rejects_missing_project(self, client):
        """POST without project returns 400."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={"session_id": "s1", "content": "hello"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "project" in body["error"]

    def test_rejects_empty_content(self, client):
        """POST with empty string content returns 400."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={"session_id": "s1", "project": "p1", "content": ""},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "content" in body["error"]

    def test_stores_dual_events(self, client, db):
        """Valid POST stores both brief-summary and full-content events."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "file_path": "/path/MEMORY.md",
                "filename": "MEMORY.md",
                "content": "# Facts\n- Python 3.10\n- Uses FastAPI",
                "is_primary": True,
                "branch": "main",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "captured"
        assert data["event_id"] > 0
        assert isinstance(data["consolidated"], bool)

        # Brief-summary event is unconsolidated (flows through pipeline)
        unconsolidated = get_unconsolidated_events(db, limit=10)
        bridge_events = [e for e in unconsolidated if e["event_type"] == "auto_memory_bridge"]
        assert len(bridge_events) == 1
        summary = bridge_events[0]["summary"]
        assert "MEMORY.md updated:" in summary
        assert "3 lines" in summary
        assert "Facts" in summary

        # Full-content event exists but is consolidated (audit only)
        from spellbook.db.engines import get_sync_session
        from spellbook.db.spellbook_models import RawEvent
        from sqlalchemy import select

        with get_sync_session(db) as session:
            all_events = session.execute(
                select(RawEvent.event_type, RawEvent.consolidated)
            ).all()
            event_map = {row[0]: row[1] for row in all_events}
            assert "auto_memory_bridge" in event_map
            assert "auto_memory_content" in event_map
            # Content event is consolidated (1), bridge event is not (0)
            assert event_map["auto_memory_content"] == 1

    def test_brief_summary_format_with_sections(self, client, db):
        """Brief summary includes line count and section headers."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "file_path": "/path/MEMORY.md",
                "filename": "MEMORY.md",
                "content": "# Architecture\nMicroservices\n# Conventions\nPEP8\n# Testing\npytest",
                "is_primary": True,
                "branch": "main",
            },
        )
        assert resp.status_code == 200

        unconsolidated = get_unconsolidated_events(db, limit=10)
        bridge_events = [e for e in unconsolidated if e["event_type"] == "auto_memory_bridge"]
        assert len(bridge_events) == 1
        summary = bridge_events[0]["summary"]
        # Format: "MEMORY.md updated: N lines, sections: X, Y, Z"
        assert summary == "MEMORY.md updated: 6 lines, sections: Architecture, Conventions, Testing"

    def test_brief_summary_no_sections(self, client, db):
        """Brief summary for content with no markdown headers omits sections clause."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "filename": "notes.md",
                "content": "Just some plain text\nwith two lines",
                "branch": "main",
            },
        )
        assert resp.status_code == 200

        unconsolidated = get_unconsolidated_events(db, limit=10)
        bridge_events = [e for e in unconsolidated if e["event_type"] == "auto_memory_bridge"]
        assert len(bridge_events) == 1
        assert bridge_events[0]["summary"] == "notes.md updated: 2 lines"

    def test_content_truncated_at_10k(self, client, db):
        """Full-content event summary is truncated to 10,000 characters."""
        large_content = "x" * 15000
        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "file_path": "/path/MEMORY.md",
                "filename": "MEMORY.md",
                "content": large_content,
                "is_primary": True,
                "branch": "main",
            },
        )
        assert resp.status_code == 200

        from spellbook.db.engines import get_sync_session
        from spellbook.db.spellbook_models import RawEvent
        from sqlalchemy import select

        with get_sync_session(db) as session:
            content_events = session.execute(
                select(RawEvent.summary).where(
                    RawEvent.event_type == "auto_memory_content"
                )
            ).all()
            assert len(content_events) == 1
            assert len(content_events[0][0]) == 10000

    def test_consolidation_triggered(self, client, db, monkeypatch):
        """When should_consolidate returns True, consolidated=True in response."""
        import spellbook.mcp.routes as routes_mod

        monkeypatch.setattr(routes_mod, "should_consolidate", lambda *a, **kw: True)
        monkeypatch.setattr(routes_mod, "consolidate_batch", lambda *a, **kw: None)

        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "file_path": "/path/MEMORY.md",
                "filename": "MEMORY.md",
                "content": "# Test",
                "is_primary": True,
                "branch": "main",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["consolidated"] is True

    def test_no_consolidation_below_threshold(self, client):
        """When should_consolidate returns False, consolidated=False."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "filename": "MEMORY.md",
                "content": "# Test content",
                "branch": "main",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["consolidated"] is False

    def test_invalid_json_returns_400(self, client):
        """Non-JSON body returns 400."""
        resp = client.post(
            "/api/memory/bridge-content",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "invalid JSON" in resp.json()["error"]

    def test_optional_fields_default(self, client, db):
        """file_path, filename, is_primary, branch are all optional."""
        resp = client.post(
            "/api/memory/bridge-content",
            json={
                "session_id": "s1",
                "project": "Users-alice-project",
                "content": "# Minimal payload",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "captured"
        assert data["event_id"] > 0

        # Brief summary uses empty filename
        unconsolidated = get_unconsolidated_events(db, limit=10)
        bridge_events = [e for e in unconsolidated if e["event_type"] == "auto_memory_bridge"]
        assert len(bridge_events) == 1
        assert bridge_events[0]["summary"] == " updated: 1 lines, sections: Minimal payload"
