"""Tests for focus.py admin routes (ORM migration).

Tests verify:
- GET /focus/stacks returns {items: [...]} (not {stacks: [...]})
- GET /focus/corrections returns paginated {items, total, page, per_page, pages}
- GET /focus/corrections supports sorting with whitelist {created_at, project_path, correction_type}
- GET /focus/corrections supports period and filter params
"""

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from spellbook.db.base import SpellbookBase
from spellbook.db.spellbook_models import StintStack, StintCorrectionEvent


@pytest.fixture
async def async_engine():
    """Create an async in-memory SQLite engine with spellbook tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SpellbookBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded_engine(async_engine):
    """Engine with test data for stacks and corrections."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(StintStack(
            id=1,
            project_path="/home/user/project-a",
            session_id="sess-1",
            stack_json='[{"name": "task-1"}, {"name": "task-2"}]',
            updated_at="2026-03-20T10:00:00",
        ))
        session.add(StintStack(
            id=2,
            project_path="/home/user/project-b",
            session_id="sess-2",
            stack_json='[]',
            updated_at="2026-03-20T09:00:00",
        ))
        session.add(StintCorrectionEvent(
            id=1,
            project_path="/home/user/project-a",
            session_id="sess-1",
            correction_type="llm_wrong",
            old_stack_json='[{"name": "old-1"}]',
            new_stack_json='[{"name": "new-1"}]',
            diff_summary="Fixed task ordering",
            created_at="2026-03-20T08:00:00",
        ))
        session.add(StintCorrectionEvent(
            id=2,
            project_path="/home/user/project-b",
            session_id="sess-2",
            correction_type="mcp_wrong",
            old_stack_json='[{"name": "old-2"}]',
            new_stack_json='[{"name": "new-2"}]',
            diff_summary="Corrected MCP call",
            created_at="2026-03-20T09:00:00",
        ))
        session.add(StintCorrectionEvent(
            id=3,
            project_path="/home/user/project-a",
            session_id="sess-1",
            correction_type="llm_wrong",
            old_stack_json='[{"name": "old-3"}]',
            new_stack_json='[{"name": "new-3"}]',
            diff_summary="Another fix",
            created_at="2026-03-20T10:00:00",
        ))
        await session.commit()
    return async_engine


@pytest.fixture
def focus_client(seeded_engine, admin_app, mock_mcp_token):
    """Test client with seeded focus data and mocked DB dependency."""
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie
    from spellbook.db import spellbook_db

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)

    async def mock_spellbook_db():
        async with factory() as session:
            yield session

    admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
    client = TestClient(admin_app)
    cookie = create_session_cookie("test-session")
    client.cookies.set("spellbook_admin_session", cookie)
    yield client
    admin_app.dependency_overrides.clear()


@pytest.fixture
def empty_focus_client(async_engine, admin_app, mock_mcp_token):
    """Test client with empty database."""
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie
    from spellbook.db import spellbook_db

    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def mock_spellbook_db():
        async with factory() as session:
            yield session

    admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
    client = TestClient(admin_app)
    cookie = create_session_cookie("test-session")
    client.cookies.set("spellbook_admin_session", cookie)
    yield client
    admin_app.dependency_overrides.clear()


class TestFocusStacksEndpoint:
    """GET /api/focus/stacks should return standardized list response."""

    def test_stacks_returns_items_key(self, focus_client):
        """Response uses 'items' key (not 'stacks')."""
        response = focus_client.get("/api/focus/stacks")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "stacks" not in data

    def test_stacks_items_contain_correct_fields(self, focus_client):
        """Each stack item has project_path, session_id, stack, depth, updated_at."""
        response = focus_client.get("/api/focus/stacks")
        assert response.status_code == 200
        data = response.json()
        items = data["items"]
        assert len(items) == 2

        # Items should be ordered by updated_at DESC
        assert items[0] == {
            "project_path": "/home/user/project-a",
            "session_id": "sess-1",
            "stack": [{"name": "task-1"}, {"name": "task-2"}],
            "depth": 2,
            "updated_at": "2026-03-20T10:00:00",
        }
        assert items[1] == {
            "project_path": "/home/user/project-b",
            "session_id": "sess-2",
            "stack": [],
            "depth": 0,
            "updated_at": "2026-03-20T09:00:00",
        }

    def test_stacks_empty_db(self, empty_focus_client):
        """Returns empty items list when no stacks exist."""
        response = empty_focus_client.get("/api/focus/stacks")
        assert response.status_code == 200
        assert response.json() == {"items": []}


class TestFocusCorrectionsEndpoint:
    """GET /api/focus/corrections should return paginated, sorted results."""

    def test_corrections_returns_paginated_response(self, focus_client):
        """Response has items, total, page, per_page, pages keys."""
        response = focus_client.get("/api/focus/corrections")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "corrections" not in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data

    def test_corrections_default_pagination(self, focus_client):
        """Default pagination returns page 1 with all 3 items."""
        response = focus_client.get("/api/focus/corrections")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["per_page"] == 50
        assert data["pages"] == 1
        assert len(data["items"]) == 3

    def test_corrections_default_sort_is_created_at_desc(self, focus_client):
        """Default sort is created_at DESC (most recent first)."""
        response = focus_client.get("/api/focus/corrections")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 3
        # Most recent first
        assert items[0]["created_at"] == "2026-03-20T10:00:00"
        assert items[1]["created_at"] == "2026-03-20T09:00:00"
        assert items[2]["created_at"] == "2026-03-20T08:00:00"

    def test_corrections_items_have_parsed_json(self, focus_client):
        """Items have old_stack and new_stack as parsed lists (not raw JSON)."""
        response = focus_client.get("/api/focus/corrections")
        assert response.status_code == 200
        items = response.json()["items"]
        # First item is id=3 (most recent by created_at)
        assert items[0] == {
            "id": 3,
            "project_path": "/home/user/project-a",
            "session_id": "sess-1",
            "correction_type": "llm_wrong",
            "old_stack": [{"name": "old-3"}],
            "new_stack": [{"name": "new-3"}],
            "diff_summary": "Another fix",
            "created_at": "2026-03-20T10:00:00",
        }

    def test_corrections_pagination_per_page(self, focus_client):
        """per_page=1 returns only 1 item with correct pagination metadata."""
        response = focus_client.get("/api/focus/corrections?per_page=1&page=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 2
        assert data["per_page"] == 1
        assert data["pages"] == 3
        assert len(data["items"]) == 1
        # Page 2 should be the second most recent
        assert data["items"][0]["created_at"] == "2026-03-20T09:00:00"

    def test_corrections_sort_by_project_path_asc(self, focus_client):
        """Sort by project_path ascending works."""
        response = focus_client.get(
            "/api/focus/corrections?sort=project_path&order=asc"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        paths = [item["project_path"] for item in items]
        assert paths == [
            "/home/user/project-a",
            "/home/user/project-a",
            "/home/user/project-b",
        ]

    def test_corrections_sort_by_correction_type(self, focus_client):
        """Sort by correction_type is in the allowed whitelist."""
        response = focus_client.get(
            "/api/focus/corrections?sort=correction_type&order=asc"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        types = [item["correction_type"] for item in items]
        assert types == ["llm_wrong", "llm_wrong", "mcp_wrong"]

    def test_corrections_invalid_sort_falls_back_to_created_at(self, focus_client):
        """Invalid sort column falls back to created_at."""
        response = focus_client.get(
            "/api/focus/corrections?sort=INVALID&order=desc"
        )
        assert response.status_code == 200
        items = response.json()["items"]
        # Should be same as default: created_at DESC
        assert items[0]["created_at"] == "2026-03-20T10:00:00"
        assert items[2]["created_at"] == "2026-03-20T08:00:00"

    def test_corrections_filter_by_project(self, focus_client):
        """Filter by project_path returns only matching items."""
        response = focus_client.get(
            "/api/focus/corrections?project=/home/user/project-b"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0] == {
            "id": 2,
            "project_path": "/home/user/project-b",
            "session_id": "sess-2",
            "correction_type": "mcp_wrong",
            "old_stack": [{"name": "old-2"}],
            "new_stack": [{"name": "new-2"}],
            "diff_summary": "Corrected MCP call",
            "created_at": "2026-03-20T09:00:00",
        }

    def test_corrections_filter_by_correction_type(self, focus_client):
        """Filter by correction_type returns only matching items."""
        response = focus_client.get(
            "/api/focus/corrections?correction_type=llm_wrong"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["correction_type"] == "llm_wrong"

    def test_corrections_page_clamping(self, focus_client):
        """Page beyond max clamps to last page."""
        response = focus_client.get("/api/focus/corrections?page=999")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1  # Only 1 page with 3 items at default 50/page
        assert data["pages"] == 1

    def test_corrections_period_all_returns_everything(self, focus_client):
        """period=all returns all corrections without time filtering."""
        response = focus_client.get("/api/focus/corrections?period=all")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    def test_corrections_period_param_accepted(self, focus_client):
        """period parameter is accepted without error."""
        response = focus_client.get("/api/focus/corrections?period=7d")
        assert response.status_code == 200
        # Period filtering uses datetime('now', offset) which depends on
        # real time. Our test data has timestamps in the future (2026),
        # so all items should be excluded by a relative period filter.
        data = response.json()
        assert "items" in data
        assert "total" in data
