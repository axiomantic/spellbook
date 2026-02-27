"""Tests for TTS MCP tool functions in server.py.

Uses .fn to access the underlying function from the FunctionTool wrapper.
All spellbook_mcp.tts functions are mocked. Tests verify tool behavior,
argument handling, and return contracts.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spellbook_mcp import server


class TestKokoroSpeak:
    """kokoro_speak() MCP tool."""

    @pytest.mark.asyncio
    async def test_success_returns_ok(self):
        mock_result = {"ok": True, "elapsed": 1.23, "wav_path": "/tmp/test.wav"}
        with patch("spellbook_mcp.tts.speak", new_callable=AsyncMock, return_value=mock_result):
            result = await server.kokoro_speak.fn(text="hello world")
        assert result["ok"] is True
        assert result["elapsed"] == 1.23

    @pytest.mark.asyncio
    async def test_not_available_returns_error(self):
        mock_result = {"error": "TTS not available. Missing kokoro"}
        with patch("spellbook_mcp.tts.speak", new_callable=AsyncMock, return_value=mock_result):
            result = await server.kokoro_speak.fn(text="hello")
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_passes_voice_and_volume(self):
        with patch("spellbook_mcp.tts.speak", new_callable=AsyncMock) as mock_speak:
            mock_speak.return_value = {"ok": True, "elapsed": 1.0, "wav_path": "/tmp/x.wav"}
            await server.kokoro_speak.fn(text="hi", voice="bf_emma", volume=0.5)
            mock_speak.assert_called_once_with("hi", voice="bf_emma", volume=0.5)


class TestKokoroStatus:
    """kokoro_status() MCP tool."""

    def test_returns_status_dict(self):
        mock_status = {
            "available": True,
            "enabled": True,
            "model_loaded": False,
            "voice": "af_heart",
            "volume": 0.3,
            "error": None,
        }
        with patch("spellbook_mcp.tts.get_status", return_value=mock_status):
            result = server.kokoro_status.fn()
        assert result == mock_status
