"""Origin and Host validation for the MCP HTTP transport.

The daemon binds loopback and holds no credentials. Binding loopback stops the
network but not the browser: any page the user visits can issue requests to
127.0.0.1. This module rejects those requests.

Two headers carry the signal:

``Origin``
    Present on the browser-issued requests that can carry a side effect --
    ``fetch``/XHR and cross-origin form submissions -- and it names the
    *attacking* page even under DNS rebinding. Its absence is allowed, which is
    what every legitimate MCP client (Claude Code, curl, pi's adapter) sends.

    A browser does *not* send it on every cross-origin request: it is omitted on
    GET navigations and on ``<img>``/``<script>``/``<link>``/``<iframe src>``
    subresource loads. Allowing an absent Origin is therefore safe only while no
    GET or HEAD route here has a side effect. A new GET route with a side effect
    needs its own check; see docs/security.md.

``Host``
    Under DNS rebinding the attacker's own hostname is what resolves to
    127.0.0.1, so it appears here. Checking it closes the rebinding path at a
    second layer, independent of Origin.
"""

from urllib.parse import urlsplit

from starlette.responses import JSONResponse

# Hostnames that denote this machine. An Origin or Host outside this set did not
# come from software running locally under the user's own control.
LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def auth_is_disabled() -> bool:
    """Check if request validation is disabled via SPELLBOOK_AUTH=disabled."""
    from spellbook.core.config import get_env

    return (get_env("AUTH") or "").lower() == "disabled"


def _hostname_of(value: str) -> str | None:
    """Extract the hostname from an Origin URL or a Host header value.

    Returns None when the value is absent or cannot be parsed. Uses urlsplit so
    that ports, IPv6 brackets, and userinfo are handled by the stdlib rather
    than by string surgery -- ``localhost.evil.com`` must not read as localhost.
    """
    if not value:
        return None
    try:
        # A bare Host header ("127.0.0.1:8765") is not a URL; the "//" prefix
        # makes urlsplit treat it as an authority.
        parsed = urlsplit(value if "//" in value else f"//{value}")
        return parsed.hostname
    except ValueError:
        return None


def get_allowed_origins() -> frozenset[str]:
    """Return extra exact-match origins from SPELLBOOK_ALLOWED_ORIGINS.

    Loopback origins are always allowed and are not listed here. This variable
    exists for a browser-based MCP client served from somewhere else, which the
    hostname rule cannot recognise.
    """
    from spellbook.core.config import get_env

    raw = get_env("ALLOWED_ORIGINS") or ""
    return frozenset(
        item.strip().rstrip("/").lower() for item in raw.split(",") if item.strip()
    )


class OriginValidationMiddleware:
    """ASGI middleware rejecting browser-issued cross-origin requests.

    Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) for
    compatibility with Starlette's Middleware() wrapper used by FastMCP.

    Configuration is read once at construction: it is process-wide daemon
    config, and re-reading it per request would let a mid-flight environment
    change alter the security boundary.
    """

    def __init__(self, app):
        self.app = app
        self.disabled = auth_is_disabled()
        self.allowed_origins = get_allowed_origins()
        self.allowed_hostnames = set(LOOPBACK_HOSTNAMES)

        # An operator who binds a non-loopback address reaches the daemon under
        # that name; refusing it would lock them out of their own deployment.
        from spellbook.core.config import get_env

        bind_host = _hostname_of(get_env("HOST", "127.0.0.1") or "")
        if bind_host:
            self.allowed_hostnames.add(bind_host.lower())

    def _rejection(self, reason: str) -> JSONResponse:
        # 403, not 401: there are no credentials, so nothing the caller could
        # supply would change the outcome. 401 would promise a retry path that
        # does not exist.
        return JSONResponse({"error": f"Forbidden: {reason}"}, status_code=403)

    def _check(self, scope) -> JSONResponse | None:
        """Return a rejection response, or None when the request may proceed."""
        headers = dict(scope.get("headers", []))

        def header(name: bytes) -> str:
            return headers.get(name, b"").decode("utf-8", errors="ignore")

        host_value = header(b"host")
        if host_value:
            hostname = _hostname_of(host_value)
            if hostname is None or hostname.lower() not in self.allowed_hostnames:
                return self._rejection("unrecognized Host header")

        origin_value = header(b"origin")
        if not origin_value:
            # No Origin: not a browser request under a page's control.
            return None

        normalized = origin_value.strip().rstrip("/").lower()
        if normalized in self.allowed_origins:
            return None

        origin_host = _hostname_of(origin_value)
        if origin_host and origin_host.lower() in LOOPBACK_HOSTNAMES:
            return None

        return self._rejection("origin not allowed")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.disabled:
            return await self.app(scope, receive, send)

        rejection = self._check(scope)
        if rejection is not None:
            return await rejection(scope, receive, send)

        return await self.app(scope, receive, send)
