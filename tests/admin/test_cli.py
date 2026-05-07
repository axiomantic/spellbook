"""CLI command tests for spellbook admin open."""

import re
import urllib.error

import tripwire
from dirty_equals import IsInstance, IsPartialDict, IsStr

from spellbook.admin.cli import admin_open, main

HANDOFF_URL = "http://127.0.0.1:8765/admin/api/auth/handoff"


class TestAdminOpen:
    def test_no_token_returns_error(self):
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns(None)

        with tripwire:
            result = admin_open()

        assert result == 1
        find_token.assert_call(args=(), kwargs={})

    def test_server_unreachable_returns_error(self):
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns("test-token")
        tripwire.http.mock_error(
            "POST",
            "http://127.0.0.1:19999/admin/api/auth/handoff",
            raises=urllib.error.URLError("Connection refused"),
        )

        with tripwire:
            result = admin_open(port=19999)

        assert result == 1
        # Interactions are asserted in occurrence order: token lookup,
        # then the failing HTTP POST.
        find_token.assert_call(args=(), kwargs={})
        tripwire.http.assert_request(
            "POST",
            "http://127.0.0.1:19999/admin/api/auth/handoff",
            headers=IsPartialDict({"Authorization": "Bearer test-token"}),
            body="",
            raised=IsInstance(urllib.error.URLError),
        )

    def test_cli_posts_to_handoff_endpoint(self):
        """The CLI MUST POST to /admin/api/auth/handoff (not /exchange)."""
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns("test-token")
        browser_open = tripwire.mock("spellbook.admin.cli:webbrowser.open")
        browser_open.returns(None)
        tripwire.http.mock_response(
            "POST",
            HANDOFF_URL,
            json={"login_url": f"{HANDOFF_URL}/abc123"},
            status=200,
        )

        with tripwire:
            result = admin_open(port=8765)

        assert result == 0
        find_token.assert_call(args=(), kwargs={})
        # The bearer token MUST be in the Authorization header and the
        # request MUST be a POST to /admin/api/auth/handoff with an empty body.
        tripwire.http.assert_request(
            "POST",
            HANDOFF_URL,
            headers=IsPartialDict({"Authorization": "Bearer test-token"}),
            body="",
        ).assert_response(200, IsPartialDict(), IsStr())
        browser_open.assert_call(args=(f"{HANDOFF_URL}/abc123",), kwargs={})

    def test_cli_sends_bearer_token_in_authorization_header(self):
        """The MCP token MUST be sent in Authorization: Bearer <token>, not in body."""
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns("secret-mcp-token")
        browser_open = tripwire.mock("spellbook.admin.cli:webbrowser.open")
        browser_open.returns(None)
        tripwire.http.mock_response(
            "POST",
            HANDOFF_URL,
            json={"login_url": f"{HANDOFF_URL}/abc123"},
            status=200,
        )

        with tripwire:
            result = admin_open(port=8765)

        assert result == 0
        find_token.assert_call(args=(), kwargs={})
        # Authorization header carries the bearer token; request body is
        # empty (no token in body).
        tripwire.http.assert_request(
            "POST",
            HANDOFF_URL,
            headers=IsPartialDict(
                {"Authorization": "Bearer secret-mcp-token"}
            ),
            body="",
        ).assert_response(200, IsPartialDict(), IsStr())
        browser_open.assert_call(args=(f"{HANDOFF_URL}/abc123",), kwargs={})

    def test_cli_opens_url_from_response_login_url_field(self):
        """The CLI MUST open EXACTLY the login_url returned by the server."""
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns("test-token")
        server_login_url = (
            "http://127.0.0.1:8765/admin/api/auth/handoff/fixed-test-id-abc123"
        )
        opened_urls: list[str] = []
        browser_open = tripwire.mock("spellbook.admin.cli:webbrowser.open")
        browser_open.calls(lambda url: opened_urls.append(url))
        tripwire.http.mock_response(
            "POST",
            HANDOFF_URL,
            json={"login_url": server_login_url},
            status=200,
        )

        with tripwire:
            result = admin_open(port=8765)

        assert result == 0
        find_token.assert_call(args=(), kwargs={})
        tripwire.http.assert_request(
            "POST",
            HANDOFF_URL,
            headers=IsPartialDict({"Authorization": "Bearer test-token"}),
            body="",
        ).assert_response(200, IsPartialDict(), IsStr())
        browser_open.assert_call(args=(server_login_url,), kwargs={})
        # Server's login_url MUST be opened verbatim -- no client-side
        # construction, no ?auth= appended.
        assert opened_urls == [server_login_url]

    def test_cli_handles_handoff_401_gracefully(self, capsys):
        """A 401 from /handoff MUST exit non-zero with a clear error message."""
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns("bad-token")
        http_error = urllib.error.HTTPError(
            url=HANDOFF_URL,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        tripwire.http.mock_error("POST", HANDOFF_URL, raises=http_error)

        with tripwire:
            result = admin_open(port=8765)

        assert result == 1
        find_token.assert_call(args=(), kwargs={})
        tripwire.http.assert_request(
            "POST",
            HANDOFF_URL,
            headers=IsPartialDict({"Authorization": "Bearer bad-token"}),
            body="",
            raised=http_error,
        )
        captured = capsys.readouterr()
        # Error MUST be printed to stderr and mention the auth failure.
        # Browser is never invoked on failure (no webbrowser mock registered,
        # so any call would raise UnmockedInteractionError).
        assert "401" in captured.err

    def test_browser_failure_prints_url(self, capsys):
        find_token = tripwire.mock("spellbook.admin.cli:_find_mcp_token")
        find_token.returns("test-token")
        server_login_url = (
            "http://127.0.0.1:8765/admin/api/auth/handoff/fixed-id-xyz"
        )
        browser_open = tripwire.mock("spellbook.admin.cli:webbrowser.open")
        browser_open.raises(Exception("No browser"))
        tripwire.http.mock_response(
            "POST",
            HANDOFF_URL,
            json={"login_url": server_login_url},
            status=200,
        )

        with tripwire:
            result = admin_open(port=8765)

        assert result == 0
        find_token.assert_call(args=(), kwargs={})
        tripwire.http.assert_request(
            "POST",
            HANDOFF_URL,
            headers=IsPartialDict({"Authorization": "Bearer test-token"}),
            body="",
        ).assert_response(200, IsPartialDict(), IsStr())
        browser_open.assert_call(
            args=(server_login_url,), kwargs={}, raised=IsInstance(Exception)
        )
        captured = capsys.readouterr()
        # The fallback printout MUST show the server-supplied login_url verbatim.
        assert server_login_url in captured.err


class TestMain:
    def test_no_command_prints_help(self, capsys):
        result = main([])
        assert result == 0

    def test_open_command(self):
        call_args: dict = {}

        def record_admin_open(**kwargs):
            call_args.update(kwargs)
            return 0

        admin_open_mock = tripwire.mock("spellbook.admin.cli:admin_open")
        admin_open_mock.calls(record_admin_open)

        with tripwire:
            result = main(["open", "--port", "9999"])

        assert result == 0
        admin_open_mock.assert_call(args=(), kwargs={"port": 9999})
        assert call_args == {"port": 9999}
