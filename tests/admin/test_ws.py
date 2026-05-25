"""WebSocket route tests: auth, event delivery, ping/pong."""


import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from spellbook.admin.auth import create_ws_ticket
from spellbook.admin.events import Event, Subsystem, event_bus


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
                    subsystem=Subsystem.CONFIG,
                    event_type="created",
                    data={"id": "cfg-1"},
                )
            )
        )
        loop.close()

        # Read the event from WebSocket
        data = ws.receive_json()
        assert data["type"] == "event"
        assert data["subsystem"] == "config"
        assert data["event"] == "created"
        assert data["data"]["id"] == "cfg-1"
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


# --- HostValidatorMiddleware: WebSocket rejection path (BOT-E1) ---
#
# HTTP coverage for HostValidatorMiddleware lives in
# tests/admin/test_host_validator.py, but the middleware also gates the
# ``websocket`` scope (spellbook/admin/middleware.py:65). On a Host mismatch
# the middleware emits ``websocket.close`` with code 1008 BEFORE
# ``websocket.accept``; Starlette translates a pre-accept close into HTTP
# 403 on the upgrade response, which the TestClient surfaces as
# ``WebSocketDisconnect`` (code 1008 if the server close races ahead, 1006
# if the transport collapses the close into an abrupt disconnect). The
# tests below pin that behavior; they mirror the surface idiom used by
# ``test_ws_origin_mismatched_close_1008`` above.

_NON_LOOPBACK_HOSTS: list[tuple[str, str]] = [
    ("evil.example.com", "non-loopback bare"),
    ("example.com:8765", "non-loopback with port"),
    ("attacker.test", "attacker tld"),
    ("127.0.0.1.evil.com", "loopback-prefixed suffix attack"),
]


@pytest.mark.parametrize(
    "bad_host,description",
    _NON_LOOPBACK_HOSTS,
    ids=[c[1] for c in _NON_LOOPBACK_HOSTS],
)
def test_ws_host_rejected_before_accept(
    admin_app, mock_mcp_token, bad_host, description
):
    """A WebSocket upgrade with a non-loopback Host must be rejected by
    HostValidatorMiddleware BEFORE ``websocket.accept``.

    Defense against DNS rebinding on the WS upgrade: even with a valid
    Origin and a valid ticket, a Host header outside the
    ``[127.0.0.1, localhost, ::1]`` allowlist must terminate the upgrade
    at the middleware layer (close code 1008, pre-accept, translated by
    Starlette to HTTP 403). The presence of a valid ticket here is
    deliberate: it isolates the Host check as the only thing that can
    reject this connection, so an accidental loosening of HostValidator
    would let the connection proceed and the test would fail.
    """
    # Per-call ``headers={"Host": ...}`` is the only Host the handler sees.
    client = TestClient(
        admin_app, headers={"Origin": "http://127.0.0.1:8765"}
    )
    ticket = create_ws_ticket()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws?ticket={ticket}",
            headers={"Host": bad_host},
        ) as ws:
            ws.receive_json()
    # 1008 when the server's pre-accept close reaches the client cleanly;
    # 1006 when the transport collapses it into an abrupt disconnect.
    assert exc_info.value.code in (1008, 1006), (
        f"{description}: Host={bad_host!r} expected close 1008/1006, "
        f"got {exc_info.value.code}"
    )


def test_ws_host_empty_rejected_before_accept(admin_app, mock_mcp_token):
    """An empty Host header on WS upgrade is rejected.

    ``HostValidatorMiddleware._extract_hostname`` returns ``""`` for empty
    or whitespace-only input, which can never match the (non-empty)
    allowlist, so the upgrade is closed pre-accept just like a non-loopback
    Host. We pass a single-space string because some HTTP stacks
    drop entirely-empty headers; ``" "`` survives transport and exercises
    the strip-to-empty branch of ``_extract_hostname``.
    """
    client = TestClient(
        admin_app, headers={"Origin": "http://127.0.0.1:8765"}
    )
    ticket = create_ws_ticket()
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws?ticket={ticket}",
            headers={"Host": " "},
        ) as ws:
            ws.receive_json()
    assert exc_info.value.code in (1008, 1006)


_LOOPBACK_HOSTS: list[tuple[str, str]] = [
    ("127.0.0.1:8765", "ipv4 loopback with port"),
    ("localhost:8765", "localhost with port"),
    ("[::1]:8765", "ipv6 loopback with port"),
]


@pytest.mark.parametrize(
    "good_host,description",
    _LOOPBACK_HOSTS,
    ids=[c[1] for c in _LOOPBACK_HOSTS],
)
def test_ws_host_loopback_passes_host_validator(
    admin_app, mock_mcp_token, good_host, description
):
    """Each loopback Host variant passes HostValidatorMiddleware on WS.

    With a valid ticket and Origin in place, a loopback Host MUST allow
    the upgrade to reach the WS handler and accept. Asserts a successful
    accept by sending a frame on the open socket; if HostValidator
    rejected the loopback variant (regression), ``websocket_connect``
    would raise ``WebSocketDisconnect`` instead.
    """
    client = TestClient(
        admin_app, headers={"Origin": "http://127.0.0.1:8765"}
    )
    ticket = create_ws_ticket()
    with client.websocket_connect(
        f"/ws?ticket={ticket}",
        headers={"Host": good_host},
    ) as ws:
        # Successful accept; send a pong to confirm the socket is open.
        ws.send_json({"type": "pong"})
