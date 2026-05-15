"""ASGI middleware for the admin sub-app.

Currently provides:

- ``HostValidatorMiddleware``: rejects requests whose ``Host`` header is not in
  a bare-hostname allowlist (DNS rebinding defense, design-doc C1).
- ``OriginCheckMiddleware``: requires a same-origin ``Origin`` header on
  state-changing methods (POST/PUT/PATCH/DELETE) for the cookie-auth path
  (CSRF defense, design-doc C4). Requests presenting a valid Bearer token
  are exempt so the CLI's bearer-authed mutations work without a browser
  Origin header.

These are pure-ASGI classes with no FastAPI dependency. Header parsing uses
``starlette.datastructures.Headers``; error responses use
``starlette.responses.PlainTextResponse``.
"""

from __future__ import annotations

import secrets

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Safe HTTP methods: never gated by the Origin check.
_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})


class HostValidatorMiddleware:
    """Reject HTTP/WS requests whose ``Host`` header is not in the allowlist.

    The allowlist holds *bare* hostnames (no scheme, no port). The incoming
    ``Host`` header is normalised before comparison:

    - Whitespace is stripped.
    - Bracketed IPv6 forms (``[::1]`` / ``[::1]:8765``) extract the inner
      address. Unclosed brackets (``[bad``) extract ``""`` so they cannot
      match the allowlist.
    - IPv4 / DNS forms split on the first ``:`` to drop the port.
    - The result is lowercased so the comparison is case-insensitive
      (``LOCALHOST`` matches ``localhost``).

    On mismatch:

    - HTTP scope -> 400 ``PlainTextResponse("Invalid host header")``.
    - WebSocket scope -> ``websocket.close`` with code 1008 sent *before*
      ``websocket.accept``. Starlette translates a pre-accept close into a
      403 on the HTTP upgrade response so the browser never opens the
      WebSocket.
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        # Allowlist is stored lowercased so comparison is case-insensitive.
        self._allowed = frozenset(h.lower() for h in allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        hostname = self._extract_hostname(headers.get("host", ""))
        if hostname and hostname in self._allowed:
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            resp = PlainTextResponse("Invalid host header", status_code=400)
            await resp(scope, receive, send)
        else:
            # Close BEFORE accept. Starlette emits HTTP 403 on the upgrade.
            await send({"type": "websocket.close", "code": 1008})

    @staticmethod
    def _extract_hostname(host_header: str) -> str:
        """Extract the bare hostname for allowlist comparison.

        Returns ``""`` for empty or malformed input so the result cannot
        accidentally match a non-empty allowlist entry.
        """
        if not host_header:
            return ""
        host_header = host_header.strip()
        if not host_header:
            return ""
        if host_header.startswith("["):
            closing = host_header.find("]")
            if closing == -1:
                return ""
            return host_header[1:closing].lower()
        if ":" in host_header:
            return host_header.split(":", 1)[0].lower()
        return host_header.lower()


class OriginCheckMiddleware:
    """Reject state-changing HTTP requests whose ``Origin`` is not in the allowlist.

    Contract:

    - Safe methods (``GET``, ``HEAD``, ``OPTIONS``) pass through unchecked.
    - Non-HTTP scopes (``websocket``, ``lifespan``) pass through; the WS
      handler in ``ws.py`` runs its own Origin check at handshake time.
    - For state-changing methods (``POST``, ``PUT``, ``PATCH``, ``DELETE``):

      1. If the request carries an ``Authorization: Bearer <token>`` header
         whose token matches ``spellbook.admin.auth.load_token()`` under
         ``secrets.compare_digest``, the request bypasses the Origin check.
      2. Otherwise (no bearer, or wrong bearer) the request MUST present an
         ``Origin`` header whose exact value is in the allowlist. Missing or
         mismatched origins receive a plain ``403 Forbidden: invalid Origin``.

    A *wrong* Bearer token does NOT short-circuit with 401; it falls through
    to the Origin check so the failure mode is indistinguishable from
    "no auth attempted" (no token-validity oracle).

    ``load_token`` is resolved at request time via ``from spellbook.admin
    import auth as admin_auth; admin_auth.load_token()``, NOT captured at
    construction. This keeps ``monkeypatch.setattr("spellbook.admin.auth.
    load_token", ...)`` working in tests and lets the token file rotate at
    runtime without restarting the daemon.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed_origins = list(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only HTTP is gated here. WebSocket has its own Origin check in ws.py;
        # lifespan and other scopes are not request traffic.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        if method in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        # Bearer exemption. Imported lazily so monkeypatch on
        # ``spellbook.admin.auth.load_token`` is respected in tests and so
        # token rotation is observed at request time.
        auth_header = headers.get("authorization", "")
        # RFC 7235: the auth-scheme token is case-insensitive. Compare the
        # scheme prefix in lowercase, but slice the ORIGINAL header so a
        # mixed-case token body is preserved verbatim for compare_digest.
        # Strip the extracted token to tolerate trailing whitespace.
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:].strip()
            from spellbook.admin import auth as admin_auth

            expected = admin_auth.load_token() or ""
            if expected and secrets.compare_digest(provided, expected):
                await self.app(scope, receive, send)
                return
            # Wrong bearer: fall through to the Origin check. Do NOT 401 here.

        origin = headers.get("origin", "")
        if origin and origin in self.allowed_origins:
            await self.app(scope, receive, send)
            return

        resp = PlainTextResponse(
            "Forbidden: invalid Origin", status_code=403
        )
        await resp(scope, receive, send)
