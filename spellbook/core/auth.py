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

# Bind addresses meaning "every interface". They name no host, so they never
# belong in the allowed set. urlsplit reduces "[::]" to "::"; both spellings are
# listed because this set is also compared against raw configuration values.
WILDCARD_BIND_ADDRESSES = frozenset({"0.0.0.0", "::", "[::]"})


def auth_is_disabled() -> bool:
    """Check if request validation is disabled via SPELLBOOK_AUTH=disabled."""
    from spellbook.core.config import get_env

    return (get_env("AUTH") or "").lower() == "disabled"


def _hostname_of(value: str) -> str | None:
    """Extract the hostname from an Origin URL or a Host header value.

    Returns None when the value is absent or cannot be parsed. Uses urlsplit so
    that ports and IPv6 bracket forms are handled by the stdlib rather than by
    string surgery -- ``localhost.evil.com`` must not read as localhost.
    """
    if not value:
        return None
    try:
        # A bare Host header ("127.0.0.1:8765") is not a URL; the "//" prefix
        # makes urlsplit treat it as an authority.
        parsed = urlsplit(value if "//" in value else f"//{value}")
        # urlsplit reads userinfo, so "evil.com@localhost" yields hostname
        # "localhost" and would be admitted under the attacker's own name. A
        # Host header has no userinfo field; anything carrying one is not a Host.
        if parsed.username is not None or parsed.password is not None:
            return None
        return parsed.hostname
    except ValueError:
        return None


def _origin_parts(value: str) -> tuple[str, str, int | None] | None:
    """Split an Origin into (scheme, hostname, port), or None if unparseable.

    Comparing the parts, not the string, keeps IPv6 bracket forms and a
    redundant explicit port from changing the answer.
    """
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname:
        return None
    # Mirrors the Host guard. A serialized Origin carries no userinfo -- a
    # browser strips it -- so anything here that does was hand-built, and
    # accepting it would make "http://evil.com@localhost:8765" read as the
    # daemon's own origin.
    if parsed.username is not None or parsed.password is not None:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def get_allowed_origins() -> frozenset[str]:
    """Return exact-match origins from SPELLBOOK_ALLOWED_ORIGINS.

    Matching is exact on scheme, host, and port. Nothing beyond the daemon's
    own origin is allowed implicitly: a browser-based MCP client -- local or
    remote -- must be listed here.
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

        # The daemon is a local-only service. A configured bind host is added
        # here only when it is itself a reachable name; a wildcard bind supplies
        # no name a client can send, so under it only the loopback Host values
        # remain allowed and a request arriving as "Host: 192.168.1.5:8765" is
        # refused. That is intended: remote access is out of scope, and
        # SPELLBOOK_AUTH=disabled is the only way to serve it. Failing closed
        # here costs a deployment this project does not support; failing open
        # would cost the rebinding defense.
        from spellbook.core.config import get_env

        bind_host = _hostname_of(get_env("HOST", "127.0.0.1") or "")
        # A wildcard bind must be dropped explicitly rather than left to parse
        # away. "::" yields no hostname and disappears on its own, but "0.0.0.0"
        # parses to "0.0.0.0" -- a name a client can literally put in a Host
        # header -- so it would otherwise be added here and admitted.
        if bind_host in WILDCARD_BIND_ADDRESSES:
            bind_host = None
        if bind_host:
            self.allowed_hostnames.add(bind_host.lower())

        # The daemon's own origin, and only that one: same scheme, same host,
        # same port. A page served from another port on this machine is a
        # different origin and gets no implicit trust from being local.
        self.self_origins: frozenset[tuple[str, str, int]] = frozenset()
        try:
            bind_port = int(get_env("PORT", "8765") or "8765")
        except ValueError:
            # An unparseable port leaves the daemon's own origin unknown, and an
            # unknown origin cannot be matched -- a None port would compare equal
            # to a port-less Origin, making http://localhost (port 80: any local
            # web server) trusted while the real daemon origin is refused. Trust
            # nothing implicitly instead.
            pass
        else:
            self.self_origins = frozenset(
                ("http", hostname, bind_port) for hostname in self.allowed_hostnames
            )

    def _rejection(self, reason: str) -> JSONResponse:
        # 403, not 401: there are no credentials, so nothing the caller could
        # supply would change the outcome. 401 would promise a retry path that
        # does not exist.
        return JSONResponse({"error": f"Forbidden: {reason}"}, status_code=403)

    def _check(self, scope) -> JSONResponse | None:
        """Return a rejection response, or None when the request may proceed."""
        raw = scope.get("headers", []) or []

        def values(name: str) -> list[str] | None:
            # Case-folded on our side rather than trusting the ASGI server to
            # have lowercased the names: a server or shim that does not would
            # otherwise make this check silently vanish.
            #
            # None signals undecodable bytes. Dropping them (errors="ignore")
            # would map two distinct byte strings onto one allowed value:
            # b"http://local\xffhost:8765" would read as the daemon's own
            # origin. Same ambiguity the duplicate-header case refuses, so it
            # gets the same answer.
            target = name.encode()
            found = []
            for key, value in raw:
                if key.lower() != target:
                    continue
                try:
                    found.append(value.decode("utf-8"))
                except UnicodeDecodeError:
                    return None
            return found

        # More than one copy of either header is a request-smuggling shape, not
        # a legitimate client. Neither first-wins nor last-wins is safe: each
        # merely picks which smuggling direction succeeds, so refuse outright.
        host_values = values("host")
        if host_values is None:
            return self._rejection("undecodable Host header")
        if len(host_values) > 1:
            return self._rejection("duplicate Host header")

        origin_values = values("origin")
        if origin_values is None:
            return self._rejection("undecodable Origin header")
        if len(origin_values) > 1:
            return self._rejection("duplicate Origin header")

        host_value = host_values[0] if host_values else ""
        if host_value:
            hostname = _hostname_of(host_value)
            if hostname is None or hostname.lower() not in self.allowed_hostnames:
                return self._rejection("unrecognized Host header")

        origin_value = origin_values[0] if origin_values else ""
        if not origin_value:
            # No Origin: not a browser request under a page's control.
            return None

        normalized = origin_value.strip().rstrip("/").lower()
        if normalized in self.allowed_origins:
            return None

        parts = _origin_parts(origin_value)
        if parts is not None and parts in self.self_origins:
            return None

        return self._rejection("origin not allowed")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.disabled:
            return await self.app(scope, receive, send)

        rejection = self._check(scope)
        if rejection is not None:
            return await rejection(scope, receive, send)

        return await self.app(scope, receive, send)
