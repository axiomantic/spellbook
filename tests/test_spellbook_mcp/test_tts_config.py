"""Tests for TTS session state and config in config_tools.py.

Tests the TTS sub-dict in session state, tts_session_set, and tts_session_get
functions. These are the settings layer only -- no kokoro availability checks.
"""

from datetime import datetime
from unittest.mock import patch


class TestSessionStateTtsKey:
    """_get_session_state() includes 'tts' key for TTS overrides."""

    def test_new_session_has_tts_key(self):
        from spellbook_mcp.config_tools import (
            _get_session_state,
            _session_activity,
            _session_states,
        )

        _session_states.clear()
        _session_activity.clear()
        state = _get_session_state("test-tts-session")
        assert "tts" in state
        assert state["tts"] == {}
        _session_states.clear()
        _session_activity.clear()

    def test_existing_session_gets_tts_key_backfilled(self):
        from spellbook_mcp.config_tools import (
            _get_session_state,
            _session_activity,
            _session_states,
        )

        _session_states.clear()
        _session_activity.clear()
        # Simulate an existing session without tts key
        _session_states["legacy-session"] = {"mode": None}
        _session_activity["legacy-session"] = datetime.now()
        state = _get_session_state("legacy-session")
        assert "tts" in state
        assert state["tts"] == {}
        _session_states.clear()
        _session_activity.clear()


class TestTtsSessionSet:
    """tts_session_set() updates TTS overrides in session state."""

    def test_sets_all_fields(self):
        from spellbook_mcp.config_tools import (
            _session_activity,
            _session_states,
            tts_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        result = tts_session_set(enabled=False, voice="bf_emma", volume=0.5)

        assert result["status"] == "ok"
        assert result["session_tts"]["enabled"] is False
        assert result["session_tts"]["voice"] == "bf_emma"
        assert result["session_tts"]["volume"] == 0.5

        _session_states.clear()
        _session_activity.clear()

    def test_partial_update_preserves_other_keys(self):
        from spellbook_mcp.config_tools import (
            _get_session_state,
            _session_activity,
            _session_states,
            tts_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        # Set initial values
        state = _get_session_state()
        state["tts"] = {"enabled": True, "voice": "af_heart", "volume": 0.3}

        # Only change voice
        result = tts_session_set(voice="bf_emma")

        assert result["session_tts"]["voice"] == "bf_emma"
        assert result["session_tts"]["enabled"] is True
        assert result["session_tts"]["volume"] == 0.3

        _session_states.clear()
        _session_activity.clear()

    def test_uses_session_id(self):
        from spellbook_mcp.config_tools import (
            _get_session_state,
            _session_activity,
            _session_states,
            tts_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        tts_session_set(enabled=True, session_id="session-a")
        tts_session_set(enabled=False, session_id="session-b")

        state_a = _get_session_state("session-a")
        state_b = _get_session_state("session-b")

        assert state_a["tts"]["enabled"] is True
        assert state_b["tts"]["enabled"] is False

        _session_states.clear()
        _session_activity.clear()

    def test_omitted_fields_not_added(self):
        from spellbook_mcp.config_tools import (
            _get_session_state,
            _session_activity,
            _session_states,
            tts_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        # Only set enabled, voice and volume should not appear
        result = tts_session_set(enabled=True)

        assert result["session_tts"]["enabled"] is True
        assert "voice" not in result["session_tts"]
        assert "volume" not in result["session_tts"]

        _session_states.clear()
        _session_activity.clear()


class TestTtsSessionGet:
    """tts_session_get() resolves TTS settings: session > config > defaults."""

    def test_returns_defaults_when_nothing_set(self, tmp_path, monkeypatch):
        from spellbook_mcp.config_tools import (
            _session_activity,
            _session_states,
            tts_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text("{}")
        monkeypatch.setattr(
            "spellbook_mcp.config_tools.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        result = tts_session_get()

        assert result["enabled"] is True
        assert result["voice"] == "af_heart"
        assert result["volume"] == 0.3
        assert result["source_enabled"] == "default"
        assert result["source_voice"] == "default"
        assert result["source_volume"] == "default"

        _session_states.clear()
        _session_activity.clear()

    def test_config_overrides_defaults(self, tmp_path, monkeypatch):
        import json

        from spellbook_mcp.config_tools import (
            _session_activity,
            _session_states,
            tts_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(
            json.dumps(
                {"tts_enabled": False, "tts_voice": "am_adam", "tts_volume": 0.7}
            )
        )
        monkeypatch.setattr(
            "spellbook_mcp.config_tools.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        result = tts_session_get()

        assert result["enabled"] is False
        assert result["voice"] == "am_adam"
        assert result["volume"] == 0.7
        assert result["source_enabled"] == "config"
        assert result["source_voice"] == "config"
        assert result["source_volume"] == "config"

        _session_states.clear()
        _session_activity.clear()

    def test_session_overrides_config(self, tmp_path, monkeypatch):
        import json

        from spellbook_mcp.config_tools import (
            _get_session_state,
            _session_activity,
            _session_states,
            tts_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(
            json.dumps(
                {"tts_enabled": True, "tts_voice": "am_adam", "tts_volume": 0.7}
            )
        )
        monkeypatch.setattr(
            "spellbook_mcp.config_tools.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        # Session overrides voice only
        state = _get_session_state()
        state["tts"]["voice"] = "bf_emma"

        result = tts_session_get()

        assert result["enabled"] is True  # from config
        assert result["voice"] == "bf_emma"  # from session
        assert result["volume"] == 0.7  # from config
        assert result["source_enabled"] == "config"
        assert result["source_voice"] == "session"
        assert result["source_volume"] == "config"

        _session_states.clear()
        _session_activity.clear()

    def test_partial_config_falls_through_to_defaults(self, tmp_path, monkeypatch):
        import json

        from spellbook_mcp.config_tools import (
            _session_activity,
            _session_states,
            tts_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        # Only voice is set in config
        config_path.write_text(json.dumps({"tts_voice": "am_adam"}))
        monkeypatch.setattr(
            "spellbook_mcp.config_tools.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        result = tts_session_get()

        assert result["enabled"] is True  # default
        assert result["voice"] == "am_adam"  # config
        assert result["volume"] == 0.3  # default
        assert result["source_enabled"] == "default"
        assert result["source_voice"] == "config"
        assert result["source_volume"] == "default"

        _session_states.clear()
        _session_activity.clear()

    def test_session_id_isolation(self, tmp_path, monkeypatch):
        from spellbook_mcp.config_tools import (
            _session_activity,
            _session_states,
            tts_session_get,
            tts_session_set,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text("{}")
        monkeypatch.setattr(
            "spellbook_mcp.config_tools.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        tts_session_set(voice="bf_emma", session_id="session-a")
        tts_session_set(voice="am_adam", session_id="session-b")

        result_a = tts_session_get(session_id="session-a")
        result_b = tts_session_get(session_id="session-b")

        assert result_a["voice"] == "bf_emma"
        assert result_b["voice"] == "am_adam"

        _session_states.clear()
        _session_activity.clear()
