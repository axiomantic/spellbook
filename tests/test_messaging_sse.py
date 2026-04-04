"""Tests for the SSE messaging endpoint.

Tests: event streaming for registered session, unregistered session returns
404, heartbeat delivery, disconnect sentinel terminates stream, health
endpoint returns JSON.
"""

import asyncio
import json

import httpx
import pytest

from spellbook.messaging.bus import MessageBus, _DISCONNECT
from spellbook.messaging import sse as sse_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bus():
    """Fresh MessageBus instance per test (not the singleton)."""
    return MessageBus(queue_size=16)


@pytest.fixture
def patched_bus(bus, monkeypatch):
    """Replace the singleton message_bus in sse module with the test bus."""
    monkeypatch.setattr(sse_module, "message_bus", bus)
    return bus


@pytest.fixture
def sse_client(patched_bus):
    """httpx AsyncClient pointing at the SSE app with bus mocked."""
    app = sse_module.create_messaging_app()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Health Endpoint
# ---------------------------------------------------------------------------


class TestSSEHealth:
    @pytest.mark.asyncio
    async def test_health_returns_json(self, sse_client):
        async with sse_client:
            resp = await sse_client.get("/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Unregistered Session
# ---------------------------------------------------------------------------


class TestSSEUnregistered:
    @pytest.mark.asyncio
    async def test_unregistered_session_returns_404(self, sse_client):
        """GET /stream/<unknown-alias> returns 404 with error JSON."""
        async with sse_client:
            resp = await sse_client.get("/stream/nonexistent")

        assert resp.status_code == 404
        assert resp.json() == {"error": "not_registered", "alias": "nonexistent"}


# ---------------------------------------------------------------------------
# Event Streaming
# ---------------------------------------------------------------------------


class TestSSEStreaming:
    @pytest.mark.asyncio
    async def test_stream_delivers_message_then_disconnect(self, patched_bus, sse_client):
        """Register session, enqueue a message + disconnect sentinel, verify SSE output."""
        await patched_bus.register("sse-recv", enable_sse=False)
        await patched_bus.register("sse-send", enable_sse=False)
        await patched_bus.send("sse-send", "sse-recv", {"via": "sse"})

        # Put disconnect sentinel so stream terminates after the message
        queue = await patched_bus.get_queue("sse-recv")
        await queue.put(_DISCONNECT)

        async with sse_client:
            resp = await sse_client.get("/stream/sse-recv")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE data lines
        lines = resp.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) == 1

        payload = json.loads(data_lines[0][len("data: "):])
        assert payload["sender"] == "sse-send"
        assert payload["recipient"] == "sse-recv"
        assert payload["payload"] == {"via": "sse"}
        assert payload["message_type"] == "direct"

        # Verify SSE event format includes id: and event: lines
        id_lines = [l for l in lines if l.startswith("id: ")]
        event_lines = [l for l in lines if l.startswith("event: ")]
        assert len(id_lines) == 1
        assert event_lines == ["event: message"]

    @pytest.mark.asyncio
    async def test_disconnect_sentinel_terminates_stream(self, patched_bus, sse_client):
        """A queue containing only _DISCONNECT produces no data lines."""
        await patched_bus.register("dc-only", enable_sse=False)
        queue = await patched_bus.get_queue("dc-only")
        await queue.put(_DISCONNECT)

        async with sse_client:
            resp = await sse_client.get("/stream/dc-only")

        assert resp.status_code == 200
        lines = resp.text.strip().split("\n") if resp.text.strip() else []
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert data_lines == []


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class TestSSEHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_sent_on_timeout(self, patched_bus, monkeypatch):
        """When queue is idle past heartbeat interval, a heartbeat comment is sent."""
        await patched_bus.register("hb-session", enable_sse=False)

        # Override HEARTBEAT_INTERVAL to something very short so the test
        # doesn't wait 15 seconds.
        monkeypatch.setattr(sse_module, "HEARTBEAT_INTERVAL", 0.1)

        async def _feed_disconnect_after_delay():
            await asyncio.sleep(0.3)
            q = await patched_bus.get_queue("hb-session")
            await q.put(_DISCONNECT)

        app = sse_module.create_messaging_app()
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

        task = asyncio.create_task(_feed_disconnect_after_delay())
        async with client:
            resp = await client.get("/stream/hb-session")
        await task

        assert resp.status_code == 200
        # Heartbeat is a SSE comment line starting with ":"
        lines = resp.text.split("\n")
        heartbeat_lines = [l for l in lines if l.startswith(": heartbeat")]
        assert len(heartbeat_lines) >= 1


# ---------------------------------------------------------------------------
# Multiple Messages
# ---------------------------------------------------------------------------


class TestSSEMultipleMessages:
    @pytest.mark.asyncio
    async def test_stream_delivers_multiple_messages(self, patched_bus, sse_client):
        """Multiple messages queued before stream starts are all delivered."""
        await patched_bus.register("multi-recv", enable_sse=False)
        await patched_bus.register("multi-send", enable_sse=False)
        await patched_bus.send("multi-send", "multi-recv", {"seq": 1})
        await patched_bus.send("multi-send", "multi-recv", {"seq": 2})
        await patched_bus.send("multi-send", "multi-recv", {"seq": 3})

        queue = await patched_bus.get_queue("multi-recv")
        await queue.put(_DISCONNECT)

        async with sse_client:
            resp = await sse_client.get("/stream/multi-recv")

        data_lines = [l for l in resp.text.split("\n") if l.startswith("data: ")]
        assert len(data_lines) == 3

        payloads = [json.loads(l[len("data: "):]) for l in data_lines]
        assert payloads[0]["payload"] == {"seq": 1}
        assert payloads[1]["payload"] == {"seq": 2}
        assert payloads[2]["payload"] == {"seq": 3}
