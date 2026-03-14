"""CLI command tests for spellbook admin open."""

import json
from unittest.mock import MagicMock, patch

import pytest

from spellbook_mcp.admin.cli import admin_open, main


class TestAdminOpen:
    def test_no_token_returns_error(self):
        with patch(
            "spellbook_mcp.admin.cli._find_mcp_token", return_value=None
        ):
            assert admin_open() == 1

    def test_server_unreachable_returns_error(self, tmp_path):
        import urllib.error

        with (
            patch(
                "spellbook_mcp.admin.cli._find_mcp_token",
                return_value="test-token",
            ),
            patch(
                "spellbook_mcp.admin.cli.urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
            ),
        ):
            assert admin_open(port=19999) == 1

    def test_successful_open(self, tmp_path):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"exchange_token": "test-exchange"}
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "spellbook_mcp.admin.cli._find_mcp_token",
                return_value="test-token",
            ),
            patch(
                "spellbook_mcp.admin.cli.urllib.request.urlopen",
                return_value=mock_response,
            ),
            patch("spellbook_mcp.admin.cli.webbrowser.open") as mock_browser,
        ):
            result = admin_open(port=8765)
            assert result == 0
            mock_browser.assert_called_once()
            call_url = mock_browser.call_args[0][0]
            assert "callback" in call_url
            assert "test-exchange" in call_url

    def test_browser_failure_prints_url(self, capsys):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"exchange_token": "test-exchange"}
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "spellbook_mcp.admin.cli._find_mcp_token",
                return_value="test-token",
            ),
            patch(
                "spellbook_mcp.admin.cli.urllib.request.urlopen",
                return_value=mock_response,
            ),
            patch(
                "spellbook_mcp.admin.cli.webbrowser.open",
                side_effect=Exception("No browser"),
            ),
        ):
            result = admin_open(port=8765)
            assert result == 0
            captured = capsys.readouterr()
            assert "callback" in captured.err
            assert "test-exchange" in captured.err


class TestMain:
    def test_no_command_prints_help(self, capsys):
        result = main([])
        assert result == 0

    def test_open_command(self):
        with patch("spellbook_mcp.admin.cli.admin_open", return_value=0) as mock:
            result = main(["open", "--port", "9999"])
            assert result == 0
            mock.assert_called_once_with(port=9999)
