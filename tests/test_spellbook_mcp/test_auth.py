"""Tests for bearer token authentication (Finding #3).

Tests token generation, file management, and ASGI middleware for
authenticating HTTP requests to the MCP server.
"""

import os
import stat
import sys
import pytest
from pathlib import Path


class TestTokenGeneration:
    """Token generation and file management."""

    def test_generates_token_with_correct_permissions(self, tmp_path):
        """Token file must have 0600 permissions and contain the returned token."""
        from spellbook.core import auth

        token_path = tmp_path / ".mcp-token"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            token = auth.generate_and_store_token()

            # Token must be url-safe base64, 43 chars for 32 bytes
            assert len(token) == 43
            # Verify token contains only url-safe base64 characters
            import re
            assert re.fullmatch(r'[A-Za-z0-9_-]+', token), (
                f"Token contains non-url-safe-base64 characters: {token}"
            )
            # File permissions must be owner-only read/write (Unix only;
            # Windows does not support POSIX permission bits)
            if sys.platform != "win32":
                file_mode = stat.S_IMODE(token_path.stat().st_mode)
                assert file_mode == 0o600
            # File content must be exactly the returned token
            assert token_path.read_text() == token
        finally:
            auth.TOKEN_PATH = original

    def test_reuses_existing_token(self, tmp_path):
        """Repeated calls must return the same stable token."""
        from spellbook.core import auth

        token_path = tmp_path / ".mcp-token"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            token1 = auth.generate_and_store_token()
            token2 = auth.generate_and_store_token()
            assert token1 == token2
        finally:
            auth.TOKEN_PATH = original

    def test_creates_parent_directories(self, tmp_path):
        """Token file creation must create parent dirs if missing."""
        from spellbook.core import auth

        token_path = tmp_path / "nested" / "dirs" / ".mcp-token"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            token = auth.generate_and_store_token()
            assert token_path.read_text() == token
        finally:
            auth.TOKEN_PATH = original

    def test_reuses_existing_token_from_file(self, tmp_path):
        """Must reuse a valid token already on disk."""
        from spellbook.core import auth

        token_path = tmp_path / ".mcp-token"
        token_path.write_text("pre-existing-token-value")
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            loaded_token = auth.generate_and_store_token()
            assert loaded_token == "pre-existing-token-value"
            assert token_path.read_text() == "pre-existing-token-value"
        finally:
            auth.TOKEN_PATH = original

    def test_generates_new_token_when_file_empty(self, tmp_path):
        """Must generate a new token when file exists but is empty."""
        from spellbook.core import auth

        token_path = tmp_path / ".mcp-token"
        token_path.write_text("")
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            new_token = auth.generate_and_store_token()
            assert new_token
            assert token_path.read_text() == new_token
        finally:
            auth.TOKEN_PATH = original

    def test_load_token_returns_stored_value(self, tmp_path):
        """load_token must return the stored token."""
        from spellbook.core import auth

        token_path = tmp_path / ".mcp-token"
        token_path.write_text("test-token-value")
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            assert auth.load_token() == "test-token-value"
        finally:
            auth.TOKEN_PATH = original

    def test_load_token_strips_whitespace(self, tmp_path):
        """load_token must strip trailing whitespace/newlines."""
        from spellbook.core import auth

        token_path = tmp_path / ".mcp-token"
        token_path.write_text("test-token-value\n")
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            assert auth.load_token() == "test-token-value"
        finally:
            auth.TOKEN_PATH = original

    def test_load_token_returns_none_if_missing(self, tmp_path):
        """load_token returns None when token file does not exist."""
        from spellbook.core import auth

        token_path = tmp_path / "nonexistent"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            assert auth.load_token() is None
        finally:
            auth.TOKEN_PATH = original


class TestBearerAuthMiddleware:
    """ASGI middleware must reject unauthenticated requests.

    Uses Starlette TestClient for realistic ASGI message handling.
    """

    @pytest.fixture
    def auth_app(self):
        """Create a minimal Starlette app wrapped in BearerAuthMiddleware."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from spellbook.core.auth import BearerAuthMiddleware

        async def index(request):
            return JSONResponse({"status": "ok"})

        async def health(request):
            return JSONResponse({"healthy": True})

        inner_app = Starlette(
            routes=[
                Route("/mcp/v1/tools", index),
                Route("/health", health),
            ]
        )

        return BearerAuthMiddleware(inner_app, token="correct-token")

    def test_rejects_request_without_token(self, auth_app):
        """Request without Authorization header must get 401 with error detail."""
        from starlette.testclient import TestClient

        client = TestClient(auth_app, raise_server_exceptions=False)
        response = client.get("/mcp/v1/tools")
        assert response.status_code == 401
        assert response.json() == {
            "error": "Unauthorized. Configure bearer token from ~/.local/spellbook/.mcp-token"
        }

    def test_rejects_wrong_token(self, auth_app):
        """Request with wrong token must get 401 with error detail."""
        from starlette.testclient import TestClient

        client = TestClient(auth_app, raise_server_exceptions=False)
        response = client.get(
            "/mcp/v1/tools",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "Unauthorized. Configure bearer token from ~/.local/spellbook/.mcp-token"
        }

    def test_rejects_malformed_auth_header(self, auth_app):
        """Request with non-Bearer auth scheme must get 401."""
        from starlette.testclient import TestClient

        client = TestClient(auth_app, raise_server_exceptions=False)
        response = client.get(
            "/mcp/v1/tools",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "Unauthorized. Configure bearer token from ~/.local/spellbook/.mcp-token"
        }

    def test_passes_correct_token(self, auth_app):
        """Request with correct token must reach the inner app."""
        from starlette.testclient import TestClient

        client = TestClient(auth_app, raise_server_exceptions=False)
        response = client.get(
            "/mcp/v1/tools",
            headers={"Authorization": "Bearer correct-token"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_endpoint_bypasses_auth(self, auth_app):
        """GET /health must not require authentication."""
        from starlette.testclient import TestClient

        client = TestClient(auth_app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"healthy": True}

    def test_admin_paths_bypass_bearer_auth(self):
        """Admin paths must bypass bearer auth (admin has its own cookie auth)."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route, Mount
        from starlette.testclient import TestClient
        from spellbook.core.auth import BearerAuthMiddleware

        async def admin_index(request):
            return JSONResponse({"admin": True})

        inner_app = Starlette(
            routes=[
                Mount("/admin", routes=[Route("/", admin_index)]),
            ]
        )
        app = BearerAuthMiddleware(inner_app, token="correct-token")
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/admin/")
        assert response.status_code == 200
        assert response.json() == {"admin": True}

    def test_uses_constant_time_comparison(self, auth_app, monkeypatch):
        """Token comparison must use secrets.compare_digest for timing safety."""
        from starlette.testclient import TestClient

        calls = []

        def _tracking_compare_digest(a, b):
            calls.append((a, b))
            return True

        monkeypatch.setattr(
            "spellbook.core.auth.secrets.compare_digest",
            _tracking_compare_digest,
        )

        client = TestClient(auth_app, raise_server_exceptions=False)
        response = client.get(
            "/mcp/v1/tools",
            headers={"Authorization": "Bearer any-token"},
        )
        assert response.status_code == 200
        assert ("any-token", "correct-token") in calls

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        """Non-HTTP scopes (e.g. websocket, lifespan) must pass through without auth."""
        from spellbook.core.auth import BearerAuthMiddleware

        received_scope = {}

        async def inner_app(scope, receive, send):
            received_scope.update(scope)

        middleware = BearerAuthMiddleware(inner_app, token="test-token")
        scope = {"type": "lifespan"}

        await middleware(scope, None, None)
        assert received_scope == {"type": "lifespan"}


class TestAuthDisabledEnvVar:
    """SPELLBOOK_MCP_AUTH=disabled escape hatch."""

    def test_auth_disabled_check(self, monkeypatch):
        """When SPELLBOOK_MCP_AUTH=disabled, auth_is_disabled() returns True."""
        from spellbook.core.auth import auth_is_disabled

        monkeypatch.setenv("SPELLBOOK_MCP_AUTH", "disabled")
        assert auth_is_disabled() is True

    def test_auth_enabled_by_default(self, monkeypatch):
        """Without SPELLBOOK_MCP_AUTH env var, auth_is_disabled() returns False."""
        from spellbook.core.auth import auth_is_disabled

        monkeypatch.delenv("SPELLBOOK_MCP_AUTH", raising=False)
        assert auth_is_disabled() is False

    def test_auth_disabled_case_insensitive(self, monkeypatch):
        """SPELLBOOK_MCP_AUTH check must be case-insensitive."""
        from spellbook.core.auth import auth_is_disabled

        monkeypatch.setenv("SPELLBOOK_MCP_AUTH", "Disabled")
        assert auth_is_disabled() is True

    def test_auth_not_disabled_for_other_values(self, monkeypatch):
        """Only 'disabled' (case-insensitive) disables auth."""
        from spellbook.core.auth import auth_is_disabled

        monkeypatch.setenv("SPELLBOOK_MCP_AUTH", "off")
        assert auth_is_disabled() is False


class TestServerStartupAuthIntegration:
    """Server startup must wire auth middleware for HTTP transport.

    These tests verify the __main__ block logic by testing the
    build_http_run_kwargs helper function that constructs the kwargs
    passed to mcp.run().
    """

    def test_http_kwargs_include_middleware_when_auth_enabled(self, tmp_path, monkeypatch):
        """When auth is not disabled, build_http_run_kwargs must return middleware list."""
        from spellbook.core import auth
        from spellbook.server import build_http_run_kwargs

        token_path = tmp_path / ".mcp-token"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            monkeypatch.setenv("SPELLBOOK_MCP_HOST", "127.0.0.1")
            monkeypatch.setenv("SPELLBOOK_MCP_PORT", "9999")
            kwargs = build_http_run_kwargs()

            assert kwargs["transport"] == "streamable-http"
            assert kwargs["host"] == "127.0.0.1"
            assert kwargs["port"] == 9999
            assert kwargs["stateless_http"] is True
            # Must have exactly one middleware entry
            assert len(kwargs["middleware"]) == 1
            mw = kwargs["middleware"][0]
            # Starlette Middleware wraps our class
            from starlette.middleware import Middleware
            assert isinstance(mw, Middleware)
            assert mw.cls is auth.BearerAuthMiddleware
            # Token must have been written to file
            assert token_path.exists()
            written_token = token_path.read_text()
            assert len(written_token) == 43
            assert mw.kwargs == {"token": written_token}
        finally:
            auth.TOKEN_PATH = original

    def test_http_kwargs_no_middleware_when_auth_disabled(self, tmp_path, monkeypatch):
        """When SPELLBOOK_MCP_AUTH=disabled, build_http_run_kwargs must return empty middleware."""
        from spellbook.core import auth
        from spellbook.server import build_http_run_kwargs

        token_path = tmp_path / ".mcp-token"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            monkeypatch.setenv("SPELLBOOK_MCP_AUTH", "disabled")
            monkeypatch.setenv("SPELLBOOK_MCP_HOST", "0.0.0.0")
            monkeypatch.setenv("SPELLBOOK_MCP_PORT", "8765")
            kwargs = build_http_run_kwargs()

            assert kwargs == {
                "transport": "streamable-http",
                "host": "0.0.0.0",
                "port": 8765,
                "stateless_http": True,
                "middleware": [],
            }
            # Token file must NOT have been created
            assert not token_path.exists()
        finally:
            auth.TOKEN_PATH = original

    def test_http_kwargs_use_default_host_and_port(self, tmp_path, monkeypatch):
        """build_http_run_kwargs must use default host/port when env vars are unset."""
        from spellbook.core import auth
        from spellbook.server import build_http_run_kwargs

        token_path = tmp_path / ".mcp-token"
        original = auth.TOKEN_PATH
        auth.TOKEN_PATH = token_path
        try:
            monkeypatch.setenv("SPELLBOOK_MCP_AUTH", "disabled")
            monkeypatch.delenv("SPELLBOOK_MCP_HOST", raising=False)
            monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
            kwargs = build_http_run_kwargs()

            assert kwargs == {
                "transport": "streamable-http",
                "host": "127.0.0.1",
                "port": 8765,
                "stateless_http": True,
                "middleware": [],
            }
        finally:
            auth.TOKEN_PATH = original

    def test_fastmcp_version_constraint(self):
        """pyproject.toml must require fastmcp in the daemon dependency group."""
        import tomllib

        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        daemon_deps = pyproject.get("dependency-groups", {}).get("daemon", [])
        fastmcp_deps = [d for d in daemon_deps if d.startswith("fastmcp")]
        assert len(fastmcp_deps) == 1, "fastmcp must be in the daemon dependency group"
        assert fastmcp_deps[0].startswith("fastmcp>="), f"fastmcp must have a minimum version: {fastmcp_deps[0]}"
