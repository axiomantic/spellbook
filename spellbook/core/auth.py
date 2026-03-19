"""Bearer token authentication for MCP HTTP transport.

Implements token generation, file management, and ASGI middleware
for authenticating HTTP requests to the MCP server.
"""

import os
import secrets
from pathlib import Path

from starlette.responses import JSONResponse

TOKEN_PATH = Path.home() / ".local" / "spellbook" / ".mcp-token"


def generate_and_store_token() -> str:
    """Load existing token or generate a new one.

    Reuses the token from TOKEN_PATH if it already exists and is non-empty,
    so that the token remains stable across daemon restarts. Clients that
    registered with the token (e.g., via ``claude mcp add --header``) will
    continue to authenticate without re-registration.

    Only generates a fresh token when no token file exists yet (first
    install) or the file is empty/unreadable.
    """
    existing = load_token()
    if existing:
        return existing

    token = secrets.token_urlsafe(32)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Atomic create with correct permissions (no TOCTOU race)
    fd = os.open(
        str(TOKEN_PATH),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(fd, "w") as f:
        f.write(token)

    return token


def load_token() -> str | None:
    """Load token from file if it exists."""
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    return None


def auth_is_disabled() -> bool:
    """Check if auth is disabled via SPELLBOOK_MCP_AUTH=disabled env var."""
    return os.environ.get("SPELLBOOK_MCP_AUTH", "").lower() == "disabled"


class BearerAuthMiddleware:
    """ASGI middleware for bearer token authentication.

    Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) for
    compatibility with Starlette's Middleware() wrapper used by FastMCP.
    """

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Allow health check and admin interface without bearer auth
            # (admin has its own cookie-based session auth)
            path = scope.get("path", "")
            if path == "/health" or path.startswith("/admin"):
                return await self.app(scope, receive, send)

            # Extract Authorization header
            headers = dict(scope.get("headers", []))
            auth_value = headers.get(
                b"authorization", b""
            ).decode("utf-8", errors="ignore")

            if not auth_value.startswith("Bearer ") or not secrets.compare_digest(
                auth_value[7:], self.token
            ):
                response = JSONResponse(
                    {
                        "error": "Unauthorized. Configure bearer token from ~/.local/spellbook/.mcp-token"
                    },
                    status_code=401,
                )
                return await response(scope, receive, send)

        return await self.app(scope, receive, send)
