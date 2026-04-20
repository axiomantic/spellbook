"""Tests for ``POST /api/events/publish`` on the MCP server root.

These tests exercise the ACTUAL mount layout the daemon ships: the admin
FastAPI app is mounted under ``/admin`` inside the MCP server, and the
event-publish endpoint lives at the MCP root so ``BearerAuthMiddleware``
covers it -- exactly like ``/api/hook-log``.

The older admin-scoped ``/admin/api/events/publish`` route was removed along
with ``EventPublishBody`` in the C1 fix; this suite also guards against a
regression where the route drifts back under ``/admin``.
"""

from __future__ import annotations

import bigfoot
import httpx
import pytest
from dirty_equals import IsInstance

from spellbook.admin.events import Event, Subsystem, event_bus


@pytest.fixture
def mcp_http_app():
    """Construct the real MCP server Starlette app (root routes + /admin mount)."""
    from spellbook.mcp.server import mcp, _mount_admin_app
    import spellbook.mcp.routes  # noqa: F401  -- registers @mcp.custom_route handlers

    # Idempotent: _mount_admin_app appends to _additional_http_routes.
    # Ensure the /admin mount is present exactly once.
    mcp._additional_http_routes = [
        r for r in mcp._additional_http_routes
        if getattr(r, "path", None) != "/admin"
    ]
    _mount_admin_app()
    return mcp.http_app()


def test_publish_route_registered_at_root_not_under_admin(mcp_http_app):
    """Regression guard: the publish route MUST live at /api/events/publish.

    If someone reintroduces the admin-mounted variant, the real path becomes
    /admin/api/events/publish and subprocess clients silently 404. Catch that
    here.
    """
    paths = [getattr(r, "path", "") for r in mcp_http_app.router.routes]
    assert "/api/events/publish" in paths
    # And the /admin mount is still present
    assert "/admin" in paths


@pytest.mark.asyncio
async def test_publish_route_routes_to_event_bus(mcp_http_app):
    captured: list[Event] = []

    async def _capture_publish(evt):
        captured.append(evt)

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_capture_publish)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": "call_ok",
                    "data": {"task": "t", "latency_ms": 42},
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert len(captured) == 1
    evt = captured[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_ok"
    assert evt.data == {"task": "t", "latency_ms": 42}


@pytest.mark.asyncio
async def test_publish_route_accepts_every_known_subsystem(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)

    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    # One .calls() per expected invocation; bigfoot pops from a FIFO queue.
    for _ in Subsystem:
        publish_mock.calls(_noop)

    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            for subsystem in Subsystem:
                r = await client.post(
                    "/api/events/publish",
                    json={
                        "subsystem": subsystem.value,
                        "event_type": "probe",
                        "data": {},
                    },
                )
                assert r.status_code == 200, (subsystem, r.text)

    with bigfoot.in_any_order():
        for _ in Subsystem:
            publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})


@pytest.mark.asyncio
async def test_publish_route_rejects_unknown_subsystem(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/events/publish",
            json={
                "subsystem": "not_a_real_subsystem",
                "event_type": "x",
                "data": {},
            },
        )

    assert r.status_code == 400
    assert "unknown subsystem" in r.json()["error"]


@pytest.mark.asyncio
async def test_publish_route_rejects_missing_fields(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/events/publish",
            json={"subsystem": "worker_llm"},  # missing event_type, data
        )

    assert r.status_code == 400
    body = r.json()
    assert "missing required fields" in body["error"]
    assert "event_type" in body["error"]
    assert "data" in body["error"]


@pytest.mark.asyncio
async def test_publish_route_rejects_non_dict_data(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/events/publish",
            json={
                "subsystem": "worker_llm",
                "event_type": "call_ok",
                "data": "not a dict",
            },
        )

    assert r.status_code == 400
    assert r.json() == {"error": "field 'data' must be an object"}


@pytest.mark.asyncio
async def test_publish_route_rejects_invalid_json(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/events/publish",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 400
    assert r.json() == {"error": "invalid JSON"}


@pytest.mark.asyncio
async def test_fallback_publisher_payload_reaches_mcp_root_route(mcp_http_app):
    """End-to-end: the payload shape produced by
    ``spellbook.worker_llm.events.publish_call`` is accepted by the real
    ``/api/events/publish`` handler on the composed MCP app.

    This is the regression-shaped test for review finding C1: if the route
    moves back under ``/admin`` (the pre-fix path) the POST here will 404.
    """
    # Build the exact payload publish_call would POST.
    payload = {
        "subsystem": "worker_llm",
        "event_type": "call_ok",
        "data": {
            "task": "t",
            "model": "m",
            "latency_ms": 1,
            "status": "ok",
            "prompt_len": 1,
            "response_len": 1,
            "error": None,
            "override_loaded": False,
        },
    }

    captured_events: list[Event] = []

    async def _fake_publish(evt):
        captured_events.append(evt)

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_fake_publish)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post("/api/events/publish", json=payload)

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert len(captured_events) == 1
    evt = captured_events[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_ok"
    assert evt.data == payload["data"]


@pytest.mark.asyncio
async def test_admin_scoped_publish_path_is_gone(mcp_http_app):
    """Hard guard: ``/admin/api/events/publish`` (the old, broken path) must
    not resolve to a publish handler. Before C1 the admin-mounted route
    existed here and silently accepted calls that worker_llm subprocesses
    were never pointed at.
    """
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/admin/api/events/publish",
            json={"subsystem": "worker_llm", "event_type": "x", "data": {}},
        )

    # The admin SPA catch-all returns the index page (200) for any unknown
    # path. The important assertion is that this path did NOT behave like a
    # real publish route (i.e., did not return our {"ok": true} shape).
    if r.status_code == 200:
        assert r.json() != {"ok": True} if r.headers.get(
            "content-type", ""
        ).startswith("application/json") else True
    else:
        assert r.status_code in (404, 405)


def test_lifespan_sets_event_bus_in_daemon_true():
    """The admin FastAPI sub-app's lifespan still flips the daemon marker.

    Kept from the old test file so we don't lose coverage of the
    ``_in_daemon`` contract that worker_llm.events relies on.
    """
    from fastapi.testclient import TestClient

    from spellbook.admin.app import create_admin_app

    app = create_admin_app()
    assert event_bus._in_daemon is False
    with TestClient(app):
        assert event_bus._in_daemon is True
    assert event_bus._in_daemon is False
