"""Tests for notification session state and config in config_tools.py.

Tests the notify sub-dict in session state, notify_session_set, and
notify_session_get functions. These are the settings layer only -- no
platform availability checks.
"""

from datetime import datetime
from unittest.mock import patch


class TestSessionStateNotifyKey:
    """_get_session_state() includes 'notify' key for notification overrides."""

    def test_new_session_has_notify_key(self):
        from spellbook.core.config import (
            _get_session_state,
            _session_activity,
            _session_states,
        )

        _session_states.clear()
        _session_activity.clear()
        state = _get_session_state("test-notify-session")
        assert "notify" in state
        assert state["notify"] == {}
        _session_states.clear()
        _session_activity.clear()

    def test_existing_session_gets_notify_key_backfilled(self):
        from spellbook.core.config import (
            _get_session_state,
            _session_activity,
            _session_states,
        )

        _session_states.clear()
        _session_activity.clear()
        # Simulate an existing session without notify key
        _session_states["legacy-session"] = {"mode": None, "tts": {}}
        _session_activity["legacy-session"] = datetime.now()
        state = _get_session_state("legacy-session")
        assert "notify" in state
        assert state["notify"] == {}
        _session_states.clear()
        _session_activity.clear()


class TestNotifySessionSet:
    """notify_session_set() updates notification overrides in session state."""

    def test_sets_all_fields(self):
        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        result = notify_session_set(enabled=False, title="My App")

        assert result["status"] == "ok"
        assert result["session_notify"]["enabled"] is False
        assert result["session_notify"]["title"] == "My App"

        _session_states.clear()
        _session_activity.clear()

    def test_partial_update_preserves_other_keys(self):
        from spellbook.core.config import (
            _get_session_state,
            _session_activity,
            _session_states,
            notify_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        # Set initial values
        state = _get_session_state()
        state["notify"] = {"enabled": True, "title": "Original"}

        # Only change title
        result = notify_session_set(title="Updated")

        assert result["session_notify"]["title"] == "Updated"
        assert result["session_notify"]["enabled"] is True

        _session_states.clear()
        _session_activity.clear()

    def test_sets_only_enabled(self):
        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        result = notify_session_set(enabled=True)

        assert result["session_notify"]["enabled"] is True
        assert "title" not in result["session_notify"]

        _session_states.clear()
        _session_activity.clear()

    def test_sets_only_title(self):
        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        result = notify_session_set(title="Custom")

        assert result["session_notify"]["title"] == "Custom"
        assert "enabled" not in result["session_notify"]

        _session_states.clear()
        _session_activity.clear()

    def test_uses_session_id(self):
        from spellbook.core.config import (
            _get_session_state,
            _session_activity,
            _session_states,
            notify_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        notify_session_set(enabled=True, session_id="session-a")
        notify_session_set(enabled=False, session_id="session-b")

        state_a = _get_session_state("session-a")
        state_b = _get_session_state("session-b")

        assert state_a["notify"]["enabled"] is True
        assert state_b["notify"]["enabled"] is False

        _session_states.clear()
        _session_activity.clear()

    def test_omitted_fields_not_added(self):
        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_set,
        )

        _session_states.clear()
        _session_activity.clear()

        # Only set enabled, title should not appear
        result = notify_session_set(enabled=True)

        assert result["session_notify"]["enabled"] is True
        assert "title" not in result["session_notify"]

        _session_states.clear()
        _session_activity.clear()


class TestNotifySessionGet:
    """notify_session_get() resolves notification settings: session > config > defaults."""

    def test_returns_defaults_when_nothing_set(self, tmp_path, monkeypatch):
        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text("{}")
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        result = notify_session_get()

        assert result["enabled"] is True
        assert result["title"] == "Spellbook"
        assert result["source_enabled"] == "default"
        assert result["source_title"] == "default"

        _session_states.clear()
        _session_activity.clear()

    def test_config_overrides_defaults(self, tmp_path, monkeypatch):
        import json

        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(
            json.dumps(
                {"notify_enabled": False, "notify_title": "My Project"}
            )
        )
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        result = notify_session_get()

        assert result["enabled"] is False
        assert result["title"] == "My Project"
        assert result["source_enabled"] == "config"
        assert result["source_title"] == "config"

        _session_states.clear()
        _session_activity.clear()

    def test_session_overrides_config(self, tmp_path, monkeypatch):
        import json

        from spellbook.core.config import (
            _get_session_state,
            _session_activity,
            _session_states,
            notify_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(
            json.dumps(
                {"notify_enabled": True, "notify_title": "Config Title"}
            )
        )
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        # Session overrides title only
        state = _get_session_state()
        state["notify"]["title"] = "Session Title"

        result = notify_session_get()

        assert result["enabled"] is True  # from config
        assert result["title"] == "Session Title"  # from session
        assert result["source_enabled"] == "config"
        assert result["source_title"] == "session"

        _session_states.clear()
        _session_activity.clear()

    def test_partial_config_falls_through_to_defaults(self, tmp_path, monkeypatch):
        import json

        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_get,
        )

        config_path = tmp_path / "spellbook.json"
        # Only title is set in config
        config_path.write_text(json.dumps({"notify_title": "From Config"}))
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        result = notify_session_get()

        assert result["enabled"] is True  # default
        assert result["title"] == "From Config"  # config
        assert result["source_enabled"] == "default"
        assert result["source_title"] == "config"

        _session_states.clear()
        _session_activity.clear()

    def test_session_id_isolation(self, tmp_path, monkeypatch):
        from spellbook.core.config import (
            _session_activity,
            _session_states,
            notify_session_get,
            notify_session_set,
        )

        config_path = tmp_path / "spellbook.json"
        config_path.write_text("{}")
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path", lambda: config_path
        )

        _session_states.clear()
        _session_activity.clear()

        notify_session_set(title="Title A", session_id="session-a")
        notify_session_set(title="Title B", session_id="session-b")

        result_a = notify_session_get(session_id="session-a")
        result_b = notify_session_get(session_id="session-b")

        assert result_a["title"] == "Title A"
        assert result_b["title"] == "Title B"

        _session_states.clear()
        _session_activity.clear()
