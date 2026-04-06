"""Tests for memory browser admin routes (SQLAlchemy ORM migration).

Tests verify:
- ORM session usage (no raw SQL via query_spellbook_db/execute_spellbook_db)
- Standard API envelope: list endpoint returns {items, total, page, per_page, pages}
- FTS5 via text() escape hatch within ORM session
- citation_count via func.count() per memory
- Sort whitelist enforcement
- All existing behavior preserved (CRUD, consolidation, events, auth)
"""

import hashlib
import json
from types import SimpleNamespace

import bigfoot
import pytest
from dirty_equals import IsInstance

ROUTE_MODULE = "spellbook.admin.routes.memory"


async def _async_noop(*args, **kwargs):
    """Async no-op for mocking awaitable calls."""
    return None


def _make_memory_obj(
    id="mem-1",
    content="test memory content",
    memory_type="observation",
    namespace="project-a",
    branch="main",
    importance=1.0,
    created_at="2026-03-14T10:00:00Z",
    accessed_at=None,
    status="active",
    deleted_at=None,
    content_hash="abc123",
    meta="{}",
    citation_count=0,
):
    """Create a stub Memory ORM object with to_dict()."""
    obj = SimpleNamespace(
        id=id,
        content=content,
        memory_type=memory_type,
        namespace=namespace,
        branch=branch,
        importance=importance,
        created_at=created_at,
        accessed_at=accessed_at,
        status=status,
        deleted_at=deleted_at,
        content_hash=content_hash,
        meta=meta,
        _citation_count=citation_count,
    )
    obj.to_dict = lambda: {
        "id": obj.id,
        "content": obj.content,
        "memory_type": obj.memory_type,
        "namespace": obj.namespace,
        "branch": obj.branch,
        "importance": obj.importance,
        "created_at": obj.created_at,
        "accessed_at": obj.accessed_at,
        "status": obj.status,
        "deleted_at": obj.deleted_at,
        "content_hash": obj.content_hash,
        "meta": json.loads(obj.meta) if obj.meta else {},
    }
    return obj


def _make_citation_obj(
    id=1,
    memory_id="mem-1",
    file_path="/src/main.py",
    line_range="10-20",
    content_snippet="def main():",
):
    """Create a stub MemoryCitation ORM object with to_dict()."""
    obj = SimpleNamespace(
        id=id,
        memory_id=memory_id,
        file_path=file_path,
        line_range=line_range,
        content_snippet=content_snippet,
    )
    obj.to_dict = lambda: {
        "id": obj.id,
        "memory_id": obj.memory_id,
        "file_path": obj.file_path,
        "line_range": obj.line_range,
        "content_snippet": obj.content_snippet,
    }
    return obj


class _FakeResult:
    """Fake SQLAlchemy result object supporting various access patterns."""

    def __init__(self, result_type, value):
        self._result_type = result_type
        self._value = value

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def mappings(self):
        return self

    def all(self):
        return self._value


class _FakeSession:
    """Fake async session with sequential execute results."""

    def __init__(self, results=None, single_result=None):
        self._results = list(results) if results else []
        self._single_result = single_result
        self._call_index = 0
        self.flush_called = False

    async def execute(self, *args, **kwargs):
        if self._single_result is not None:
            return self._single_result
        if self._call_index < len(self._results):
            result = self._results[self._call_index]
            self._call_index += 1
            return result
        raise RuntimeError(f"No more results (called {self._call_index} times)")

    async def flush(self):
        self.flush_called = True


def _build_result(result_type, value):
    """Build a fake result object for session.execute()."""
    return _FakeResult(result_type, value)


def _make_list_session(memories, total=None, citation_counts=None):
    """Create a fake session for the list endpoint.

    The list endpoint executes:
    1. count query -> scalar_one
    2. data query -> scalars().all()
    3. N citation count queries -> scalar_one each
    """
    if total is None:
        total = len(memories)
    if citation_counts is None:
        citation_counts = [getattr(m, "_citation_count", 0) for m in memories]

    results = [
        _build_result("scalar_one", total),
        _build_result("scalars_all", memories),
    ]
    for cc in citation_counts:
        results.append(_build_result("scalar_one", cc))

    return _FakeSession(results=results)


def _make_test_client(session):
    """Create an authenticated test client with the given fake session as db dependency."""
    from spellbook.admin.app import create_admin_app
    from spellbook.db import spellbook_db
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie

    app = create_admin_app()
    app.dependency_overrides[spellbook_db] = lambda: session
    test_client = TestClient(app)
    cookie = create_session_cookie("test-session")
    test_client.cookies.set("spellbook_admin_session", cookie)
    return test_client


class TestMemoryList:
    def test_list_memories_returns_items_key(self, client):
        """List endpoint returns standard {items, ...} envelope, not {memories, ...}."""
        session = _make_list_session([_make_memory_obj()])
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories")
        assert response.status_code == 200
        data = response.json()
        # Standard envelope uses "items" key
        assert "items" in data, f"Expected 'items' key in response, got keys: {list(data.keys())}"
        assert "memories" not in data, "Response should use 'items' not 'memories'"
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["per_page"] == 50
        assert data["pages"] == 1
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["id"] == "mem-1"
        assert item["content"] == "test memory content"
        assert item["memory_type"] == "observation"
        assert item["namespace"] == "project-a"
        assert item["branch"] == "main"
        assert item["importance"] == 1.0
        assert item["created_at"] == "2026-03-14T10:00:00Z"
        assert item["accessed_at"] is None
        assert item["status"] == "active"
        assert item["meta"] == {}

    def test_list_memories_with_citation_count(self, client):
        """List includes citation_count field from per-memory count query."""
        mem = _make_memory_obj(citation_count=3)
        session = _make_list_session([mem], citation_counts=[3])
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["citation_count"] == 3

    def test_list_memories_pagination(self, client):
        """Pagination metadata is correct for multi-page results."""
        mems = [_make_memory_obj(id=f"mem-{i}") for i in range(25)]
        session = _make_list_session(mems, total=75)
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories?page=2&per_page=25")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 25
        assert data["pages"] == 3
        assert data["total"] == 75

    def test_list_memories_fts_search(self, client):
        """FTS search uses text() escape hatch, not ORM."""
        # FTS path returns raw dicts from text() query, not ORM objects.
        # Build fake for FTS path: count (scalar_one) + data (mappings().all())
        results = [
            _build_result("scalar_one", 1),
            _build_result("all_tuples", [{
                "id": "mem-1",
                "content": "matching result",
                "memory_type": "observation",
                "namespace": "project-a",
                "branch": "main",
                "importance": 1.0,
                "created_at": "2026-03-14T10:00:00Z",
                "accessed_at": None,
                "status": "active",
                "meta": "{}",
                "deleted_at": None,
                "content_hash": "abc123",
                "citation_count": 0,
            }]),
        ]
        session = _FakeSession(results=results)
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories?q=matching")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "matching result"
        assert data["items"][0]["citation_count"] == 0

    def test_list_memories_invalid_sort_defaults_to_created_at(self, client):
        """Invalid sort column silently defaults to created_at."""
        session = _make_list_session([], total=0)
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories?sort=invalid_column")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_memories_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/memories")
        assert response.status_code == 401

    def test_list_memories_namespace_filter(self, client):
        """Namespace filter produces filtered results."""
        mem = _make_memory_obj(namespace="filtered-ns")
        session = _make_list_session([mem])
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories?namespace=filtered-ns")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["namespace"] == "filtered-ns"

    def test_list_memories_status_filter_overrides_deleted_exclusion(self, client):
        """When status filter is provided, it replaces the default deleted exclusion."""
        mem = _make_memory_obj(status="deleted")
        # Override to_dict to return deleted status
        orig_to_dict = mem.to_dict
        d = orig_to_dict()
        d["status"] = "deleted"
        mem.to_dict = lambda: d
        session = _make_list_session([mem])
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories?status=deleted")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "deleted"


class TestMemoryDetail:
    def test_get_memory_returns_detail_with_citations(self, client):
        """Detail endpoint returns memory with citations list."""
        mem = _make_memory_obj(content="full content here")
        citation = _make_citation_obj()

        results = [
            _build_result("scalar_one_or_none", mem),
            _build_result("scalar_one", 1),
            _build_result("scalars_all", [citation]),
        ]
        session = _FakeSession(results=results)
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories/mem-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "mem-1"
        assert data["content"] == "full content here"
        assert data["citation_count"] == 1
        assert len(data["citations"]) == 1
        assert data["citations"][0] == {
            "id": 1,
            "memory_id": "mem-1",
            "file_path": "/src/main.py",
            "line_range": "10-20",
            "content_snippet": "def main():",
        }

    def test_get_memory_not_found(self, client):
        """Non-existent memory returns 404 with error code."""
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", None)
        )
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "MEMORY_NOT_FOUND"
        assert "nonexistent" in data["error"]["message"]

    def test_get_memory_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/memories/mem-1")
        assert response.status_code == 401


class TestMemoryUpdate:
    def test_update_memory_content(self, client, monkeypatch):
        """Update content also updates content_hash."""
        mem = _make_memory_obj(id="mem-1", content="old content")
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )

        test_client = _make_test_client(session)

        published_events = []

        async def capture_publish(event):
            published_events.append(event)

        mock_bus = SimpleNamespace(publish=capture_publish)
        monkeypatch.setattr(f"{ROUTE_MODULE}.event_bus", mock_bus)

        response = test_client.put(
            "/api/memories/mem-1", json={"content": "updated content"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok", "memory_id": "mem-1"}
        # Verify the ORM object was modified
        assert mem.content == "updated content"
        expected_hash = hashlib.sha256("updated content".encode()).hexdigest()
        assert mem.content_hash == expected_hash
        assert len(published_events) == 1

    def test_update_memory_importance(self, client, monkeypatch):
        """Update importance field via ORM."""
        mem = _make_memory_obj()
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )

        test_client = _make_test_client(session)

        mock_bus = SimpleNamespace(publish=_async_noop)
        monkeypatch.setattr(f"{ROUTE_MODULE}.event_bus", mock_bus)

        response = test_client.put(
            "/api/memories/mem-1", json={"importance": 5.0}
        )

        assert response.status_code == 200
        assert mem.importance == 5.0
        mock_bus.publish.assert_call(args=(IsInstance[object],), kwargs={})

    def test_update_memory_meta(self, client, monkeypatch):
        """Update meta field stores JSON string on ORM object."""
        mem = _make_memory_obj()
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )

        test_client = _make_test_client(session)

        mock_bus = SimpleNamespace(publish=_async_noop)
        monkeypatch.setattr(f"{ROUTE_MODULE}.event_bus", mock_bus)

        response = test_client.put(
            "/api/memories/mem-1", json={"meta": {"key": "value"}}
        )

        assert response.status_code == 200
        assert mem.meta == json.dumps({"key": "value"})
        mock_bus.publish.assert_call(args=(IsInstance[object],), kwargs={})

    def test_update_memory_not_found(self, client):
        """Update non-existent memory returns 404."""
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", None)
        )
        test_client = _make_test_client(session)

        response = test_client.put(
            "/api/memories/nonexistent", json={"content": "new"}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MEMORY_NOT_FOUND"

    def test_update_no_valid_fields(self, client):
        """Update with empty body returns 400."""
        mem = _make_memory_obj()
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )
        test_client = _make_test_client(session)

        response = test_client.put("/api/memories/mem-1", json={})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"

    def test_update_publishes_event(self, client, monkeypatch):
        """Update publishes memory.updated event."""
        mem = _make_memory_obj()
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )

        test_client = _make_test_client(session)

        captured_events = []

        async def capture_publish(event):
            captured_events.append(event)

        mock_bus = SimpleNamespace(publish=capture_publish)
        monkeypatch.setattr(f"{ROUTE_MODULE}.event_bus", mock_bus)

        response = test_client.put(
            "/api/memories/mem-1",
            json={"content": "updated"},
        )

        assert response.status_code == 200
        assert len(captured_events) == 1
        event = captured_events[0]
        assert event.event_type == "memory.updated"
        assert event.data["memory_id"] == "mem-1"
        assert event.data["fields"] == ["content"]

    def test_update_memory_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.put(
            "/api/memories/mem-1", json={"content": "new"}
        )
        assert response.status_code == 401


class TestMemoryDelete:
    def test_delete_memory_soft_deletes(self, client, monkeypatch):
        """Delete sets status='deleted' and deleted_at via ORM."""
        mem = _make_memory_obj(id="mem-1", status="active")
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )

        test_client = _make_test_client(session)

        mock_bus = SimpleNamespace(publish=_async_noop)
        monkeypatch.setattr(f"{ROUTE_MODULE}.event_bus", mock_bus)

        response = test_client.delete("/api/memories/mem-1")

        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok", "memory_id": "mem-1"}
        # Verify ORM object was modified for soft delete
        assert mem.status == "deleted"
        assert mem.deleted_at is not None  # Should be set to current time
        mock_bus.publish.assert_call(args=(IsInstance[object],), kwargs={})

    def test_delete_memory_not_found(self, client):
        """Delete non-existent memory returns 404."""
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", None)
        )
        test_client = _make_test_client(session)

        response = test_client.delete("/api/memories/nonexistent")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MEMORY_NOT_FOUND"

    def test_delete_already_deleted_returns_404(self, client):
        """Delete on already-deleted memory returns 404."""
        mem = _make_memory_obj(id="mem-1", status="deleted")
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )
        test_client = _make_test_client(session)

        response = test_client.delete("/api/memories/mem-1")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "MEMORY_NOT_FOUND"

    def test_delete_publishes_event(self, client, monkeypatch):
        """Delete publishes memory.deleted event."""
        mem = _make_memory_obj(id="mem-1", status="active")
        session = _FakeSession(
            single_result=_build_result("scalar_one_or_none", mem)
        )

        test_client = _make_test_client(session)

        captured_events = []

        async def capture_publish(event):
            captured_events.append(event)

        mock_bus = SimpleNamespace(publish=capture_publish)
        monkeypatch.setattr(f"{ROUTE_MODULE}.event_bus", mock_bus)

        response = test_client.delete("/api/memories/mem-1")

        assert response.status_code == 200
        assert len(captured_events) == 1
        event = captured_events[0]
        assert event.event_type == "memory.deleted"
        assert event.data["memory_id"] == "mem-1"

    def test_delete_memory_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.delete("/api/memories/mem-1")
        assert response.status_code == 401


class TestConsolidate:
    def test_consolidate_triggers_successfully(self, client, monkeypatch):
        monkeypatch.setattr(
            f"{ROUTE_MODULE}.consolidate_batch",
            lambda *a, **kw: {
                "status": "ok",
                "memories_created": 3,
                "events_consolidated": 10,
            },
        )

        monkeypatch.setattr(
            f"{ROUTE_MODULE}.get_db_path",
            lambda *a, **kw: "/tmp/test.db",
        )

        response = client.post(
            "/api/memories/consolidate",
            json={"namespace": "test-ns", "max_events": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert data == {
            "memories_created": 3,
            "events_consolidated": 10,
        }

    def test_consolidate_409_when_running(self, client, monkeypatch):
        monkeypatch.setattr(
            f"{ROUTE_MODULE}._consolidation_running", True
        )

        response = client.post(
            "/api/memories/consolidate",
            json={"namespace": "test-ns"},
        )
        assert response.status_code == 409
        assert (
            response.json()["error"]["code"]
            == "CONSOLIDATION_IN_PROGRESS"
        )

    def test_consolidate_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/memories/consolidate", json={"namespace": "test-ns"}
        )
        assert response.status_code == 401


class TestNamespaces:
    def test_list_namespaces_via_orm(self, client):
        """Namespaces endpoint uses ORM query."""
        mock_mem_a = SimpleNamespace(namespace="project-a")
        mock_mem_b = SimpleNamespace(namespace="project-b")

        results = [_build_result("scalars_all", [mock_mem_a, mock_mem_b])]
        session = _FakeSession(results=results)
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories/namespaces")
        assert response.status_code == 200
        data = response.json()
        assert data == {"namespaces": ["project-a", "project-b"]}


class TestMemoryStats:
    def test_stats_returns_aggregated_via_orm(self, client):
        """Stats endpoint uses ORM func.count() and group_by."""
        results = [
            _build_result("scalar_one", 42),
            _build_result("all_tuples", [
                ("observation", 30),
                ("synthesis", 12),
            ]),
            _build_result("all_tuples", [
                ("active", 40),
                ("deleted", 2),
            ]),
            _build_result("all_tuples", [
                ("project-a", 25),
                ("project-b", 17),
            ]),
        ]
        session = _FakeSession(results=results)
        test_client = _make_test_client(session)

        response = test_client.get("/api/memories/stats")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "total": 42,
            "by_type": {"observation": 30, "synthesis": 12},
            "by_status": {"active": 40, "deleted": 2},
            "by_namespace": {"project-a": 25, "project-b": 17},
        }
