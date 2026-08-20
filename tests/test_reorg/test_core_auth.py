"""Tests for spellbook.core.auth: Origin/Host validation for the MCP transport.

The daemon binds loopback and has no credentials. The threat it defends against
is a web page the user visits issuing requests to 127.0.0.1, so the checks are
on Origin (present only on browser-issued cross-origin requests) and Host
(which carries the attacker's name under DNS rebinding).
"""

import pytest

from spellbook.core.auth import OriginValidationMiddleware, auth_is_disabled


async def _ok_app(scope, receive, send):
    """Terminal ASGI app: always 200."""
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": b"ok"})


async def drive(middleware, headers, path="/mcp"):
    """Drive an ASGI middleware once and return (status, body_bytes)."""
    scope = {
        "type": "http",
        "path": path,
        "method": "POST",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await middleware(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


@pytest.fixture
def app():
    return OriginValidationMiddleware(_ok_app)


# ---------------------------------------------------------------------------
# The four dispatched cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evil_origin_is_rejected(app):
    """A page on another site cannot drive the daemon."""
    status, body = await drive(app, {"Host": "127.0.0.1:8765", "Origin": "http://evil.com"})
    assert status == 403
    assert b"evil.com" not in body


@pytest.mark.asyncio
async def test_missing_origin_is_allowed(app):
    """Legitimate MCP clients (Claude Code, curl, pi) send no Origin."""
    status, _ = await drive(app, {"Host": "127.0.0.1:8765"})
    assert status == 200


@pytest.mark.asyncio
async def test_non_localhost_host_is_rejected(app):
    """A rebound DNS name arrives with the attacker's hostname in Host."""
    status, _ = await drive(app, {"Host": "attacker.example.com", "Origin": "http://localhost:3000"})
    assert status == 403


# ---------------------------------------------------------------------------
# Allowlist behaviour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://[::1]:8080",
        "https://localhost",
    ],
)
@pytest.mark.asyncio
async def test_loopback_origins_are_allowed(app, origin):
    """A browser MCP client served from the user's own machine is allowed."""
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": origin})
    assert status == 200


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost.evil.com",
        "http://evil.com/localhost",
        "null",
        "http://127.0.0.1.evil.com",
    ],
)
@pytest.mark.asyncio
async def test_lookalike_origins_are_rejected(app, origin):
    """Suffix/prefix tricks on a loopback name do not pass."""
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": origin})
    assert status == 403


@pytest.mark.asyncio
async def test_allowlist_is_configurable(monkeypatch):
    """SPELLBOOK_ALLOWED_ORIGINS admits a hosted browser client."""
    monkeypatch.setenv("SPELLBOOK_ALLOWED_ORIGINS", "https://mcp.example.com")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": "https://mcp.example.com"})
    assert status == 200


@pytest.mark.asyncio
async def test_configured_allowlist_still_rejects_others(monkeypatch):
    """Configuring an extra origin does not open the door generally."""
    monkeypatch.setenv("SPELLBOOK_ALLOWED_ORIGINS", "https://mcp.example.com")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": "http://evil.com"})
    assert status == 403


# ---------------------------------------------------------------------------
# Host handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765", "localhost", ""])
@pytest.mark.asyncio
async def test_loopback_hosts_are_allowed(app, host):
    status, _ = await drive(app, {"Host": host})
    assert status == 200


@pytest.mark.asyncio
async def test_configured_bind_host_is_allowed(monkeypatch):
    """Binding a non-loopback address must not lock the operator out."""
    monkeypatch.setenv("SPELLBOOK_HOST", "192.168.1.50")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "192.168.1.50:8765"})
    assert status == 200


@pytest.mark.asyncio
async def test_health_endpoint_still_validates_host(app):
    """/health skips nothing that closes rebinding."""
    status, _ = await drive(app, {"Host": "attacker.example.com"}, path="/health")
    assert status == 403


@pytest.mark.asyncio
async def test_health_endpoint_allowed_from_loopback(app):
    status, _ = await drive(app, {"Host": "127.0.0.1:8765"}, path="/health")
    assert status == 200


@pytest.mark.asyncio
async def test_non_http_scope_passes_through(app):
    """Lifespan and websocket scopes are not HTTP requests."""
    seen = []

    async def lifespan_app(scope, receive, send):
        seen.append(scope["type"])

    mw = OriginValidationMiddleware(lifespan_app)
    await mw({"type": "lifespan"}, None, None)
    assert seen == ["lifespan"]


@pytest.mark.asyncio
async def test_disabled_auth_skips_validation(monkeypatch):
    """The documented escape hatch still works."""
    monkeypatch.setenv("SPELLBOOK_AUTH", "disabled")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "attacker.example.com", "Origin": "http://evil.com"})
    assert status == 200


def test_auth_is_disabled_exists():
    assert callable(auth_is_disabled)


# ---------------------------------------------------------------------------
# The token is gone
# ---------------------------------------------------------------------------


def test_no_token_symbols_remain():
    """The bearer-token surface is removed, not merely unused."""
    import spellbook.core.auth as auth

    for name in ("BearerAuthMiddleware", "generate_and_store_token", "load_token", "TOKEN_PATH"):
        assert not hasattr(auth, name), f"{name} still present"
