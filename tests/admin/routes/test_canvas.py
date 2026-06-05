"""Tests for ``spellbook.admin.routes.canvas``.

Auth dependency is overridden for the non-``test_requires_auth`` cases
via ``app.dependency_overrides``. The canvas root is monkeypatched via
the ``canvas_tmp_root`` fixture imported explicitly from
``tests/canvas/conftest.py``.
"""

from __future__ import annotations

import os

import pytest

from spellbook.admin.auth import require_admin_auth
from spellbook.canvas import store as canvas_store

# Pytest does not automatically pick up sibling-package conftests for
# cross-package fixtures; import explicitly. Marked F401 — the names are used
# implicitly by pytest's parameter resolution. ``event_subscriber`` is the
# captured-publish LIST (tests/canvas/conftest.py), shared by the
# decision-submit event test below. (Fixture params shadowing these imports
# raise F811 at each call site — a pre-existing pytest/ruff pattern in this
# file for ``canvas_tmp_root``, already present on the branch baseline.)
from tests.canvas.conftest import (  # noqa: F401
    canvas_tmp_root,
    event_subscriber,
)


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

    # The admin app wires HostValidatorMiddleware (loopback Host allowlist)
    # and OriginCheckMiddleware. Starlette's TestClient defaults to
    # ``Host: testserver``, which the Host validator rejects with 400.
    # Send the same default loopback Host/Origin headers the shared admin
    # fixtures use (see tests/admin/conftest.py::_DEFAULT_TEST_HEADERS) so
    # these route tests exercise the route logic, not the Host rejection.
    default_headers = {
        "Host": "127.0.0.1:8765",
        "Origin": "http://127.0.0.1:8765",
    }
    with TestClient(authed_app, headers=default_headers) as c:
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
    # Full response-body equality. ``created_at``/``last_updated`` are the only
    # dynamic fields (server clock at open); anchor them to the actual response
    # values so the assertion stays exact and non-partial across every field
    # (name, title, page, content, bytes, closed, AND decision==None).
    assert body == {
        "name": "design",
        "title": "Design Doc",
        "created_at": body["created_at"],
        "last_updated": body["last_updated"],
        "closed": False,
        "page": "index.md",
        "content": "# Hello",
        "bytes": 7,
        "decision": None,
    }


def test_get_canvas_not_found(canvas_tmp_root, authed_client):
    resp = authed_client.get("/api/canvas/ghost")
    assert resp.status_code == 404
    # Full error-body equality with the exact §5.2 message string.
    assert resp.json() == {
        "error": {
            "code": "not_found",
            "message": "Canvas 'ghost' not found",
        }
    }


def test_get_canvas_invalid_name(canvas_tmp_root, authed_client):
    # FastAPI's path param with a slash gets URL-encoded; pass an
    # invalid (uppercase) name to exercise the regex-rejection branch.
    resp = authed_client.get("/api/canvas/FOO")
    assert resp.status_code == 400
    # Full error-body equality with the exact §5.2 message string.
    assert resp.json() == {
        "error": {
            "code": "invalid_name",
            "message": "Name must match ^[a-z0-9][a-z0-9_-]{0,63}$",
        }
    }


def test_get_canvas_requires_auth(unauthenticated_client):
    resp = unauthenticated_client.get("/api/canvas/anything")
    assert resp.status_code == 401


def test_get_canvas_detail_includes_decision(authed_client, canvas_tmp_root):
    from spellbook.canvas import store

    store.open_canvas("plan-x", title="Plan X")
    store.declare_decision(
        "plan-x", "d1", "approve", "Ship?", None, "sess-1", "tok-1"
    )
    resp = authed_client.get("/api/canvas/plan-x")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == {
        "decision_id": "d1",
        "kind": "approve",
        "prompt": "Ship?",
        "options": None,
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Task C1: POST /api/canvas/{name}/decision/submit (design §5.1, §5.2, §7)
# ---------------------------------------------------------------------------


def _open_decision(name="plan-x", did="d1", kind="choice"):
    """Open a canvas with one pending decision. Binding session/token mirror
    Task B2's declare contract (the browser never sends these; the route
    reconstructs the binding from stored meta, §5.1 step 2)."""
    from spellbook.canvas import store

    opts = (
        [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]
        if kind == "choice"
        else None
    )
    store.open_canvas(name, title=name)
    store.declare_decision(name, did, kind, "Q", opts, "sess-1", "tok-1")


def test_submit_happy_path(authed_client, canvas_tmp_root):
    import json

    _open_decision()
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Side effect: the SubmissionItem JSON landed in the inbox (the first-wins
    # claim key, §3.6.1). Read it first so its server-generated ``submitted_at``
    # anchors the full-equality assertions below (it is the only genuinely
    # dynamic field; everything else is asserted exactly).
    inbox = os.path.join(
        canvas_store._resolve_canvas_root(), "plan-x", "inbox", "d1.json"
    )
    with open(inbox, encoding="utf-8") as fh:
        written = json.loads(fh.read())
    submitted_at = written["submitted_at"]
    # Full inbox-file equality: every field of the persisted SubmissionItem.
    assert written == {
        "schema_version": 1,
        "decision_id": "d1",
        "canvas": "plan-x",
        "kind": "choice",
        "value": "a",
        "free_text": None,
        "await_binding": {"session_id": "sess-1", "await_token": "tok-1"},
        "submitted_at": submitted_at,  # dynamic: anchored to the persisted value
        "consumed": False,
    }
    # Full response-body equality. ``submitted_at`` MUST equal the persisted
    # value (the response reports what was durably claimed), so anchoring to the
    # disk value makes this an exact, non-partial assertion.
    assert body == {
        "status": "accepted",
        "decision_id": "d1",
        "submitted_at": submitted_at,
    }


def test_submit_no_cookie_401(unauthenticated_client, canvas_tmp_root):
    # ``unauthenticated_client`` (tests/admin/conftest.py) sends loopback
    # Host/Origin but NO auth cookie → require_admin_auth rejects with 401.
    # The local ``authed_client`` overrides require_admin_auth and would never
    # 401, so it is deliberately NOT used here (mirrors test_requires_auth).
    _open_decision()
    resp = unauthenticated_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 401


def test_submit_cross_origin_403(authed_client, canvas_tmp_root):
    # M3 (REQUIRED, §5.2 403 row): OriginCheckMiddleware is app-level and runs
    # even when require_admin_auth is overridden by authed_client. The client
    # default Origin is loopback; override it per-request to a cross-origin
    # value (pattern: tests/admin/test_origin_middleware.py).
    _open_decision()
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
        headers={"Origin": "http://evil.com"},
    )
    assert resp.status_code == 403


def test_submit_first_wins_409(authed_client, canvas_tmp_root):
    _open_decision()
    first = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    second = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "b"},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json() == {
        "error": {
            "code": "already_decided",
            "message": "Decision 'd1' was already submitted",
        }
    }


def test_submit_invalid_value_400(authed_client, canvas_tmp_root):
    _open_decision()
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "zzz"},
    )
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {
            "code": "invalid_value",
            "message": "Value 'zzz' is not valid for this decision",
        }
    }


def test_submit_no_such_decision_404(authed_client, canvas_tmp_root):
    from spellbook.canvas import store

    store.open_canvas("plan-x", title="Plan X")  # no decision declared
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 404
    assert resp.json() == {
        "error": {
            "code": "no_such_decision",
            "message": "No pending decision 'd1' on canvas 'plan-x'",
        }
    }


def test_submit_canvas_closed_409(authed_client, canvas_tmp_root):
    from spellbook.canvas import store

    _open_decision()
    store.close_canvas("plan-x")
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "canvas_closed",
            "message": "Canvas 'plan-x' is closed",
        }
    }


def test_submit_cancelled_409(authed_client, canvas_tmp_root):
    from spellbook.canvas import store

    _open_decision()
    store.cancel_decision("plan-x", "d1")
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "cancelled",
            "message": "Decision 'd1' was cancelled",
        }
    }


def test_submit_invalid_name_400(authed_client, canvas_tmp_root):
    resp = authed_client.post(
        "/api/canvas/Bad_Name!/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {
            "code": "invalid_name",
            "message": "Name must match ^[a-z0-9][a-z0-9_-]{0,63}$",
        }
    }


def test_submit_malformed_body_422(authed_client, canvas_tmp_root):
    _open_decision()
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit", json={"value": "a"}
    )
    assert resp.status_code == 422


def test_submit_route_uses_event_constant():
    # Stitch 2: the route must publish via B1's events.CANVAS_DECISION_SUBMITTED
    # constant (b6c17c39), not a bare literal. The wire-string contract test
    # below stays literal — it pins the on-the-wire value the SPA depends on.
    import ast
    import inspect

    import spellbook.admin.routes.canvas as canvas_routes
    from spellbook.admin import events

    # The constant must be imported into the route module's namespace.
    assert (
        canvas_routes.CANVAS_DECISION_SUBMITTED
        is events.CANVAS_DECISION_SUBMITTED
    )

    # AST proof (replaces the three brittle ``not in src`` substring scans,
    # which a moved/renamed comment or a literal hiding in an unrelated string
    # could defeat): SOME ``Event(...)`` constructor in the route module passes
    # ``event_type=CANVAS_DECISION_SUBMITTED`` as a Name reference to the
    # constant, and NO ``Event(...)`` passes the bare wire literal there.
    tree = ast.parse(inspect.getsource(canvas_routes))
    event_type_kwargs = [
        kw.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Event"
        for kw in node.keywords
        if kw.arg == "event_type"
    ]
    assert any(
        isinstance(v, ast.Name) and v.id == "CANVAS_DECISION_SUBMITTED"
        for v in event_type_kwargs
    ), "route must pass event_type=CANVAS_DECISION_SUBMITTED (the constant)"
    assert not any(
        isinstance(v, ast.Constant) and v.value == "canvas.decision.submitted"
        for v in event_type_kwargs
    ), "route must not pass the bare 'canvas.decision.submitted' literal"


def test_submit_publishes_submitted_event(
    authed_client, canvas_tmp_root, event_subscriber
):
    # event_subscriber is the captured-publish LIST: it monkeypatches
    # event_bus.publish to append each Event (tests/canvas/conftest.py). The
    # sync TestClient.post drives the async route on the test loop; the route's
    # ``await event_bus.publish(...)`` appends synchronously, so after the POST
    # returns we read the list directly.
    from spellbook.admin import events

    _open_decision()
    resp = authed_client.post(
        "/api/canvas/plan-x/decision/submit",
        json={"decision_id": "d1", "value": "a"},
    )
    assert resp.status_code == 200
    # Exactly one event, fully specified: subsystem, type, data, and the
    # canvas-keyed routing fields (NEITHER session_id NOR namespace, finding #6).
    assert len(event_subscriber) == 1
    evt = event_subscriber[-1]
    assert evt.subsystem == events.Subsystem.CANVAS
    assert evt.event_type == "canvas.decision.submitted"
    assert evt.data == {"canvas": "plan-x", "decision_id": "d1", "value": "a"}
    assert evt.session_id is None
    assert evt.namespace is None
