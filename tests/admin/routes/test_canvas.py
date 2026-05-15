"""Tests for ``spellbook.admin.routes.canvas``.

Auth dependency is overridden for the non-``test_requires_auth`` cases
via ``app.dependency_overrides``. The canvas root is monkeypatched via
the ``canvas_tmp_root`` fixture imported explicitly from
``tests/canvas/conftest.py``.
"""

from __future__ import annotations

import pytest

from spellbook.admin.auth import require_admin_auth
from spellbook.canvas import store as canvas_store

# Pytest does not automatically pick up sibling-package conftests for
# cross-package fixtures; import explicitly. Marked F401 — the names
# are used implicitly by pytest's parameter resolution.
from tests.canvas.conftest import canvas_tmp_root  # noqa: F401


@pytest.fixture
def authed_app(admin_app):
    """Override ``require_admin_auth`` so non-auth tests get straight to
    the route logic."""
    admin_app.dependency_overrides[require_admin_auth] = lambda: "test-session"
    yield admin_app
    admin_app.dependency_overrides.pop(require_admin_auth, None)


@pytest.fixture
def authed_client(authed_app):
    from fastapi.testclient import TestClient

    with TestClient(authed_app) as c:
        yield c


def test_requires_auth(unauthenticated_client):
    """Without a session cookie, GET /api/canvas returns 401."""
    resp = unauthenticated_client.get("/api/canvas")
    assert resp.status_code == 401


def test_list_canvases_empty(canvas_tmp_root, authed_client):
    resp = authed_client.get("/api/canvas")
    assert resp.status_code == 200
    assert resp.json() == {"canvases": [], "count": 0}


def test_list_canvases_populated(canvas_tmp_root, authed_client):
    import time
    canvas_store.open_canvas("alpha", title="Alpha")
    time.sleep(0.01)
    canvas_store.open_canvas("beta", title="Beta")
    # Bump alpha so it sorts first.
    meta = canvas_store.read_meta("alpha")
    bumped = meta.model_copy(update={"last_updated": canvas_store._now_utc()})
    canvas_store.write_meta("alpha", bumped)

    resp = authed_client.get("/api/canvas")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    names = [c["name"] for c in payload["canvases"]]
    assert names == ["alpha", "beta"]


def test_get_canvas_happy(canvas_tmp_root, authed_client):
    canvas_store.open_canvas("design", title="Design Doc")
    canvas_store.write_page("design", "# Hello")
    resp = authed_client.get("/api/canvas/design")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "design"
    assert body["title"] == "Design Doc"
    assert body["page"] == "index.md"
    assert body["content"] == "# Hello"
    assert body["bytes"] == 7
    assert body["closed"] is False


def test_get_canvas_not_found(canvas_tmp_root, authed_client):
    resp = authed_client.get("/api/canvas/ghost")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert "ghost" in body["error"]["message"]


def test_get_canvas_invalid_name(canvas_tmp_root, authed_client):
    # FastAPI's path param with a slash gets URL-encoded; pass an
    # invalid (uppercase) name to exercise the regex-rejection branch.
    resp = authed_client.get("/api/canvas/FOO")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_name"


def test_get_canvas_requires_auth(unauthenticated_client):
    resp = unauthenticated_client.get("/api/canvas/anything")
    assert resp.status_code == 401
