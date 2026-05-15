"""WebSocket route tests: auth, event delivery, ping/pong."""

import asyncio

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from spellbook.admin.auth import create_ws_ticket
from spellbook.admin.events import Event, EventBus, Subsystem, event_bus


def test_ws_rejects_missing_ticket(admin_app):
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"})
    with pytest.raises(Exception):
        with client.websocket_connect("/ws"):
            pass


def test_ws_rejects_invalid_ticket(admin_app):
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"})
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?ticket=invalid-ticket"):
            pass


def test_ws_accepts_valid_ticket(admin_app, mock_mcp_token):
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"})
    ticket = create_ws_ticket()
    with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
        # Connection accepted -- send a pong to verify bidirectional
        ws.send_json({"type": "pong"})


def test_ws_ticket_single_use(admin_app, mock_mcp_token):
    """A WS ticket can only be used once."""
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"})
    ticket = create_ws_ticket()
    # First connection succeeds
    with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
        ws.send_json({"type": "pong"})
    # Second connection with same ticket should fail
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws?ticket={ticket}"):
            pass


def test_ws_receives_events(admin_app, mock_mcp_token):
    """Events published to the bus should appear on the WebSocket."""
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"})
    ticket = create_ws_ticket()
    with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
        # Publish an event to the bus
        import asyncio as _asyncio

        loop = _asyncio.new_event_loop()
        loop.run_until_complete(
            event_bus.publish(
                Event(
                    subsystem=Subsystem.MEMORY,
                    event_type="created",
                    data={"id": "mem-1"},
                )
            )
        )
        loop.close()

        # Read the event from WebSocket
        data = ws.receive_json()
        assert data["type"] == "event"
        assert data["subsystem"] == "memory"
        assert data["event"] == "created"
        assert data["data"]["id"] == "mem-1"
        assert "timestamp" in data


def test_ws_ticket_endpoint_requires_auth(admin_app):
    """POST /api/auth/ws-ticket requires session cookie."""
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:8765"})
    response = client.post("/api/auth/ws-ticket")
    assert response.status_code == 401


def test_ws_ticket_endpoint_returns_ticket(admin_app, mock_mcp_token, client):
    """POST /api/auth/ws-ticket returns a valid ticket."""
    response = client.post("/api/auth/ws-ticket")
    assert response.status_code == 200
    assert "ticket" in response.json()
    ticket = response.json()["ticket"]
    assert len(ticket) > 0


def test_ws_origin_mismatched_close_1008(admin_app, mock_mcp_token):
    """A WebSocket upgrade with a non-allowlisted Origin must be rejected.

    Defense-in-depth against cross-origin WebSocket hijack: the handler
    rejects (close code 1008, Policy Violation) any upgrade whose Origin
    is not in ``ws.app.state.allowed_origins``. Starlette converts
    ``close(1008)`` before ``accept()`` into HTTP 403 on the underlying
    transport, which surfaces to httpx as ``WebSocketDisconnect``.
    """
    # Construct a TestClient WITHOUT the default Origin header so the
    # per-call ``headers=`` kwarg is the only Origin the handler sees.
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765"})
    ticket = create_ws_ticket()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws?ticket={ticket}",
            headers={"Origin": "http://evil.com"},
        ) as ws:
            ws.receive_json()
    # 1008 if server closed cleanly before accept; 1006 if the transport
    # converted the pre-accept close into an abrupt disconnect.
    assert exc_info.value.code in (1008, 1006)


def test_ws_origin_missing_close_1008(admin_app, mock_mcp_token):
    """A WebSocket upgrade without an Origin header must be rejected.

    Non-browser clients that omit Origin are rejected by the same
    defense-in-depth check as mismatched origins.
    """
    # No Origin header at all: build a client whose only default header
    # is Host (HostValidator still requires a valid Host) and do not
    # add Origin per call.
    client = TestClient(admin_app, headers={"Host": "127.0.0.1:8765"})
    ticket = create_ws_ticket()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
            ws.receive_json()
    assert exc_info.value.code in (1008, 1006)
