"""Tests for TTS MCP tool functions in server.py.

Uses .fn to access the underlying function from the FunctionTool wrapper.
All spellbook.notifications.tts functions are mocked. Tests verify tool behavior,
argument handling, and return contracts.
"""

import bigfoot
import pytest

from spellbook import server


def _async_return(value):
    """Create an async callable that returns value, for mocking async functions."""
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestTtsSpeak:
    """tts_speak() MCP tool."""

    @pytest.mark.asyncio
    async def test_success_returns_ok(self):
        mock_result = {"ok": True, "elapsed": 1.23, "wav_path": "/tmp/test.wav"}
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return(mock_result))

        async with bigfoot:
            result = await server.tts_speak.fn(text="hello world")

        assert result["ok"] is True
        assert result["elapsed"] == 1.23
        mock_speak.assert_call(args=("hello world",), kwargs={"voice": None, "volume": None, "session_id": None})

    @pytest.mark.asyncio
    async def test_not_available_returns_error(self):
        mock_result = {"error": "TTS not available. Server unreachable"}
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return(mock_result))

        async with bigfoot:
            result = await server.tts_speak.fn(text="hello")

        assert result == {"error": "TTS not available. Server unreachable"}
        mock_speak.assert_call(args=("hello",), kwargs={"voice": None, "volume": None, "session_id": None})

    @pytest.mark.asyncio
    async def test_passes_voice_and_volume(self):
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return({"ok": True, "elapsed": 1.0, "wav_path": "/tmp/x.wav"}))

        async with bigfoot:
            await server.tts_speak.fn(text="hi", voice="test-voice", volume=0.5)

        mock_speak.assert_call(args=("hi",), kwargs={"voice": "test-voice", "volume": 0.5, "session_id": None})

    @pytest.mark.asyncio
    async def test_passes_session_id(self):
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return({"ok": True, "elapsed": 1.0, "wav_path": "/tmp/x.wav"}))

        async with bigfoot:
            await server.tts_speak.fn(text="hi", session_id="sess-123")

        mock_speak.assert_call(args=("hi",), kwargs={"voice": None, "volume": None, "session_id": "sess-123"})


class TestTtsStatus:
    """tts_status() MCP tool."""

    def test_returns_status_dict(self):
        mock_status = {
            "available": True,
            "enabled": True,
            "server_reachable": False,
            "voice": "",
            "volume": 0.3,
            "tts_wyoming_host": "localhost",
            "tts_wyoming_port": 10200,
            "error": None,
        }
        mock_get = bigfoot.mock("spellbook.notifications.tts:get_status")
        mock_get.returns(mock_status)

        with bigfoot:
            result = server.tts_status.fn()

        assert result == mock_status
        mock_get.assert_call(kwargs={"session_id": None})

    def test_passes_session_id(self):
        mock_status = {
            "available": True,
            "enabled": True,
            "server_reachable": False,
            "voice": "",
            "volume": 0.3,
            "tts_wyoming_host": "localhost",
            "tts_wyoming_port": 10200,
            "error": None,
        }
        mock_get = bigfoot.mock("spellbook.notifications.tts:get_status")
        mock_get.returns(mock_status)

        with bigfoot:
            server.tts_status.fn(session_id="sess-456")

        mock_get.assert_call(kwargs={"session_id": "sess-456"})


class TestTtsSessionSet:
    """tts_session_set() MCP tool."""

    def test_updates_session_state(self):
        from spellbook.core.config import _session_states, _session_activity

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
        from spellbook.core.config import _session_states, _session_activity, _get_session_state

        _session_states.clear()
        _session_activity.clear()

        # Set initial values
        state = _get_session_state()
        state["tts"] = {"enabled": True, "voice": "test-voice", "volume": 0.3}

        result = server.tts_session_set.fn(voice="bf_emma")  # Only change voice

        assert result["session_tts"]["voice"] == "bf_emma"
        assert result["session_tts"]["enabled"] is True  # Unchanged
        assert result["session_tts"]["volume"] == 0.3  # Unchanged

        _session_states.clear()
        _session_activity.clear()


class TestTtsConfigSet:
    """tts_config_set() MCP tool."""

    def test_sets_all_config_keys(self, tmp_path, monkeypatch):
        import spellbook.core.config as config_mod

        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        mock_config_path = bigfoot.mock("spellbook.core.config:get_config_path")
        mock_config_path.returns(config_file)
        monkeypatch.setattr(config_mod, "CONFIG_LOCK_PATH", tmp_path / "config.lock")

        with bigfoot:
            result = server.tts_config_set.fn(enabled=True, voice="bf_emma", volume=0.5)

        assert result["status"] == "ok"
        assert result["config"]["tts_enabled"] is True
        assert result["config"]["tts_voice"] == "bf_emma"
        assert result["config"]["tts_volume"] == 0.5
        mock_config_path.assert_call(args=(), kwargs={})

    def test_partial_update_only_sets_provided(self, tmp_path, monkeypatch):
        import spellbook.core.config as config_mod

        config_file = tmp_path / "spellbook.json"
        config_file.write_text('{"tts_enabled": true}')
        mock_config_path = bigfoot.mock("spellbook.core.config:get_config_path")
        mock_config_path.returns(config_file)
        monkeypatch.setattr(config_mod, "CONFIG_LOCK_PATH", tmp_path / "config.lock")

        with bigfoot:
            result = server.tts_config_set.fn(voice="am_adam")

        assert result["config"]["tts_voice"] == "am_adam"
        assert result["config"]["tts_enabled"] is True  # Preserved
        mock_config_path.assert_call(args=(), kwargs={})


class TestApiSpeakEndpoint:
    """POST /api/speak custom route tests.

    Uses mcp.http_app() to obtain the Starlette ASGI app for TestClient.
    This creates a full HTTP transport app that includes all custom routes.
    """

    @pytest.fixture(autouse=True)
    def _register_routes(self):
        """Ensure custom routes are registered before testing HTTP endpoints."""
        from spellbook.mcp.server import register_all_tools
        register_all_tools()

    def test_success_returns_200(self):
        from starlette.testclient import TestClient

        mock_result = {"ok": True, "elapsed": 1.0, "wav_path": "/tmp/test.wav"}
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return(mock_result))

        with bigfoot:
            app = server.mcp.http_app(transport="http")
            client = TestClient(app)
            response = client.post("/api/speak", json={"text": "hello"})

        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_speak.assert_call(args=("hello",), kwargs={"voice": None, "volume": None, "session_id": None})

    def test_no_text_returns_400(self):
        from starlette.testclient import TestClient

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post("/api/speak", json={})
        assert response.status_code == 400
        assert response.json()["error"] == "no text provided"

    def test_invalid_json_returns_400(self):
        from starlette.testclient import TestClient

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post(
            "/api/speak",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid JSON"

    def test_passes_voice_and_volume_to_speak(self):
        from starlette.testclient import TestClient

        mock_result = {"ok": True, "elapsed": 0.5, "wav_path": "/tmp/x.wav"}
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return(mock_result))

        with bigfoot:
            app = server.mcp.http_app(transport="http")
            client = TestClient(app)
            response = client.post(
                "/api/speak",
                json={"text": "hi", "voice": "bf_emma", "volume": 0.7},
            )

        assert response.status_code == 200
        mock_speak.assert_call(args=("hi",), kwargs={"voice": "bf_emma", "volume": 0.7, "session_id": None})

    def test_tts_error_returns_500(self):
        from starlette.testclient import TestClient

        mock_result = {"error": "TTS not available"}
        mock_speak = bigfoot.mock("spellbook.notifications.tts:speak")
        mock_speak.calls(_async_return(mock_result))

        with bigfoot:
            app = server.mcp.http_app(transport="http")
            client = TestClient(app)
            response = client.post("/api/speak", json={"text": "hello"})

        assert response.status_code == 500
        body = response.json()
        assert "error" in body
        assert body.get("ok") is not True
        assert body["error"] == "TTS not available"
        mock_speak.assert_call(args=("hello",), kwargs={"voice": None, "volume": None, "session_id": None})
