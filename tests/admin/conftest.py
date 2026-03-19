import pytest
from unittest.mock import patch
import secrets


@pytest.fixture(autouse=True)
def mock_mcp_token(tmp_path):
    """Mock the MCP token for all admin tests."""
    token = secrets.token_urlsafe(32)
    token_path = tmp_path / ".mcp-token"
    token_path.write_text(token)
    with patch("spellbook.admin.auth.load_token", return_value=token), \
         patch("spellbook.admin.routes.auth.load_token", return_value=token):
        yield token


@pytest.fixture
def admin_app():
    """Create admin app for testing."""
    from spellbook.admin.app import create_admin_app

    return create_admin_app()


@pytest.fixture
def client(admin_app, mock_mcp_token):
    """Test client with authenticated session."""
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie

    client = TestClient(admin_app)
    cookie = create_session_cookie("test-session")
    client.cookies.set("spellbook_admin_session", cookie)
    return client


@pytest.fixture
def unauthenticated_client(admin_app):
    """Test client without auth cookie."""
    from fastapi.testclient import TestClient

    return TestClient(admin_app)
