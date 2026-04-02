"""Tests for TTS MCP tool functions in server.py.

Uses .fn to access the underlying function from the FunctionTool wrapper.
All spellbook.notifications.tts functions are mocked. Tests verify tool behavior,
argument handling, and return contracts.
"""

import pytest

from spellbook import server


class TestKokoroSpeak:
    """kokoro_speak() MCP tool."""

    @pytest.mark.asyncio
    async def test_success_returns_ok(self, monkeypatch):
        mock_result = {"ok": True, "elapsed": 1.23, "wav_path": "/tmp/test.wav"}

        async def _mock_speak(*args, **kwargs):
            return mock_result

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        result = await server.kokoro_speak.fn(text="hello world")

        assert result["ok"] is True
        assert result["elapsed"] == 1.23

    @pytest.mark.asyncio
    async def test_not_available_returns_error(self, monkeypatch):
        mock_result = {"error": "TTS not available. Missing kokoro"}

        async def _mock_speak(*args, **kwargs):
            return mock_result

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        result = await server.kokoro_speak.fn(text="hello")

        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_passes_voice_and_volume(self, monkeypatch):
        calls = []

        async def _mock_speak(*args, **kwargs):
            calls.append((args, kwargs))
            return {"ok": True, "elapsed": 1.0, "wav_path": "/tmp/x.wav"}

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        await server.kokoro_speak.fn(text="hi", voice="bf_emma", volume=0.5)

        assert len(calls) == 1
        assert calls[0][0] == ("hi",)
        assert calls[0][1]["voice"] == "bf_emma"
        assert calls[0][1]["volume"] == 0.5

    @pytest.mark.asyncio
    async def test_passes_session_id(self, monkeypatch):
        calls = []

        async def _mock_speak(*args, **kwargs):
            calls.append((args, kwargs))
            return {"ok": True, "elapsed": 1.0, "wav_path": "/tmp/x.wav"}

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        await server.kokoro_speak.fn(text="hi", session_id="sess-123")

        assert len(calls) == 1
        assert calls[0][1]["session_id"] == "sess-123"


class TestKokoroStatus:
    """kokoro_status() MCP tool."""

    def test_returns_status_dict(self, monkeypatch):
        mock_status = {
            "available": True,
            "enabled": True,
            "model_loaded": False,
            "voice": "af_heart",
            "volume": 0.3,
            "error": None,
        }
        monkeypatch.setattr(
            "spellbook.notifications.tts.get_status",
            lambda **kw: mock_status,
        )

        result = server.kokoro_status.fn()

        assert result == mock_status

    def test_passes_session_id(self, monkeypatch):
        calls = []

        def _mock_get_status(**kwargs):
            calls.append(kwargs)
            return {
                "available": True,
                "enabled": True,
                "model_loaded": False,
                "voice": "af_heart",
                "volume": 0.3,
                "error": None,
            }

        monkeypatch.setattr("spellbook.notifications.tts.get_status", _mock_get_status)

        server.kokoro_status.fn(session_id="sess-456")

        assert len(calls) == 1
        assert calls[0]["session_id"] == "sess-456"


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
        state["tts"] = {"enabled": True, "voice": "af_heart", "volume": 0.3}

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
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_file)
        monkeypatch.setattr(config_mod, "CONFIG_LOCK_PATH", tmp_path / "config.lock")

        result = server.tts_config_set.fn(enabled=True, voice="bf_emma", volume=0.5)

        assert result["status"] == "ok"
        assert result["config"]["tts_enabled"] is True
        assert result["config"]["tts_voice"] == "bf_emma"
        assert result["config"]["tts_volume"] == 0.5

    def test_partial_update_only_sets_provided(self, tmp_path, monkeypatch):
        import spellbook.core.config as config_mod

        config_file = tmp_path / "spellbook.json"
        config_file.write_text('{"tts_enabled": true}')
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_file)
        monkeypatch.setattr(config_mod, "CONFIG_LOCK_PATH", tmp_path / "config.lock")

        result = server.tts_config_set.fn(voice="am_adam")

        assert result["config"]["tts_voice"] == "am_adam"
        assert result["config"]["tts_enabled"] is True  # Preserved


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

    def test_success_returns_200(self, monkeypatch):
        from starlette.testclient import TestClient

        mock_result = {"ok": True, "elapsed": 1.0, "wav_path": "/tmp/test.wav"}

        async def _mock_speak(*args, **kwargs):
            return mock_result

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post("/api/speak", json={"text": "hello"})

        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_no_text_returns_400(self):
        from starlette.testclient import TestClient

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post("/api/speak", json={})
        assert response.status_code == 400
        assert "no text" in response.json()["error"]

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
        assert "invalid JSON" in response.json()["error"]

    def test_passes_voice_and_volume_to_speak(self, monkeypatch):
        from starlette.testclient import TestClient

        calls = []

        async def _mock_speak(*args, **kwargs):
            calls.append((args, kwargs))
            return {"ok": True, "elapsed": 0.5, "wav_path": "/tmp/x.wav"}

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post(
            "/api/speak",
            json={"text": "hi", "voice": "bf_emma", "volume": 0.7},
        )

        assert response.status_code == 200
        assert len(calls) == 1
        assert calls[0][0] == ("hi",)
        assert calls[0][1]["voice"] == "bf_emma"
        assert calls[0][1]["volume"] == 0.7

    def test_tts_error_returns_500(self, monkeypatch):
        from starlette.testclient import TestClient

        async def _mock_speak(*args, **kwargs):
            return {"error": "TTS not available"}

        monkeypatch.setattr("spellbook.notifications.tts.speak", _mock_speak)

        app = server.mcp.http_app(transport="http")
        client = TestClient(app)
        response = client.post("/api/speak", json={"text": "hello"})

        assert response.status_code == 500
        body = response.json()
        assert "error" in body
        assert body.get("ok") is not True
        assert body["error"] == "TTS not available"
