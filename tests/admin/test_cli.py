"""CLI command tests for spellbook admin open."""

import json
import urllib.error
import urllib.request

from spellbook.admin.cli import admin_open, main


class _FakeResponse:
    """Minimal context-manager response with .read()."""

    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _UrlopenRecorder:
    """Records the Request object passed to urlopen and returns a fixed response."""

    def __init__(self, response: _FakeResponse):
        self.response = response
        self.requests: list[urllib.request.Request] = []

    def __call__(self, req, *args, **kwargs):
        # urlopen may be called with either a Request or a url string;
        # in CLI we always pass a Request.
        self.requests.append(req)
        return self.response


class TestAdminOpen:
    def test_no_token_returns_error(self, monkeypatch):
        monkeypatch.setattr("spellbook.admin.cli._find_mcp_token", lambda: None)

        assert admin_open() == 1

    def test_server_unreachable_returns_error(self, monkeypatch):
        monkeypatch.setattr("spellbook.admin.cli._find_mcp_token", lambda: "test-token")
        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen",
            lambda *a, **kw: (_ for _ in ()).throw(
                urllib.error.URLError("Connection refused")
            ),
        )

        assert admin_open(port=19999) == 1

    def test_cli_posts_to_handoff_endpoint(self, monkeypatch):
        """The CLI MUST POST to /admin/api/auth/handoff (not /exchange)."""
        monkeypatch.setattr(
            "spellbook.admin.cli._find_mcp_token", lambda: "test-token"
        )

        fake_resp = _FakeResponse(
            {"login_url": "http://127.0.0.1:8765/admin/api/auth/handoff/abc123"}
        )
        recorder = _UrlopenRecorder(fake_resp)
        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen", recorder
        )
        monkeypatch.setattr(
            "spellbook.admin.cli.webbrowser.open", lambda url: None
        )

        result = admin_open(port=8765)

        assert result == 0
        assert len(recorder.requests) == 1
        req = recorder.requests[0]
        assert req.full_url == "http://127.0.0.1:8765/admin/api/auth/handoff"
        assert req.get_method() == "POST"

    def test_cli_sends_bearer_token_in_authorization_header(self, monkeypatch):
        """The MCP token MUST be sent in Authorization: Bearer <token>, not in body."""
        monkeypatch.setattr(
            "spellbook.admin.cli._find_mcp_token", lambda: "secret-mcp-token"
        )

        fake_resp = _FakeResponse(
            {"login_url": "http://127.0.0.1:8765/admin/api/auth/handoff/abc123"}
        )
        recorder = _UrlopenRecorder(fake_resp)
        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen", recorder
        )
        monkeypatch.setattr(
            "spellbook.admin.cli.webbrowser.open", lambda url: None
        )

        result = admin_open(port=8765)

        assert result == 0
        assert len(recorder.requests) == 1
        req = recorder.requests[0]
        # urllib normalizes header names to capitalized form.
        assert req.get_header("Authorization") == "Bearer secret-mcp-token"
        # Body MUST be empty -- no token in body.
        body = req.data
        assert body == b""

    def test_cli_opens_url_from_response_login_url_field(self, monkeypatch):
        """The CLI MUST open EXACTLY the login_url returned by the server."""
        monkeypatch.setattr(
            "spellbook.admin.cli._find_mcp_token", lambda: "test-token"
        )

        server_login_url = (
            "http://127.0.0.1:8765/admin/api/auth/handoff/fixed-test-id-abc123"
        )
        fake_resp = _FakeResponse({"login_url": server_login_url})
        recorder = _UrlopenRecorder(fake_resp)
        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen", recorder
        )

        opened_urls: list[str] = []
        monkeypatch.setattr(
            "spellbook.admin.cli.webbrowser.open",
            lambda url: opened_urls.append(url),
        )

        result = admin_open(port=8765)

        assert result == 0
        # Server's login_url MUST be opened verbatim -- no client-side
        # construction, no ?auth= appended.
        assert opened_urls == [server_login_url]

    def test_cli_handles_handoff_401_gracefully(self, capsys, monkeypatch):
        """A 401 from /handoff MUST exit non-zero with a clear error message."""
        monkeypatch.setattr(
            "spellbook.admin.cli._find_mcp_token", lambda: "bad-token"
        )

        def raise_401(*args, **kwargs):
            raise urllib.error.HTTPError(
                url="http://127.0.0.1:8765/admin/api/auth/handoff",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=None,
            )

        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen", raise_401
        )

        opened_urls: list[str] = []
        monkeypatch.setattr(
            "spellbook.admin.cli.webbrowser.open",
            lambda url: opened_urls.append(url),
        )

        result = admin_open(port=8765)

        assert result == 1
        # Browser MUST NOT be opened on failure.
        assert opened_urls == []
        captured = capsys.readouterr()
        # Error MUST be printed to stderr and mention the auth failure.
        assert "401" in captured.err

    def test_browser_failure_prints_url(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "spellbook.admin.cli._find_mcp_token", lambda: "test-token"
        )

        server_login_url = (
            "http://127.0.0.1:8765/admin/api/auth/handoff/fixed-id-xyz"
        )
        fake_resp = _FakeResponse({"login_url": server_login_url})
        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen",
            lambda *a, **kw: fake_resp,
        )

        def raise_browser_error(url):
            raise Exception("No browser")

        monkeypatch.setattr(
            "spellbook.admin.cli.webbrowser.open",
            raise_browser_error,
        )

        result = admin_open(port=8765)

        assert result == 0
        captured = capsys.readouterr()
        # The fallback printout MUST show the server-supplied login_url verbatim.
        assert server_login_url in captured.err


class TestMain:
    def test_no_command_prints_help(self, capsys):
        result = main([])
        assert result == 0

    def test_open_command(self, monkeypatch):
        call_args = {}

        def mock_admin_open(**kwargs):
            call_args.update(kwargs)
            return 0

        monkeypatch.setattr("spellbook.admin.cli.admin_open", mock_admin_open)

        result = main(["open", "--port", "9999"])

        assert result == 0
        assert call_args == {"port": 9999}
