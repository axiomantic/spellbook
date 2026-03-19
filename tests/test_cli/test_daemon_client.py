"""Tests for spellbook.cli.daemon_client - HTTP/WebSocket client."""

import pytest

from spellbook.cli import daemon_client
from spellbook.cli.daemon_client import get_token, daemon_request


class TestGetToken:
    """Tests for get_token()."""

    def test_returns_none_when_no_file(self, tmp_path, monkeypatch):
        """When .mcp-token file doesn't exist, return None."""
        token_path = tmp_path / ".local" / "spellbook" / ".mcp-token"
        assert not token_path.exists()
        monkeypatch.setattr(daemon_client, "_token_path", lambda: token_path)
        result = get_token()
        assert result is None

    def test_reads_token_from_file(self, tmp_path, monkeypatch):
        """When .mcp-token exists, read and return stripped content."""
        token_path = tmp_path / ".local" / "spellbook" / ".mcp-token"
        token_path.parent.mkdir(parents=True)
        token_path.write_text("  test-token-123  \n")
        monkeypatch.setattr(daemon_client, "_token_path", lambda: token_path)
        result = get_token()
        assert result == "test-token-123"

    def test_returns_none_for_empty_file(self, tmp_path, monkeypatch):
        """When .mcp-token exists but is empty, return None."""
        token_path = tmp_path / ".local" / "spellbook" / ".mcp-token"
        token_path.parent.mkdir(parents=True)
        token_path.write_text("   \n")
        monkeypatch.setattr(daemon_client, "_token_path", lambda: token_path)
        result = get_token()
        assert result is None


class TestDaemonRequest:
    """Tests for daemon_request()."""

    def test_raises_on_connection_error(self):
        """Should raise ConnectionError when daemon is not running."""
        with pytest.raises((ConnectionError, OSError)):
            daemon_request("/health", host="127.0.0.1", port=1)

    def test_default_method_is_get(self, monkeypatch):
        """Verify the function signature has GET as default method."""
        import inspect

        sig = inspect.signature(daemon_request)
        assert sig.parameters["method"].default == "GET"

    def test_accepts_data_parameter(self):
        """Verify the function accepts a data parameter."""
        import inspect

        sig = inspect.signature(daemon_request)
        assert "data" in sig.parameters


class TestStreamEvents:
    """Tests for stream_events()."""

    def test_stream_events_is_async(self):
        """stream_events should be an async generator or coroutine."""
        import asyncio
        import inspect

        from spellbook.cli.daemon_client import stream_events

        assert inspect.isasyncgenfunction(stream_events) or inspect.iscoroutinefunction(
            stream_events
        )
