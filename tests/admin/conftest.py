import pytest
import secrets


@pytest.fixture(autouse=True)
def clear_handoff_store():
    """Clear handoff/exchange token store between tests."""
    from spellbook.admin import auth as admin_auth

    for attr in ("_handoff_tokens", "_exchange_tokens"):
        store = getattr(admin_auth, attr, None)
        if store is not None:
            store.clear()
    yield
    for attr in ("_handoff_tokens", "_exchange_tokens"):
        store = getattr(admin_auth, attr, None)
        if store is not None:
            store.clear()


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


_DEFAULT_TEST_HEADERS = {
    "Host": "127.0.0.1:8765",
    "Origin": "http://127.0.0.1:8765",
}


@pytest.fixture
def client(admin_app, mock_mcp_token):
    """Test client with authenticated session.

    Constructed with default ``Host`` and ``Origin`` headers acceptable to
    the HostValidator and OriginCheck middlewares so existing tests do not
    need per-call header changes. Individual tests can override these by
    passing explicit ``headers={...}`` kwargs to request methods; httpx
    request-level headers take precedence over client-level defaults.
    """
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie

    with TestClient(admin_app, headers=_DEFAULT_TEST_HEADERS) as client:
        cookie = create_session_cookie("test-session")
        client.cookies.set("spellbook_admin_session", cookie)
        yield client


@pytest.fixture
def unauthenticated_client(admin_app):
    """Test client without auth cookie.

    See :func:`client` for the rationale behind default Host/Origin headers.
    """
    from fastapi.testclient import TestClient

    with TestClient(admin_app, headers=_DEFAULT_TEST_HEADERS) as client:
        yield client
