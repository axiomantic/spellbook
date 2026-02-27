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


class TestTtsSessionSet:
    """tts_session_set() MCP tool."""

    def test_updates_session_state(self):
        from spellbook_mcp.config_tools import _session_states, _session_activity

        _session_states.clear()
        _session_activity.clear()

        result = server.tts_session_set.fn(enabled=False, voice="bf_emma", volume=0.5)

        assert result["status"] == "ok"
        assert result["session_tts"]["enabled"] is False
        assert result["session_tts"]["voice"] == "bf_emma"
        assert result["session_tts"]["volume"] == 0.5

        _session_states.clear()
        _session_activity.clear()

    def test_partial_update_preserves_other_keys(self):
        from spellbook_mcp.config_tools import _session_states, _session_activity, _get_session_state

        _session_states.clear()
        _session_activity.clear()

        # Set initial values
        state = _get_session_state()
        state["tts"] = {"enabled": True, "voice": "af_heart", "volume": 0.3}

        result = server.tts_session_set.fn(voice="bf_emma")  # Only change voice

        assert result["session_tts"]["voice"] == "bf_emma"
        assert result["session_tts"]["enabled"] is True  # Unchanged
        assert result["session_tts"]["volume"] == 0.3  # Unchanged

        _session_states.clear()
        _session_activity.clear()


class TestTtsConfigSet:
    """tts_config_set() MCP tool."""

    def test_sets_all_config_keys(self, tmp_path):
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        with patch("spellbook_mcp.config_tools.get_config_path", return_value=config_file):
            with patch("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", tmp_path / "config.lock"):
                result = server.tts_config_set.fn(enabled=True, voice="bf_emma", volume=0.5)

        assert result["status"] == "ok"
        assert result["config"]["tts_enabled"] is True
        assert result["config"]["tts_voice"] == "bf_emma"
        assert result["config"]["tts_volume"] == 0.5

    def test_partial_update_only_sets_provided(self, tmp_path):
        config_file = tmp_path / "spellbook.json"
        config_file.write_text('{"tts_enabled": true}')
        with patch("spellbook_mcp.config_tools.get_config_path", return_value=config_file):
            with patch("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", tmp_path / "config.lock"):
                result = server.tts_config_set.fn(voice="am_adam")

        assert result["config"]["tts_voice"] == "am_adam"
        assert result["config"]["tts_enabled"] is True  # Preserved


class TestApiSpeakEndpoint:
    """POST /api/speak custom route tests.

    Uses mcp.http_app() to obtain the Starlette ASGI app for TestClient.
    This creates a full HTTP transport app that includes all custom routes.
    """

    @pytest.mark.asyncio
    async def test_success_returns_200(self):
        from starlette.testclient import TestClient

        mock_result = {"ok": True, "elapsed": 1.0, "wav_path": "/tmp/test.wav"}
        with patch("spellbook_mcp.tts.speak", new_callable=AsyncMock, return_value=mock_result):
            app = server.mcp.http_app(transport="http")
            client = TestClient(app)
            response = client.post("/api/speak", json={"text": "hello"})
        assert response.status_code == 200
        assert response.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_no_text_returns_400(self):
        from starlette.testclient import TestClient

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post("/api/speak", json={})
        assert response.status_code == 400
        assert "no text" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self):
        from starlette.testclient import TestClient

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post(
            "/api/speak",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "invalid JSON" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_passes_voice_and_volume_to_speak(self):
        from starlette.testclient import TestClient

        mock_result = {"ok": True, "elapsed": 0.5, "wav_path": "/tmp/x.wav"}
        with patch("spellbook_mcp.tts.speak", new_callable=AsyncMock, return_value=mock_result) as mock_speak:
            app = server.mcp.http_app(transport="http")
            client = TestClient(app)
            response = client.post(
                "/api/speak",
                json={"text": "hi", "voice": "bf_emma", "volume": 0.7},
            )
        assert response.status_code == 200
        mock_speak.assert_called_once_with("hi", voice="bf_emma", volume=0.7)

    @pytest.mark.asyncio
    async def test_tts_error_returns_500(self):
        from starlette.testclient import TestClient

        mock_result = {"error": "TTS not available"}
        with patch("spellbook_mcp.tts.speak", new_callable=AsyncMock, return_value=mock_result):
            app = server.mcp.http_app(transport="http")
            client = TestClient(app)
            response = client.post("/api/speak", json={"text": "hello"})
        assert response.status_code == 500
        body = response.json()
        assert "error" in body
        assert body.get("ok") is not True
        assert body["error"] == "TTS not available"
