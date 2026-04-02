"""CLI command tests for spellbook admin open."""

import json
import re
import urllib.error
import urllib.request

import pytest

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

    def test_successful_open(self, monkeypatch):
        monkeypatch.setattr("spellbook.admin.cli._find_mcp_token", lambda: "test-token")

        fake_resp = _FakeResponse({"exchange_token": "test-exchange"})
        monkeypatch.setattr(
            "spellbook.admin.cli.urllib.request.urlopen",
            lambda *a, **kw: fake_resp,
        )

        opened_urls = []
        monkeypatch.setattr(
            "spellbook.admin.cli.webbrowser.open",
            lambda url: opened_urls.append(url),
        )

        result = admin_open(port=8765)

        assert result == 0
        assert len(opened_urls) == 1
        assert "callback" in opened_urls[0]
        assert "auth=test-exchange" in opened_urls[0]

    def test_browser_failure_prints_url(self, capsys, monkeypatch):
        monkeypatch.setattr("spellbook.admin.cli._find_mcp_token", lambda: "test-token")

        fake_resp = _FakeResponse({"exchange_token": "test-exchange"})
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
        assert "callback" in captured.err
        assert "test-exchange" in captured.err


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
