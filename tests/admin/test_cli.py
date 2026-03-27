"""CLI command tests for spellbook admin open."""

import json
import urllib.error
import urllib.request

import bigfoot
import pytest
from dirty_equals import IsInstance, IsStr

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
    def test_no_token_returns_error(self):
        mock_token = bigfoot.mock("spellbook.admin.cli:_find_mcp_token")
        mock_token.returns(None)

        with bigfoot:
            assert admin_open() == 1

        mock_token.assert_call(args=(), kwargs={})

    def test_server_unreachable_returns_error(self):
        mock_token = bigfoot.mock("spellbook.admin.cli:_find_mcp_token")
        mock_token.returns("test-token")

        mock_urlopen = bigfoot.mock("spellbook.admin.cli:urllib.request.urlopen")
        mock_urlopen.raises(urllib.error.URLError("Connection refused"))

        with bigfoot:
            assert admin_open(port=19999) == 1

        mock_token.assert_call(args=(), kwargs={})
        mock_urlopen.assert_call(
            args=(IsInstance(urllib.request.Request),),
            kwargs={"timeout": 5},
            raised=IsInstance(urllib.error.URLError),
        )

    def test_successful_open(self):
        mock_token = bigfoot.mock("spellbook.admin.cli:_find_mcp_token")
        mock_token.returns("test-token")

        fake_resp = _FakeResponse({"exchange_token": "test-exchange"})
        mock_urlopen = bigfoot.mock("spellbook.admin.cli:urllib.request.urlopen")
        mock_urlopen.returns(fake_resp)

        mock_browser = bigfoot.mock("spellbook.admin.cli:webbrowser.open")
        mock_browser.returns(None)

        with bigfoot:
            result = admin_open(port=8765)

        assert result == 0
        mock_token.assert_call(args=(), kwargs={})
        mock_urlopen.assert_call(
            args=(IsInstance(urllib.request.Request),),
            kwargs={"timeout": 5},
        )
        mock_browser.assert_call(
            args=(IsStr(regex=r".*callback.*auth=test-exchange.*"),),
            kwargs={},
        )

    def test_browser_failure_prints_url(self, capsys):
        mock_token = bigfoot.mock("spellbook.admin.cli:_find_mcp_token")
        mock_token.returns("test-token")

        fake_resp = _FakeResponse({"exchange_token": "test-exchange"})
        mock_urlopen = bigfoot.mock("spellbook.admin.cli:urllib.request.urlopen")
        mock_urlopen.returns(fake_resp)

        mock_browser = bigfoot.mock("spellbook.admin.cli:webbrowser.open")
        mock_browser.raises(Exception("No browser"))

        with bigfoot:
            result = admin_open(port=8765)

        assert result == 0
        captured = capsys.readouterr()
        assert "callback" in captured.err
        assert "test-exchange" in captured.err
        mock_token.assert_call(args=(), kwargs={})
        mock_urlopen.assert_call(
            args=(IsInstance(urllib.request.Request),),
            kwargs={"timeout": 5},
        )
        mock_browser.assert_call(
            args=(IsStr(regex=r".*callback.*auth=test-exchange.*"),),
            kwargs={},
            raised=IsInstance(Exception),
        )


class TestMain:
    def test_no_command_prints_help(self, capsys):
        result = main([])
        assert result == 0

    def test_open_command(self):
        mock_open = bigfoot.mock("spellbook.admin.cli:admin_open")
        mock_open.returns(0)

        with bigfoot:
            result = main(["open", "--port", "9999"])

        assert result == 0
        mock_open.assert_call(args=(), kwargs={"port": 9999})
