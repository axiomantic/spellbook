import socket
import sqlite3

import pytest
from unittest.mock import patch
import secrets


@pytest.fixture(autouse=True)
def _restore_io_patches():
    """Restore original socket and sqlite3 methods during admin tests.

    bigfoot patches socket.send/recv/etc. and sqlite3.connect at the class/module
    level. TestClient runs in a background thread where bigfoot's interceptors
    raise GuardedCallError (no active sandbox). This fixture temporarily restores
    the originals for test duration.
    """
    saved_socket_patches = {}
    saved_db_connect = None

    try:
        from bigfoot.plugins.socket_plugin import (
            _SOCKET_SEND_ORIGINAL,
            _SOCKET_RECV_ORIGINAL,
            _SOCKET_CONNECT_ORIGINAL,
            _SOCKET_SENDALL_ORIGINAL,
            _SOCKET_CLOSE_ORIGINAL,
        )
        bf_socket_originals = {
            "send": _SOCKET_SEND_ORIGINAL,
            "recv": _SOCKET_RECV_ORIGINAL,
            "connect": _SOCKET_CONNECT_ORIGINAL,
            "sendall": _SOCKET_SENDALL_ORIGINAL,
            "close": _SOCKET_CLOSE_ORIGINAL,
        }
        for name, original in bf_socket_originals.items():
            current = getattr(socket.socket, name)
            if current is not original:
                saved_socket_patches[name] = current
                setattr(socket.socket, name, original)
    except ImportError:
        pass

    try:
        from bigfoot.plugins.database_plugin import DatabasePlugin
        bf_db_original = DatabasePlugin._original_connect
        if bf_db_original is not None and sqlite3.connect is not bf_db_original:
            saved_db_connect = sqlite3.connect
            sqlite3.connect = bf_db_original
    except (ImportError, AttributeError):
        pass

    yield

    for name, bf_patch in saved_socket_patches.items():
        setattr(socket.socket, name, bf_patch)
    if saved_db_connect is not None:
        sqlite3.connect = saved_db_connect


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
