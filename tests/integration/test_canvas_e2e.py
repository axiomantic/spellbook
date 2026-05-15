"""End-to-end integration test for the canvas feature.

Exercises the full loop:

    MCP canvas_open
      -> MCP canvas_write
        -> event_bus.publish (canvas.updated)
          -> GET /api/canvas/{name} returns updated content

Conftest discovery: pytest's sibling-conftest discovery does NOT
auto-load ``tests/admin/conftest.py``'s ``client`` / ``mock_mcp_token``
fixtures from a sibling package (``tests/integration/``). We construct
the admin app + authed test client inline here to keep this test
self-contained. The ``canvas_tmp_root``, ``mock_ctx``, and
``event_subscriber`` fixtures are imported explicitly from
``tests.canvas.conftest``.
"""

from __future__ import annotations

import secrets

import pytest

from tests.canvas.conftest import (  # noqa: F401 — re-export pytest fixtures
    canvas_tmp_root,
    event_subscriber,
    mock_ctx,
)


@pytest.fixture
def admin_client(monkeypatch):
    """Authed FastAPI TestClient against the real admin app.

    Mocks the MCP token loader and writes the matching HMAC cookie so
    auth checks pass. Mirrors ``tests/admin/conftest.py`` rather than
    importing it, to keep the integration package self-contained
    (per impl plan A.5 step 1 — documented choice).
    """
    from fastapi.testclient import TestClient

    from spellbook.admin.app import create_admin_app
    from spellbook.admin.auth import create_session_cookie

    token = secrets.token_urlsafe(32)
    monkeypatch.setattr("spellbook.admin.auth.load_token", lambda: token)
    monkeypatch.setattr("spellbook.admin.routes.auth.load_token", lambda: token)

    app = create_admin_app()
    with TestClient(app) as c:
        c.cookies.set("spellbook_admin_session", create_session_cookie("test-session"))
        yield c


@pytest.mark.asyncio
async def test_canvas_e2e(
    canvas_tmp_root, mock_ctx, event_subscriber, admin_client
):
    """write -> event -> route returns updated content."""
    from spellbook.mcp.tools.canvas import canvas_open, canvas_write

    # 1. Open the canvas via MCP.
    open_result = await canvas_open(ctx=mock_ctx, name="test")
    assert open_result["status"] == "opened"

    # 2. Write content via MCP.
    write_result = await canvas_write(
        ctx=mock_ctx, canvas="test", content="# Hello"
    )
    assert write_result["status"] == "written"
    assert write_result["bytes"] == len(b"# Hello")

    # 3. The event_subscriber list (populated by the monkeypatched
    #    event_bus.publish) should now contain canvas.opened followed
    #    by canvas.updated.
    event_types = [e.event_type for e in event_subscriber]
    assert "canvas.opened" in event_types
    assert "canvas.updated" in event_types
    updated = next(e for e in event_subscriber if e.event_type == "canvas.updated")
    assert updated.data["canvas"] == "test"
    assert updated.data["page"] == "index.md"
    assert updated.data["bytes"] == len(b"# Hello")

    # 4. Fetch the canvas via the admin route and confirm the content
    #    round-trips.
    resp = admin_client.get("/api/canvas/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "test"
    assert body["content"] == "# Hello"
    assert body["bytes"] == len(b"# Hello")
    assert body["page"] == "index.md"
    assert body["closed"] is False


@pytest.mark.asyncio
async def test_canvas_e2e_list_then_detail(
    canvas_tmp_root, mock_ctx, event_subscriber, admin_client
):
    """canvas_open visible in list; detail returns full content."""
    from spellbook.mcp.tools.canvas import canvas_open, canvas_write

    await canvas_open(ctx=mock_ctx, name="alpha", title="Alpha Plan")
    await canvas_write(ctx=mock_ctx, canvas="alpha", content="body-1")

    # Listing should include it.
    list_resp = admin_client.get("/api/canvas")
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["count"] == 1
    assert payload["canvases"][0]["name"] == "alpha"
    assert payload["canvases"][0]["title"] == "Alpha Plan"

    # Detail should return the body.
    detail = admin_client.get("/api/canvas/alpha")
    assert detail.status_code == 200
    assert detail.json()["content"] == "body-1"
