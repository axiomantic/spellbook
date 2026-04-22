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


@pytest.fixture
def record_call_spy(monkeypatch):
    """Replace ``spellbook.worker_llm.observability.record_call`` with a spy
    that records every invocation into a list.

    The ``/api/events/publish`` route imports ``record_call`` inside the
    handler (``from spellbook.worker_llm.observability import record_call``),
    so we must patch the attribute on the ``observability`` module itself —
    the import binds the function object at call-time, not route-registration
    time, meaning the monkeypatched attribute IS the one the handler picks up.
    """
    from spellbook.worker_llm import observability

    calls: list[dict] = []

    def _spy(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(observability, "record_call", _spy)
    return calls


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
async def test_publish_route_routes_to_event_bus(mcp_http_app, record_call_spy):
    captured: list[Event] = []

    async def _capture_publish(evt):
        captured.append(evt)

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_capture_publish)

    transport = httpx.ASGITransport(app=mcp_http_app)
    payload_data = {
        "task": "t",
        "model": "m",
        "latency_ms": 42,
        "status": "success",
        "prompt_len": 0,
        "response_len": 0,
        "error": None,
        "override_loaded": False,
    }
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": "call_ok",
                    "data": payload_data,
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert len(captured) == 1
    evt = captured[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_ok"
    assert evt.data == payload_data


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
async def test_fallback_publisher_payload_reaches_mcp_root_route(
    mcp_http_app, record_call_spy,
):
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
            "status": "success",
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


@pytest.mark.asyncio
async def test_publish_route_call_ok_invokes_record_call(
    mcp_http_app, record_call_spy,
):
    """Happy path: a well-formed ``call_ok`` event triggers ``record_call``.

    ESCAPE: test_publish_route_call_ok_invokes_record_call
      CLAIM:    A valid worker_llm ``call_ok`` POST persists the call via
                ``record_call`` AND returns 200.
      PATH:     POST -> handler -> event_bus.publish -> validation ->
                record_call(task=..., model=..., ...).
      CHECK:    (a) status 200; (b) exactly one ``record_call`` invocation
                whose kwargs match every field of the payload ``data`` dict.
      MUTATION: If the route forgot to call record_call, the spy list is
                empty. If it dropped a kwarg (e.g. override_loaded), the
                full-equality kwargs check fails. If it misrouted to a
                different event_type's branch, the kwargs differ.
      ESCAPE:   A no-op wiring that only returns 200 is caught by the spy
                length check. A wiring that calls record_call with the
                wrong arg (e.g. task from a hard-coded string) is caught
                by the full-equality check.
      IMPACT:   Without this the subprocess path is silent — the design
                goal (subprocess calls land in worker_llm_calls) fails.
    """
    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_noop)

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
                    "data": {
                        "task": "transcript_harvest",
                        "model": "gpt-test",
                        "latency_ms": 321,
                        "status": "success",
                        "prompt_len": 10,
                        "response_len": 20,
                        "error": None,
                        "override_loaded": True,
                    },
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert record_call_spy == [
        {
            "task": "transcript_harvest",
            "model": "gpt-test",
            "latency_ms": 321,
            "status": "success",
            "prompt_len": 10,
            "response_len": 20,
            "error": None,
            "override_loaded": True,
        }
    ]


@pytest.mark.asyncio
async def test_publish_route_rejects_oversize_task(
    mcp_http_app, record_call_spy,
):
    """Oversize ``task`` (len 129) returns 400 and skips ``record_call``.

    ESCAPE: test_publish_route_rejects_oversize_task
      CLAIM:    ``task`` length > 128 triggers 400 with the "too long"
                message AND no row is written (record_call not invoked).
      PATH:     POST -> handler -> validation branch for len(task)>128.
      CHECK:    (a) status 400; (b) error body names the cap;
                (c) record_call spy remained empty.
      MUTATION: If the cap were missing (no length check), record_call
                would run and the spy would have one entry. If the cap
                were at the wrong boundary (e.g. >129), a 129-char task
                would pass and the spy would have one entry.
      ESCAPE:   A gate with inverted comparison (`< 128`) would still 400
                but on valid inputs; covered by the happy-path test above.
      IMPACT:   Without the cap, subprocess callers could poison the
                indexed ``task`` column with unbounded strings.
    """
    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_noop)

    transport = httpx.ASGITransport(app=mcp_http_app)
    oversize_task = "t" * 129
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": "call_ok",
                    "data": {
                        "task": oversize_task,
                        "model": "m",
                        "latency_ms": 1,
                        "status": "success",
                        "prompt_len": 0,
                        "response_len": 0,
                        "error": None,
                        "override_loaded": False,
                    },
                },
            )

    # The event still publishes (validation runs AFTER publish per design
    # §4.2: the event bus is fire-and-forget and observability is additive).
    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 400, r.text
    assert r.json() == {"error": "task/model too long (max 128 chars)"}
    assert record_call_spy == []


@pytest.mark.asyncio
async def test_publish_route_rejects_oversize_model(
    mcp_http_app, record_call_spy,
):
    """Oversize ``model`` (len 129) returns 400 and skips ``record_call``.

    ESCAPE: test_publish_route_rejects_oversize_model
      CLAIM:    ``model`` length > 128 triggers 400 AND record_call not
                invoked. Mirrors the task-cap test for the other indexed
                column.
      PATH:     POST -> handler -> validation branch for len(model)>128.
      CHECK:    (a) status 400; (b) error body; (c) spy empty.
      MUTATION: If the cap only checked ``task`` (copy/paste miss), an
                oversized model would pass and the spy would be non-empty.
      ESCAPE:   None specific beyond the mutation above.
      IMPACT:   Same as task: unbounded strings poison the observability
                column and bloat the DB file.
    """
    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_noop)

    transport = httpx.ASGITransport(app=mcp_http_app)
    oversize_model = "m" * 129
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": "call_ok",
                    "data": {
                        "task": "t",
                        "model": oversize_model,
                        "latency_ms": 1,
                        "status": "success",
                        "prompt_len": 0,
                        "response_len": 0,
                        "error": None,
                        "override_loaded": False,
                    },
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 400, r.text
    assert r.json() == {"error": "task/model too long (max 128 chars)"}
    assert record_call_spy == []


@pytest.mark.asyncio
async def test_publish_route_rejects_invalid_status(
    mcp_http_app, record_call_spy,
):
    """Unknown ``status`` value returns 400 and skips ``record_call``.

    ESCAPE: test_publish_route_rejects_invalid_status
      CLAIM:    A status outside {success, error, timeout, fail_open}
                produces 400 AND record_call not invoked.
      PATH:     POST -> handler -> validation branch for status not in enum.
      CHECK:    (a) status 400; (b) error body names the offending value;
                (c) spy empty.
      MUTATION: If the enum check were dropped, record_call would be called
                with arbitrary status strings, silently producing orphan
                rows that distort ``success_rate`` aggregates.
      ESCAPE:   A wider enum that accidentally admits "frobnozzle" would
                fail this test when the error body text is asserted.
      IMPACT:   Dashboard aggregates (success_rate, error_breakdown) become
                meaningless once arbitrary statuses land in the table.
    """
    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_noop)

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
                    "data": {
                        "task": "t",
                        "model": "m",
                        "latency_ms": 1,
                        "status": "frobnozzle",
                        "prompt_len": 0,
                        "response_len": 0,
                        "error": None,
                        "override_loaded": False,
                    },
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 400, r.text
    assert r.json() == {"error": "invalid status: 'frobnozzle'"}
    assert record_call_spy == []


@pytest.mark.asyncio
async def test_publish_route_call_fail_open_invokes_record_call(
    mcp_http_app, record_call_spy,
):
    """``call_fail_open`` events persist via ``record_call`` (fail-open path).

    ESCAPE: test_publish_route_call_fail_open_invokes_record_call
      CLAIM:    A valid worker_llm ``call_fail_open`` POST persists the call
                via ``record_call`` (status='fail_open') AND returns 200.
      PATH:     POST -> handler -> event_bus.publish -> validation ->
                record_call(...status='fail_open', error=<reason>).
      CHECK:    (a) status 200; (b) exactly one ``record_call`` invocation
                whose kwargs match the payload ``data`` dict (including a
                non-empty error string documenting the fail-open reason).
      MUTATION: If ``call_fail_open`` were dropped from the trigger set in
                ``spellbook/mcp/routes.py``, the spy would be empty and the
                len-1 assertion would fail. If the handler mis-routed to a
                different branch, kwargs would differ.
      ESCAPE:   A no-op wiring that only returns 200 is caught by the spy
                length check. A handler that preserves ``call_ok`` and
                ``call_failed`` but silently skips ``call_fail_open`` is
                caught here (and NOT by the non-call parametrize, which
                only covers event types that truly should skip record_call).
      IMPACT:   Fail-open calls (transport/parse errors the task recovered
                from via fallback) would be invisible in the observability
                table, breaking ``fail_open_rate`` aggregates.
    """
    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_noop)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": "call_fail_open",
                    "data": {
                        "task": "tool_safety",
                        "model": "gpt-test",
                        "latency_ms": 0,
                        "status": "fail_open",
                        "prompt_len": 0,
                        "response_len": 0,
                        "error": "parser_failure: could not parse verdict",
                        "override_loaded": False,
                    },
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert record_call_spy == [
        {
            "task": "tool_safety",
            "model": "gpt-test",
            "latency_ms": 0,
            "status": "fail_open",
            "prompt_len": 0,
            "response_len": 0,
            "error": "parser_failure: could not parse verdict",
            "override_loaded": False,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type",
    ["call_metrics", "override_loaded", "hook_integration"],
)
async def test_publish_route_non_call_event_types_skip_record_call(
    mcp_http_app, record_call_spy, event_type,
):
    """Non-call worker_llm events publish normally but never call record_call.

    ESCAPE: test_publish_route_non_call_event_types_skip_record_call
      CLAIM:    Event types outside {call_ok, call_failed, call_fail_open}
                are published to the event bus (200) but do NOT trigger
                ``record_call`` — those rows belong only to per-call
                outcomes, not summaries (``hook_integration``), overrides
                (``override_loaded``), or aggregates (``call_metrics``).
      PATH:     POST -> handler -> event_bus.publish -> skip record_call
                branch (event_type not in trigger set).
      CHECK:    (a) status 200; (b) event_bus.publish received the Event;
                (c) record_call spy is empty.
      MUTATION: If the trigger set were widened (e.g. {call_ok, *}), the
                spy would be non-empty for at least one of the three
                parametrized event types — covered by this parametrize.
                If the handler blindly called record_call for ALL
                worker_llm subsystem events, all three would fail.
      ESCAPE:   A handler that bails out on any event_type outside the
                call set (e.g. short-circuit 400) would fail the 200 check.
      IMPACT:   Without this gate, ``hook_integration`` summaries (which
                carry no ``status`` field) would either 400 (trigger enum
                rejection) or poison the table with rows whose columns
                come from the wrong event shape.
    """
    async def _noop(evt):
        return None

    publish_mock = bigfoot.mock.object(event_bus, "publish")
    publish_mock.calls(_noop)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with bigfoot:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.post(
                "/api/events/publish",
                json={
                    "subsystem": "worker_llm",
                    "event_type": event_type,
                    "data": {"task": "t"},
                },
            )

    publish_mock.assert_call(args=(IsInstance(Event),), kwargs={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert record_call_spy == []


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
