import time

import pytest


class TestExchangeToken:
    def test_create_exchange_token_returns_string(self, mock_mcp_token):
        from spellbook.admin.auth import create_exchange_token

        token = create_exchange_token()
        assert isinstance(token, str)
        assert len(token) > 20

    def test_validate_exchange_token_consumes_on_first_use(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_exchange_token,
            validate_exchange_token,
        )

        token = create_exchange_token()
        assert validate_exchange_token(token) is True
        assert validate_exchange_token(token) is False  # consumed

    def test_validate_exchange_token_rejects_expired(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_exchange_token,
            validate_exchange_token,
            _exchange_tokens,
        )

        token = create_exchange_token()
        _exchange_tokens[token] = time.time() - 1  # expired
        assert validate_exchange_token(token) is False

    def test_validate_exchange_token_rejects_unknown(self, mock_mcp_token):
        from spellbook.admin.auth import validate_exchange_token

        assert validate_exchange_token("nonexistent-token") is False


class TestSessionCookie:
    def test_create_and_validate_session_cookie(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_session_cookie,
            validate_session_cookie,
        )

        cookie = create_session_cookie("test-session-id")
        session_id = validate_session_cookie(cookie)
        assert session_id == "test-session-id"

    def test_validate_session_cookie_rejects_tampered(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_session_cookie,
            validate_session_cookie,
        )

        cookie = create_session_cookie("test-session-id")
        tampered = cookie[:-5] + "XXXXX"
        assert validate_session_cookie(tampered) is None

    def test_validate_session_cookie_rejects_expired(self, mock_mcp_token):
        from spellbook.admin.auth import validate_session_cookie, _get_signing_key
        import json
        import hashlib
        import hmac as hmac_mod

        payload = json.dumps({"sid": "test", "exp": time.time() - 1})
        sig = hmac_mod.new(
            _get_signing_key(), payload.encode(), hashlib.sha256
        ).hexdigest()
        cookie = f"{payload}|{sig}"
        assert validate_session_cookie(cookie) is None

    def test_validate_session_cookie_rejects_malformed(self, mock_mcp_token):
        from spellbook.admin.auth import validate_session_cookie

        assert validate_session_cookie("not-a-valid-cookie") is None
        assert validate_session_cookie("") is None


class TestWSTicket:
    def test_create_ws_ticket_returns_string(self, mock_mcp_token):
        from spellbook.admin.auth import create_ws_ticket

        ticket = create_ws_ticket()
        assert isinstance(ticket, str)
        assert len(ticket) > 10

    def test_validate_ws_ticket_consumes_on_first_use(self, mock_mcp_token):
        from spellbook.admin.auth import create_ws_ticket, validate_ws_ticket

        ticket = create_ws_ticket()
        assert validate_ws_ticket(ticket) is True
        assert validate_ws_ticket(ticket) is False

    def test_validate_ws_ticket_rejects_expired(self, mock_mcp_token):
        from spellbook.admin.auth import (
            create_ws_ticket,
            validate_ws_ticket,
            _ws_tickets,
        )

        ticket = create_ws_ticket()
        _ws_tickets[ticket] = time.time() - 1
        assert validate_ws_ticket(ticket) is False


class TestLogin:
    def test_login_with_correct_token_sets_cookie(self, unauthenticated_client, mock_mcp_token):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": mock_mcp_token},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "spellbook_admin_session" in response.cookies

    def test_login_with_wrong_token_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_login_with_empty_password_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/login",
            json={"password": ""},
        )
        assert response.status_code == 401


class TestCheckAuth:
    def test_check_with_valid_session_returns_200(self, client):
        response = client.get("/api/auth/check")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_check_without_session_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/auth/check")
        assert response.status_code == 401


class TestRequireAdminAuth:
    def test_unauthenticated_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/auth/callback?auth=invalid")
        assert response.status_code == 401
