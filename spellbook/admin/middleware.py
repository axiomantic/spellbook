"""ASGI middleware for the admin sub-app.

Currently provides:

- ``HostValidatorMiddleware``: rejects requests whose ``Host`` header is not in
  a bare-hostname allowlist (DNS rebinding defense, design-doc C1).

These are pure-ASGI classes with no FastAPI dependency. Header parsing uses
``starlette.datastructures.Headers``; error responses use
``starlette.responses.PlainTextResponse``.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


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
