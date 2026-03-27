import pytest
import secrets


@pytest.fixture(autouse=True)
def mock_mcp_token(monkeypatch):
    """Mock the MCP token for all admin tests."""
    token = secrets.token_urlsafe(32)

    monkeypatch.setattr("spellbook.admin.auth.load_token", lambda: token)
    monkeypatch.setattr("spellbook.admin.routes.auth.load_token", lambda: token)

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

    with TestClient(admin_app) as client:
        cookie = create_session_cookie("test-session")
        client.cookies.set("spellbook_admin_session", cookie)
        yield client


@pytest.fixture
def unauthenticated_client(admin_app):
    """Test client without auth cookie."""
    from fastapi.testclient import TestClient

    with TestClient(admin_app) as client:
        yield client
