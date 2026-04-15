"""Tests for memory browser admin routes (file-based memory system).

Tests verify:
- List endpoint returns paginated results sorted by created desc
- Offset/limit pagination over the memory directory tree
- Single memory lookup by relative path (with slash-containing paths)
- 404 on nonexistent memory
- Search endpoint delegates to search_qmd.search_memories
- Response shape matches the new schema (type, kind, tags, citations,
  confidence, created, last_verified, body) -- NOT the old ORM shape
- Removed endpoints (/stats, /consolidate, /namespaces) return 404
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from spellbook.admin.app import create_admin_app
from spellbook.admin.auth import create_session_cookie

ROUTE_MODULE = "spellbook.admin.routes.memory"


def _write_memory(
    root: Path,
    rel_path: str,
    *,
    type: str = "project",
    created: str = "2026-03-14",
    kind: str | None = None,
    tags: list[str] | None = None,
    citations: list[dict] | None = None,
    confidence: str | None = None,
    last_verified: str | None = None,
    content_hash: str | None = None,
    body: str = "Example body text.",
) -> Path:
    """Write a minimal valid memory file and return its absolute path."""
    import yaml

    fm: dict = {"type": type, "created": datetime.date.fromisoformat(created)}
    if kind is not None:
        fm["kind"] = kind
    if citations:
        fm["citations"] = citations
    if tags:
        fm["tags"] = tags
    if last_verified is not None:
        fm["last_verified"] = datetime.date.fromisoformat(last_verified)
    if confidence is not None:
        fm["confidence"] = confidence
    if content_hash is not None:
        fm["content_hash"] = content_hash

    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
    doc = f"---\n{yaml_str}---\n\n{body}\n"
    abs_path = root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(doc)
    return abs_path


@pytest.fixture
def memory_root(tmp_path, monkeypatch):
    """Create a tmp memory root and patch the admin dependency to point at it."""
    root = tmp_path / "memories"
    root.mkdir()
    # Patch the module-level resolver used by admin routes.
    import spellbook.admin.routes.memory as memory_route
    monkeypatch.setattr(memory_route, "_resolve_memory_root", lambda: str(root))
    return root


@pytest.fixture
def auth_client(memory_root, mock_mcp_token):
    """Authenticated test client with memory_root fixture in scope."""
    app = create_admin_app()
    with TestClient(app) as c:
        cookie = create_session_cookie("test-session")
        c.cookies.set("spellbook_admin_session", cookie)
        yield c


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------


class TestMemoryList:
    def test_list_returns_paginated_memories_sorted_by_created_desc(
        self, memory_root, auth_client
    ):
        _write_memory(
            memory_root, "proj-a/project/oldest.md",
            created="2026-01-01", body="Oldest memory.",
        )
        _write_memory(
            memory_root, "proj-a/project/middle.md",
            created="2026-02-15", body="Middle memory.",
        )
        _write_memory(
            memory_root, "proj-a/project/newest.md",
            created="2026-03-30", body="Newest memory.",
        )

        response = auth_client.get("/api/memories")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert data["offset"] == 0
        assert data["limit"] == 50
        ids = [item["id"] for item in data["items"]]
        assert ids == [
            "proj-a/project/newest.md",
            "proj-a/project/middle.md",
            "proj-a/project/oldest.md",
        ]
        assert [item["created"] for item in data["items"]] == [
            "2026-03-30",
            "2026-02-15",
            "2026-01-01",
        ]

    def test_list_offset_and_limit(self, memory_root, auth_client):
        # Create 5 memories with distinct created dates, newest first in expected sort.
        dates = [
            "2026-05-01", "2026-04-01", "2026-03-01", "2026-02-01", "2026-01-01"
        ]
        for i, d in enumerate(dates):
            _write_memory(
                memory_root,
                f"proj/project/mem-{i}.md",
                created=d,
                body=f"Memory {i}.",
            )

        response = auth_client.get("/api/memories?offset=1&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["offset"] == 1
        assert data["limit"] == 2
        ids = [item["id"] for item in data["items"]]
        # Sorted desc by created: [mem-0, mem-1, mem-2, mem-3, mem-4]
        # offset=1, limit=2 -> [mem-1, mem-2]
        assert ids == ["proj/project/mem-1.md", "proj/project/mem-2.md"]

    def test_list_requires_auth(self, memory_root):
        app = create_admin_app()
        with TestClient(app) as c:
            response = c.get("/api/memories")
            assert response.status_code == 401


# ---------------------------------------------------------------------------
# Single memory endpoint
# ---------------------------------------------------------------------------


class TestMemoryDetail:
    def test_get_single_memory_by_path(self, memory_root, auth_client):
        _write_memory(
            memory_root,
            "proj-x/feedback/my-memory.md",
            type="feedback",
            created="2026-03-10",
            kind="decision",
            tags=["api", "retry"],
            citations=[{"file": "src/main.py", "symbol": "main", "symbol_type": "function"}],
            confidence="high",
            last_verified="2026-03-12",
            content_hash="sha256:deadbeef",
            body="This is the body.\nSecond line.",
        )

        response = auth_client.get("/api/memories/proj-x/feedback/my-memory.md")
        assert response.status_code == 200
        data = response.json()

        assert data == {
            "id": "proj-x/feedback/my-memory.md",
            "type": "feedback",
            "kind": "decision",
            "tags": ["api", "retry"],
            "citations": [
                {"file": "src/main.py", "symbol": "main", "symbol_type": "function"},
            ],
            "confidence": "high",
            "created": "2026-03-10",
            "last_verified": "2026-03-12",
            "body": "This is the body.\nSecond line.",
        }

    def test_get_nonexistent_memory_returns_404(self, memory_root, auth_client):
        response = auth_client.get("/api/memories/does/not/exist.md")
        assert response.status_code == 404
        data = response.json()
        assert data == {
            "error": {
                "code": "MEMORY_NOT_FOUND",
                "message": "Memory 'does/not/exist.md' not found",
            }
        }

    def test_get_rejects_path_traversal(self, memory_root, auth_client):
        # An escape-attempt path should 404 (or 400), never leak outside root.
        response = auth_client.get("/api/memories/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------


class TestMemorySearch:
    def test_search_delegates_to_recall(self, memory_root, auth_client, monkeypatch):
        from spellbook.memory.models import (
            Citation,
            MemoryFile,
            MemoryFrontmatter,
            MemoryResult,
        )

        # Create a real memory file that the result will point at.
        mem_path = _write_memory(
            memory_root,
            "proj-a/project/retry-logic.md",
            created="2026-03-01",
            kind="rule",
            tags=["retry"],
            citations=[{"file": "src/retry.py"}],
            body="Retry failed operations with exponential backoff.",
        )

        captured: dict = {}

        def fake_search(query, memory_dirs, **kwargs):
            captured["query"] = query
            captured["memory_dirs"] = memory_dirs
            captured["kwargs"] = kwargs
            fm = MemoryFrontmatter(
                type="project",
                created=datetime.date(2026, 3, 1),
                kind="rule",
                citations=[Citation(file="src/retry.py")],
                tags=["retry"],
            )
            mf = MemoryFile(
                path=str(mem_path),
                frontmatter=fm,
                content="Retry failed operations with exponential backoff.",
            )
            return [MemoryResult(memory=mf, score=0.85, match_context="Retry failed")]

        monkeypatch.setattr(
            "spellbook.admin.routes.memory.search_memories", fake_search
        )

        response = auth_client.get("/api/memories/search?q=retry&limit=5")
        assert response.status_code == 200
        data = response.json()

        assert captured["query"] == "retry"
        assert captured["memory_dirs"] == [str(memory_root)]
        assert captured["kwargs"]["limit"] == 5

        assert data == {
            "query": "retry",
            "total": 1,
            "items": [
                {
                    "id": "proj-a/project/retry-logic.md",
                    "type": "project",
                    "kind": "rule",
                    "tags": ["retry"],
                    "citations": [
                        {"file": "src/retry.py", "symbol": None, "symbol_type": None},
                    ],
                    "confidence": None,
                    "created": "2026-03-01",
                    "last_verified": None,
                    "body": "Retry failed operations with exponential backoff.",
                    "score": 0.85,
                    "match_context": "Retry failed",
                }
            ],
        }

    def test_search_requires_query(self, memory_root, auth_client):
        response = auth_client.get("/api/memories/search")
        assert response.status_code == 422

    def test_search_requires_auth(self, memory_root):
        app = create_admin_app()
        with TestClient(app) as c:
            response = c.get("/api/memories/search?q=foo")
            assert response.status_code == 401


# ---------------------------------------------------------------------------
# Schema / shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_response_shape_matches_new_schema(self, memory_root, auth_client):
        _write_memory(
            memory_root,
            "proj/project/shape-test.md",
            type="project",
            created="2026-03-14",
            kind="convention",
            tags=["t1"],
            body="Shape.",
        )

        list_resp = auth_client.get("/api/memories").json()
        item = list_resp["items"][0]
        assert set(item.keys()) == {
            "id", "type", "kind", "tags", "citations",
            "confidence", "created", "last_verified", "body",
        }

        detail = auth_client.get(
            "/api/memories/proj/project/shape-test.md"
        ).json()
        assert set(detail.keys()) == {
            "id", "type", "kind", "tags", "citations",
            "confidence", "created", "last_verified", "body",
        }

        # Explicitly assert legacy fields are absent.
        forbidden = {
            "memory_type", "status", "importance", "namespace",
            "memory_id", "meta", "accessed_at", "deleted_at",
            "content_hash", "content", "citation_count",
        }
        assert forbidden.isdisjoint(item.keys())
        assert forbidden.isdisjoint(detail.keys())


# ---------------------------------------------------------------------------
# Removed endpoints
# ---------------------------------------------------------------------------


class TestRemovedEndpoints:
    def test_stats_endpoint_removed(self, memory_root, auth_client):
        response = auth_client.get("/api/memories/stats")
        # /stats would now match {path:path} -> 404 from filestore.
        assert response.status_code == 404
        # The response body must NOT be a stats payload.
        body = response.json()
        assert "total" not in body or "by_type" not in body
        # Must be our structured not-found error.
        assert body.get("error", {}).get("code") == "MEMORY_NOT_FOUND"

    def test_consolidate_endpoint_removed(self, memory_root, auth_client):
        response = auth_client.post(
            "/api/memories/consolidate", json={"namespace": "x"}
        )
        # POST method is not registered; FastAPI returns 405 Method Not Allowed
        # because GET /api/memories/{path:path} matches the path.
        assert response.status_code in (404, 405)

    def test_namespaces_endpoint_removed(self, memory_root, auth_client):
        response = auth_client.get("/api/memories/namespaces")
        assert response.status_code == 404
        body = response.json()
        assert "namespaces" not in body
        assert body.get("error", {}).get("code") == "MEMORY_NOT_FOUND"
