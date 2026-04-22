"""Tests for ``POST /api/worker-llm/enqueue`` on the MCP server root.

Mirrors ``test_events_publish_route.py``: builds the real MCP Starlette
app, wires an ``ASGITransport``, and drives the endpoint with
``httpx.AsyncClient``.

The tests monkeypatch the queue module helpers (``is_available``,
``enqueue``) at the route's import time so we exercise the route's
wiring without a live daemon loop.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
def mcp_http_app():
    """Construct the real MCP server Starlette app (root routes + /admin mount).

    Idempotent: resets the ``_additional_http_routes`` /admin entry so
    repeated test runs inside a single interpreter do not stack mounts.
    """
    from spellbook.mcp.server import mcp, _mount_admin_app
    import spellbook.mcp.routes  # noqa: F401  -- registers @mcp.custom_route handlers

    mcp._additional_http_routes = [
        r for r in mcp._additional_http_routes
        if getattr(r, "path", None) != "/admin"
    ]
    _mount_admin_app()
    return mcp.http_app()


@pytest.fixture
def queue_enabled_and_running(monkeypatch):
    """Patch config to report queue-enabled and install a fake ``enqueue``.

    The route pulls ``config_get`` and ``queue`` via late imports, so we
    patch the source modules.
    """
    from spellbook.core import config as _cfg
    from spellbook.worker_llm import queue as _queue

    monkeypatch.setattr(
        _cfg,
        "config_get",
        lambda k: True if k == "worker_llm_queue_enabled" else None,
    )
    monkeypatch.setattr(_queue, "is_available", lambda: True)

    calls: list[dict] = []

    async def _fake_enqueue(task_name, prompt, callback=None, context=None):
        calls.append(
            {
                "task_name": task_name,
                "prompt": prompt,
                "callback": callback,
                "context": context,
            }
        )
        return True  # queued, no drop

    monkeypatch.setattr(_queue, "enqueue", _fake_enqueue)
    return calls


@pytest.mark.asyncio
async def test_enqueue_route_accepts_valid_payload(
    mcp_http_app, queue_enabled_and_running
):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={
                "task_name": "transcript_harvest",
                "prompt": "some body",
                "context": {"namespace": "proj", "branch": "main"},
            },
        )
    assert r.status_code == 202, r.text
    assert r.json() == {"ok": True, "dropped": False}
    assert len(queue_enabled_and_running) == 1
    assert queue_enabled_and_running[0]["task_name"] == "transcript_harvest"
    assert queue_enabled_and_running[0]["prompt"] == "some body"
    assert queue_enabled_and_running[0]["context"] == {
        "namespace": "proj",
        "branch": "main",
    }


@pytest.mark.asyncio
async def test_enqueue_route_reports_dropped_when_eviction_occurs(
    mcp_http_app, monkeypatch
):
    from spellbook.core import config as _cfg
    from spellbook.worker_llm import queue as _queue

    monkeypatch.setattr(
        _cfg,
        "config_get",
        lambda k: True if k == "worker_llm_queue_enabled" else None,
    )
    monkeypatch.setattr(_queue, "is_available", lambda: True)

    async def _fake_enqueue(task_name, prompt, callback=None, context=None):
        return False  # drop-oldest fired

    monkeypatch.setattr(_queue, "enqueue", _fake_enqueue)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={"task_name": "transcript_harvest", "prompt": "x"},
        )
    assert r.status_code == 202
    assert r.json() == {"ok": True, "dropped": True}


@pytest.mark.asyncio
async def test_enqueue_route_503_when_feature_disabled(mcp_http_app, monkeypatch):
    from spellbook.core import config as _cfg

    monkeypatch.setattr(_cfg, "config_get", lambda k: False)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={"task_name": "transcript_harvest", "prompt": "x"},
        )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_enqueue_route_503_when_queue_not_running(mcp_http_app, monkeypatch):
    from spellbook.core import config as _cfg
    from spellbook.worker_llm import queue as _queue

    monkeypatch.setattr(
        _cfg,
        "config_get",
        lambda k: True if k == "worker_llm_queue_enabled" else None,
    )
    monkeypatch.setattr(_queue, "is_available", lambda: False)

    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={"task_name": "transcript_harvest", "prompt": "x"},
        )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_enqueue_route_rejects_missing_task_name(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={"prompt": "x"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_enqueue_route_rejects_missing_prompt(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={"task_name": "transcript_harvest"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_enqueue_route_rejects_non_dict_context(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            json={
                "task_name": "transcript_harvest",
                "prompt": "x",
                "context": "not-a-dict",
            },
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_enqueue_route_rejects_invalid_json(mcp_http_app):
    transport = httpx.ASGITransport(app=mcp_http_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        r = await client.post(
            "/api/worker-llm/enqueue",
            content=b"{ not json",
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 400
