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
    """Generate auth token, write to file with 0600 perms atomically, return token."""
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
            # Allow health check endpoint without auth
            path = scope.get("path", "")
            if path == "/health":
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
