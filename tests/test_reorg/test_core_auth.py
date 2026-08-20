"""Tests for spellbook.core.auth: Origin/Host validation for the MCP transport.

The daemon binds loopback and has no credentials. The threat it defends against
is a web page the user visits issuing requests to 127.0.0.1, so the checks are
on Origin (present only on browser-issued cross-origin requests) and Host
(which carries the attacker's name under DNS rebinding).
"""

import logging

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


async def drive_raw(middleware, raw_headers, path="/mcp"):
    """Drive an ASGI middleware with a raw header list.

    A dict cannot express a repeated header or a name whose case the ASGI
    server did not fold, and both are exactly what the smuggling cases need.
    """
    scope = {
        "type": "http",
        "path": path,
        "method": "POST",
        "headers": [(k.encode(), v.encode()) for k, v in raw_headers],
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


async def drive_bytes(middleware, raw_headers, path="/mcp"):
    """Drive an ASGI middleware with header values that are already bytes.

    ASGI header values are bytes and need not be valid UTF-8; drive_raw() takes
    str and so cannot express a value that fails to decode.
    """
    scope = {
        "type": "http",
        "path": path,
        "method": "POST",
        "headers": list(raw_headers),
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
    ["http://localhost:8765", "http://127.0.0.1:8765", "http://[::1]:8765"],
)
@pytest.mark.asyncio
async def test_daemon_own_origin_is_allowed(app, origin):
    """The daemon's own origin -- its scheme, its host, its port -- is allowed."""
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": origin})
    assert status == 200


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://[::1]:8080",
        "https://localhost",
        "https://localhost:8765",
        "http://localhost",
    ],
)
@pytest.mark.asyncio
async def test_loopback_on_another_origin_is_rejected(app, origin):
    """Being local buys nothing: a different port or scheme is a different origin.

    A local browser client must be named in SPELLBOOK_ALLOWED_ORIGINS.
    """
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": origin})
    assert status == 403


@pytest.mark.asyncio
async def test_local_browser_client_via_allowlist(monkeypatch):
    """The documented way back to a local browser client on another port."""
    monkeypatch.setenv("SPELLBOOK_ALLOWED_ORIGINS", "http://localhost:3000")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "127.0.0.1:8765", "Origin": "http://localhost:3000"})
    assert status == 200


# ---------------------------------------------------------------------------
# Duplicate headers and header-name case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origins",
    [
        ["http://localhost:8765", "http://evil.com"],
        ["http://evil.com", "http://localhost:8765"],
    ],
    ids=["benign-first", "hostile-first"],
)
@pytest.mark.asyncio
async def test_duplicate_origin_is_rejected(app, origins):
    """Neither first-wins nor last-wins is safe, so two Origins are refused.

    Picking either one only chooses which smuggling direction succeeds.
    """
    headers = [("host", "127.0.0.1:8765")] + [("origin", o) for o in origins]
    status, body = await drive_raw(app, headers)
    assert status == 403
    assert b"duplicate Origin" in body


@pytest.mark.asyncio
async def test_duplicate_host_is_rejected(app):
    """Same reasoning applies to a repeated Host."""
    headers = [("host", "127.0.0.1:8765"), ("host", "attacker.example.com")]
    status, body = await drive_raw(app, headers)
    assert status == 403
    assert b"duplicate Host" in body


@pytest.mark.asyncio
async def test_header_names_are_matched_case_insensitively(app):
    """The check must not depend on the server having lowercased header names."""
    headers = [("Host", "127.0.0.1:8765"), ("Origin", "http://evil.com")]
    status, _ = await drive_raw(app, headers)
    assert status == 403


@pytest.mark.asyncio
async def test_mixed_case_host_is_still_checked(app):
    """An unfolded Host name must not slip the rebinding check."""
    status, body = await drive_raw(app, [("HOST", "attacker.example.com")])
    assert status == 403
    assert b"Host" in body


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
    """A bind address that is also a reachable name is allowed under that name."""
    monkeypatch.setenv("SPELLBOOK_HOST", "192.168.1.50")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "192.168.1.50:8765"})
    assert status == 200


@pytest.mark.parametrize("bind", ["0.0.0.0", "::"])
@pytest.mark.parametrize(
    "host", ["192.168.1.5:8765", "myhost.local:8765", "0.0.0.0:8765", "[::]:8765"]
)
@pytest.mark.asyncio
async def test_wildcard_bind_rejects_remote_hosts(monkeypatch, bind, host):
    """A wildcard bind fails CLOSED, and that is the intended behaviour.

    "0.0.0.0" is a bind address, not a reachable name: a LAN client sends the
    address or name it dialed ("Host: 192.168.1.5:8765"). So under a wildcard
    bind only the loopback Host values remain allowed and every remote client
    is refused.

    "0.0.0.0:8765" is in the params on purpose. It is the one value the claim
    above is actually about, and the one the code got wrong: _hostname_of
    parses "0.0.0.0" to the truthy hostname "0.0.0.0", which was then added to
    the allowed set and admitted, while "::" yields None and disappeared on its
    own. Two values the same sentence described, behaving differently.

    This is pinned deliberately. The daemon is a local-only service; remote
    access is out of scope, and SPELLBOOK_AUTH=disabled is the only supported
    way to run that configuration. Do not "fix" this by widening the allowed
    hostnames -- that would reopen the DNS-rebinding path this module closes.

    test_configured_bind_host_is_allowed above uses 192.168.1.50, a bind value
    that happens to also be a reachable name, so it cannot see this case.
    """
    monkeypatch.setenv("SPELLBOOK_HOST", bind)
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": host})
    assert status == 403


@pytest.mark.asyncio
async def test_wildcard_bind_still_serves_loopback(monkeypatch):
    """The negative half: a wildcard bind does not lock out the local client."""
    monkeypatch.setenv("SPELLBOOK_HOST", "0.0.0.0")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "127.0.0.1:8765"})
    assert status == 200


@pytest.mark.asyncio
async def test_host_userinfo_does_not_smuggle_a_hostname():
    """urlsplit reads userinfo; a Host header has no such field.

    "evil.com@localhost" parses to hostname "localhost" and would otherwise be
    admitted under the attacker's own name.
    """
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "evil.com@localhost:8765"})
    assert status == 403


@pytest.mark.asyncio
async def test_origin_userinfo_does_not_smuggle_a_hostname():
    """The same guard on the Origin side.

    A browser strips userinfo when it serializes an Origin, so this is not
    browser-reachable -- but the two paths resolving one ambiguity in opposite
    directions is how the Host case survived.
    """
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(
        app,
        {"Host": "127.0.0.1:8765", "Origin": "http://evil.com@localhost:8765"},
    )
    assert status == 403


# ---------------------------------------------------------------------------
# Unparseable port: an unknown self-origin trusts nothing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    ["http://localhost", "http://127.0.0.1", "http://localhost:8765"],
)
@pytest.mark.asyncio
async def test_unparseable_port_trusts_no_origin(monkeypatch, origin):
    """A None port would compare equal to a port-less Origin.

    http://localhost is port 80 -- any local web server. It must not inherit the
    daemon's own trust just because the daemon's port could not be parsed.

    Only the port-less params discriminate: "http://localhost:8765" was refused
    by the old code too, since 8765 never equalled the None port. It is kept to
    record what failing closed costs -- with the port unknown, even the real
    daemon origin is refused -- not as evidence of the fix.
    """
    monkeypatch.setenv("SPELLBOOK_PORT", "not-a-port")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "127.0.0.1", "Origin": origin})
    assert status == 403


@pytest.mark.asyncio
async def test_unparseable_port_still_allows_explicit_allowlist(monkeypatch):
    """Failing closed on the self-origin does not disable the allowlist."""
    monkeypatch.setenv("SPELLBOOK_PORT", "not-a-port")
    monkeypatch.setenv("SPELLBOOK_ALLOWED_ORIGINS", "http://localhost:3000")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "127.0.0.1", "Origin": "http://localhost:3000"})
    assert status == 200


@pytest.mark.parametrize("header", ["origin", "host"])
@pytest.mark.asyncio
async def test_undecodable_header_bytes_are_rejected(header):
    """Two distinct byte strings must not map onto one allowed value.

    errors="ignore" dropped the invalid byte, so b"http://local\\xffhost:8765"
    decoded to the daemon's own origin.
    """
    app = OriginValidationMiddleware(_ok_app)
    if header == "origin":
        raw = [(b"host", b"127.0.0.1:8765"), (b"origin", b"http://local\xffhost:8765")]
    else:
        raw = [(b"host", b"local\xffhost:8765")]
    status, _ = await drive_bytes(app, raw)
    assert status == 403


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
async def test_lifespan_scope_passes_through(app):
    """A lifespan scope is not a request and carries no headers to check."""
    seen = []

    async def lifespan_app(scope, receive, send):
        seen.append(scope["type"])

    mw = OriginValidationMiddleware(lifespan_app)
    await mw({"type": "lifespan"}, None, None)
    assert seen == ["lifespan"]


def test_configured_app_has_no_websocket_route():
    """The precondition that makes the scope skip safe.

    __call__ skips every non-"http" scope, so a "websocket" scope reaches the
    inner app unchecked. That is safe only while no websocket route exists: a
    browser may open ws:// to loopback cross-origin with no CORS preflight and
    no Origin enforcement of its own, so a ws route would be reachable from any
    page the user visits.

    Builds the real configured app the way spellbook/mcp/__main__.py does, not
    a stand-in. If a WebSocketRoute is ever added, this test goes red and the
    skip in __call__ must be narrowed before it can go green again.
    """
    from starlette.middleware import Middleware
    from starlette.routing import WebSocketRoute

    from spellbook.mcp.server import mcp, register_all_tools

    register_all_tools()
    app = mcp.http_app(
        stateless_http=True,
        middleware=[Middleware(OriginValidationMiddleware)],
    )

    def walk(routes):
        for route in routes:
            yield route
            yield from walk(getattr(route, "routes", None) or [])

    found = [r for r in walk(app.routes) if isinstance(r, WebSocketRoute)]
    assert found == [], f"websocket routes bypass Origin validation: {found}"


@pytest.mark.asyncio
async def test_disabled_auth_skips_validation(monkeypatch):
    """The documented escape hatch still works."""
    monkeypatch.setenv("SPELLBOOK_AUTH", "disabled")
    app = OriginValidationMiddleware(_ok_app)
    status, _ = await drive(app, {"Host": "attacker.example.com", "Origin": "http://evil.com"})
    assert status == 200


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("disabled", True),
        ("DISABLED", True),
        ("Disabled", True),
        (" disabled ", False),
        ("enabled", False),
        ("0", False),
        ("false", False),
        ("", False),
        (None, False),
    ],
)
def test_auth_is_disabled_reads_the_value(monkeypatch, value, expected):
    """Pins the values, not the signature.

    An assertion that auth_is_disabled is callable passes against
    ``def auth_is_disabled(): return True`` -- which disables validation
    everywhere.

    " disabled " is False on purpose: the value is compared unstripped, so a
    padded value leaves validation ON. That is the safe direction, and pinning
    it keeps a later "tidy-up" from silently turning it into a bypass.
    """
    monkeypatch.delenv("SPELLBOOK_MCP_AUTH", raising=False)
    if value is None:
        monkeypatch.delenv("SPELLBOOK_AUTH", raising=False)
    else:
        monkeypatch.setenv("SPELLBOOK_AUTH", value)

    assert auth_is_disabled() is expected


# ---------------------------------------------------------------------------
# The token is gone
# ---------------------------------------------------------------------------


def test_no_token_symbols_remain():
    """The bearer-token surface is removed, not merely unused."""
    import spellbook.core.auth as auth

    for name in ("BearerAuthMiddleware", "generate_and_store_token", "load_token", "TOKEN_PATH"):
        assert not hasattr(auth, name), f"{name} still present"


# ---------------------------------------------------------------------------
# The disabled state must announce itself
#
# test_disabled_auth_skips_validation above proves the bypass WORKS. That is
# only half the contract: a bypass that works silently is the dangerous half.
# The banner once derived its text from whether the run kwargs carried a
# middleware list, which is always non-empty, so SPELLBOOK_AUTH=disabled
# printed "auth enabled" and logged nothing at all.
# ---------------------------------------------------------------------------


def test_disabled_auth_logs_a_warning(monkeypatch, caplog):
    from spellbook.mcp.server import (
        AUTH_DISABLED_WARNING,
        announce_request_validation_status,
    )

    monkeypatch.setenv("SPELLBOOK_AUTH", "disabled")
    with caplog.at_level(logging.WARNING, logger="spellbook.mcp.server"):
        announce_request_validation_status("127.0.0.1", 8765)

    assert AUTH_DISABLED_WARNING in caplog.text


def test_disabled_auth_banner_says_disabled(monkeypatch, capsys):
    from spellbook.mcp.server import announce_request_validation_status

    monkeypatch.setenv("SPELLBOOK_AUTH", "disabled")
    banner = announce_request_validation_status("127.0.0.1", 8765)

    assert "DISABLED" in banner
    assert "127.0.0.1:8765" in banner
    assert "DISABLED" in capsys.readouterr().out


def test_deprecated_alias_also_announces(monkeypatch, caplog):
    """SPELLBOOK_MCP_AUTH is still live, so it must announce itself too."""
    from spellbook.mcp.server import announce_request_validation_status

    monkeypatch.delenv("SPELLBOOK_AUTH", raising=False)
    monkeypatch.setenv("SPELLBOOK_MCP_AUTH", "disabled")
    with caplog.at_level(logging.WARNING, logger="spellbook.mcp.server"):
        banner = announce_request_validation_status("127.0.0.1", 8765)

    assert "DISABLED" in banner
    assert "disabled" in caplog.text.lower()


def test_enabled_auth_is_quiet_and_honest(monkeypatch, caplog):
    """The negative case: no warning, and no false alarm in the banner."""
    monkeypatch.delenv("SPELLBOOK_AUTH", raising=False)
    monkeypatch.delenv("SPELLBOOK_MCP_AUTH", raising=False)
    from spellbook.mcp.server import announce_request_validation_status

    with caplog.at_level(logging.WARNING, logger="spellbook.mcp.server"):
        banner = announce_request_validation_status("127.0.0.1", 8765)

    assert "DISABLED" not in banner
    assert "enabled" in banner
    assert caplog.text == ""


def test_banner_does_not_depend_on_middleware_list(monkeypatch):
    """Guards the exact defect: status derived from run-kwargs shape.

    build_http_run_kwargs() always returns a non-empty middleware list, so any
    implementation reading that list reports "enabled" here and fails.
    """
    from spellbook.mcp.server import (
        announce_request_validation_status,
        build_http_run_kwargs,
    )

    monkeypatch.setenv("SPELLBOOK_AUTH", "disabled")
    kwargs = build_http_run_kwargs()
    assert kwargs.get("middleware"), "precondition: middleware list is non-empty"

    assert "DISABLED" in announce_request_validation_status("127.0.0.1", 8765)
