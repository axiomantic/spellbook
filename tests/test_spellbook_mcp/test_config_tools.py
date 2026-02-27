"""Tests for spellbook config management and session initialization tools."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestConfigGet:
    """Tests for config_get function."""

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        """Test that missing config file returns None."""
        from spellbook_mcp.config_tools import config_get, get_config_path

        # Point to a non-existent config
        fake_config = tmp_path / "nonexistent" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: fake_config)

        result = config_get("any_key")
        assert result is None

    def test_returns_none_when_key_missing(self, tmp_path, monkeypatch):
        """Test that missing key returns None."""
        from spellbook_mcp.config_tools import config_get

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"other_key": "value"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = config_get("missing_key")
        assert result is None

    def test_returns_value_when_key_exists(self, tmp_path, monkeypatch):
        """Test that existing key returns its value."""
        from spellbook_mcp.config_tools import config_get

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": true, "theme": "dark"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        assert config_get("fun_mode") is True
        assert config_get("theme") == "dark"

    def test_handles_various_value_types(self, tmp_path, monkeypatch):
        """Test that various JSON types are handled correctly."""
        from spellbook_mcp.config_tools import config_get

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({
            "bool_true": True,
            "bool_false": False,
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
            "null": None
        }))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        assert config_get("bool_true") is True
        assert config_get("bool_false") is False
        assert config_get("string") == "hello"
        assert config_get("number") == 42
        assert config_get("float") == 3.14
        assert config_get("array") == [1, 2, 3]
        assert config_get("object") == {"nested": "value"}
        assert config_get("null") is None

    def test_handles_invalid_json(self, tmp_path, monkeypatch):
        """Test that invalid JSON file returns None gracefully."""
        from spellbook_mcp.config_tools import config_get

        config_path = tmp_path / "spellbook.json"
        config_path.write_text("not valid json {{{")
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = config_get("any_key")
        assert result is None


class TestConfigSet:
    """Tests for config_set function."""

    def test_creates_file_when_missing(self, tmp_path, monkeypatch):
        """Test that config file is created if it doesn't exist."""
        from spellbook_mcp.config_tools import config_set

        config_path = tmp_path / "config" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = config_set("fun_mode", True)

        assert result["status"] == "ok"
        assert result["config"]["fun_mode"] is True
        assert config_path.exists()
        assert json.loads(config_path.read_text())["fun_mode"] is True

    def test_preserves_existing_values(self, tmp_path, monkeypatch):
        """Test that other config values are preserved."""
        from spellbook_mcp.config_tools import config_set

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"existing": "value", "other": 123}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = config_set("new_key", "new_value")

        assert result["status"] == "ok"
        assert result["config"]["existing"] == "value"
        assert result["config"]["other"] == 123
        assert result["config"]["new_key"] == "new_value"

    def test_overwrites_existing_key(self, tmp_path, monkeypatch):
        """Test that existing key is overwritten."""
        from spellbook_mcp.config_tools import config_set

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": false}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = config_set("fun_mode", True)

        assert result["config"]["fun_mode"] is True
        saved = json.loads(config_path.read_text())
        assert saved["fun_mode"] is True

    def test_handles_complex_values(self, tmp_path, monkeypatch):
        """Test that complex JSON values can be stored."""
        from spellbook_mcp.config_tools import config_set

        config_path = tmp_path / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        complex_value = {
            "nested": {"deep": {"value": 42}},
            "array": [1, "two", {"three": 3}]
        }
        result = config_set("complex", complex_value)

        assert result["config"]["complex"] == complex_value
        saved = json.loads(config_path.read_text())
        assert saved["complex"] == complex_value

    def test_handles_corrupt_existing_file(self, tmp_path, monkeypatch):
        """Test that corrupt config file is replaced."""
        from spellbook_mcp.config_tools import config_set

        config_path = tmp_path / "spellbook.json"
        config_path.write_text("corrupt json {{{")
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = config_set("key", "value")

        assert result["status"] == "ok"
        assert result["config"] == {"key": "value"}


class TestSessionInit:
    """Tests for session_init function."""

    def test_returns_unset_when_no_config(self, tmp_path, monkeypatch):
        """Test that missing config returns mode.type=unset."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "nonexistent" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result["mode"]["type"] == "unset"
        assert result["fun_mode"] == "unset"  # Legacy key

    def test_returns_unset_when_no_mode_keys_set(self, tmp_path, monkeypatch):
        """Test that config without session_mode or fun_mode returns unset."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"other_key": "value"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result["mode"]["type"] == "unset"
        assert result["fun_mode"] == "unset"  # Legacy key

    def test_returns_none_when_session_mode_none(self, tmp_path, monkeypatch):
        """Test that session_mode='none' returns mode.type=none."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "none"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result["mode"]["type"] == "none"
        assert result["fun_mode"] == "no"  # Legacy key

    def test_returns_tarot_mode(self, tmp_path, monkeypatch):
        """Test that session_mode='tarot' returns tarot mode."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "tarot"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result["mode"]["type"] == "tarot"
        assert result["fun_mode"] == "no"  # Legacy key - tarot is not fun mode

    def test_session_mode_takes_precedence_over_legacy(self, tmp_path, monkeypatch):
        """Test that session_mode takes precedence over legacy fun_mode."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        # Both set, session_mode should win
        config_path.write_text('{"session_mode": "tarot", "fun_mode": true}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result["mode"]["type"] == "tarot"

    def test_legacy_fun_mode_false_returns_none(self, tmp_path, monkeypatch):
        """Test that legacy fun_mode=false returns mode.type=none."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": false}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result["mode"]["type"] == "none"
        assert result["fun_mode"] == "no"  # Legacy key

    def test_returns_fun_mode_with_selections(self, tmp_path, monkeypatch):
        """Test that session_mode='fun' returns fun mode with persona/context/undertow."""
        from spellbook_mcp.config_tools import session_init

        # Set up config
        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Set up fun-mode assets
        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("Test Persona 1\nTest Persona 2\n")
        (fun_assets / "contexts.txt").write_text("Test Context 1\nTest Context 2\n")
        (fun_assets / "undertows.txt").write_text("Test Undertow 1\nTest Undertow 2\n")
        monkeypatch.setenv("SPELLBOOK_DIR", str(spellbook_dir))

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert result["mode"]["persona"] in ["Test Persona 1", "Test Persona 2"]
        assert result["mode"]["context"] in ["Test Context 1", "Test Context 2"]
        assert result["mode"]["undertow"] in ["Test Undertow 1", "Test Undertow 2"]
        # Legacy keys
        assert result["fun_mode"] == "yes"
        assert result["persona"] in ["Test Persona 1", "Test Persona 2"]

    def test_legacy_fun_mode_true_works(self, tmp_path, monkeypatch):
        """Test that legacy fun_mode=true still works when session_mode not set."""
        from spellbook_mcp.config_tools import session_init

        # Set up config with legacy key only
        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": true}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Set up fun-mode assets
        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("Test Persona\n")
        (fun_assets / "contexts.txt").write_text("Test Context\n")
        (fun_assets / "undertows.txt").write_text("Test Undertow\n")
        monkeypatch.setenv("SPELLBOOK_DIR", str(spellbook_dir))

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert result["fun_mode"] == "yes"

    def test_handles_missing_assets_dir(self, tmp_path, monkeypatch):
        """Test error when fun-mode assets directory doesn't exist."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Point to a directory that exists but doesn't have fun-mode assets
        fake_spellbook = tmp_path / "fake_spellbook"
        fake_spellbook.mkdir()
        monkeypatch.setattr("spellbook_mcp.config_tools.get_spellbook_dir", lambda: fake_spellbook)

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert "error" in result["mode"]
        assert "fun-mode assets not found" in result["mode"]["error"]
        # Legacy keys
        assert result["fun_mode"] == "yes"
        assert "error" in result

    def test_handles_empty_asset_files(self, tmp_path, monkeypatch):
        """Test handling of empty persona/context/undertow files."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("")
        (fun_assets / "contexts.txt").write_text("")
        (fun_assets / "undertows.txt").write_text("")
        monkeypatch.setenv("SPELLBOOK_DIR", str(spellbook_dir))

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert result["mode"]["persona"] == ""
        assert result["fun_mode"] == "yes"
        assert result["persona"] == ""

    def test_handles_missing_asset_files(self, tmp_path, monkeypatch):
        """Test handling of missing persona/context/undertow files."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        # Don't create any .txt files
        monkeypatch.setenv("SPELLBOOK_DIR", str(spellbook_dir))

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert result["mode"]["persona"] == ""
        assert result["fun_mode"] == "yes"
        assert result["persona"] == ""


class TestSessionModeSet:
    """Tests for session_mode_set function."""

    def test_session_only_mode_set(self, tmp_path, monkeypatch):
        """Test setting session-only mode (not permanent)."""
        from spellbook_mcp.config_tools import (
            session_mode_set, _get_session_state, _session_states, DEFAULT_SESSION_ID
        )

        # Reset session state
        _session_states.clear()

        result = session_mode_set("tarot", permanent=False)

        assert result["status"] == "ok"
        assert result["mode"] == "tarot"
        assert result["permanent"] is False
        assert _get_session_state(DEFAULT_SESSION_ID)["mode"] == "tarot"

        # Clean up
        _session_states.clear()

    def test_permanent_mode_set(self, tmp_path, monkeypatch):
        """Test setting permanent mode (saved to config)."""
        from spellbook_mcp.config_tools import (
            session_mode_set, _get_session_state, _session_states, DEFAULT_SESSION_ID, config_get
        )

        config_path = tmp_path / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset session state
        _session_states.clear()

        result = session_mode_set("fun", permanent=True)

        assert result["status"] == "ok"
        assert result["mode"] == "fun"
        assert result["permanent"] is True
        # Session state should be cleared so config takes effect
        assert _get_session_state(DEFAULT_SESSION_ID)["mode"] is None
        # Config should be updated
        assert config_get("session_mode") == "fun"

        # Clean up
        _session_states.clear()

    def test_invalid_mode_rejected(self):
        """Test that invalid modes are rejected."""
        from spellbook_mcp.config_tools import session_mode_set

        result = session_mode_set("invalid_mode", permanent=False)

        assert result["status"] == "error"
        assert "Invalid mode" in result["message"]


class TestSessionModeGet:
    """Tests for session_mode_get function."""

    def test_returns_session_override(self, tmp_path, monkeypatch):
        """Test that session override is returned when set."""
        from spellbook_mcp.config_tools import (
            session_mode_get, _get_session_state, _session_states, DEFAULT_SESSION_ID
        )

        # Reset and set session state
        _session_states.clear()
        _get_session_state(DEFAULT_SESSION_ID)["mode"] = "tarot"

        result = session_mode_get()

        assert result["mode"] == "tarot"
        assert result["source"] == "session"
        assert result["permanent"] is False

        # Clean up
        _session_states.clear()

    def test_returns_config_when_no_session(self, tmp_path, monkeypatch):
        """Test that config is returned when no session override."""
        from spellbook_mcp.config_tools import session_mode_get, _session_states

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset session state (no override)
        _session_states.clear()

        result = session_mode_get()

        assert result["mode"] == "fun"
        assert result["source"] == "config"
        assert result["permanent"] is True

        # Clean up
        _session_states.clear()

    def test_returns_unset_when_nothing_configured(self, tmp_path, monkeypatch):
        """Test that unset is returned when nothing configured."""
        from spellbook_mcp.config_tools import session_mode_get, _session_states

        config_path = tmp_path / "nonexistent" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset session state (no override)
        _session_states.clear()

        result = session_mode_get()

        assert result["mode"] is None
        assert result["source"] == "unset"

        # Clean up
        _session_states.clear()


class TestSessionInitWithSessionState:
    """Tests for session_init with session state override."""

    def test_session_state_takes_priority(self, tmp_path, monkeypatch):
        """Test that session state overrides config."""
        from spellbook_mcp.config_tools import (
            session_init, _get_session_state, _session_states, DEFAULT_SESSION_ID
        )

        # Config says fun, but session says tarot
        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset and set session state
        _session_states.clear()
        _get_session_state(DEFAULT_SESSION_ID)["mode"] = "tarot"

        result = session_init()

        assert result["mode"]["type"] == "tarot"

        # Clean up
        _session_states.clear()


class TestRandomLine:
    """Tests for random_line helper function."""

    def test_selects_from_non_empty_lines(self, tmp_path):
        """Test that only non-empty lines are selected."""
        from spellbook_mcp.config_tools import random_line

        file_path = tmp_path / "lines.txt"
        file_path.write_text("Line 1\n\nLine 2\n   \nLine 3\n")

        # Run multiple times to ensure empty lines are never selected
        for _ in range(20):
            result = random_line(file_path)
            assert result in ["Line 1", "Line 2", "Line 3"]

    def test_returns_empty_for_empty_file(self, tmp_path):
        """Test that empty file returns empty string."""
        from spellbook_mcp.config_tools import random_line

        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        result = random_line(file_path)
        assert result == ""

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Test that missing file returns empty string."""
        from spellbook_mcp.config_tools import random_line

        file_path = tmp_path / "nonexistent.txt"

        result = random_line(file_path)
        assert result == ""

    def test_strips_whitespace(self, tmp_path):
        """Test that leading/trailing whitespace is stripped."""
        from spellbook_mcp.config_tools import random_line

        file_path = tmp_path / "whitespace.txt"
        file_path.write_text("  Line with spaces  \n")

        result = random_line(file_path)
        assert result == "Line with spaces"


class TestGetSpellbookDir:
    """Tests for get_spellbook_dir function."""

    def test_returns_env_var_when_set(self, tmp_path, monkeypatch):
        """Test that SPELLBOOK_DIR env var is respected."""
        from spellbook_mcp.config_tools import get_spellbook_dir

        expected = str(tmp_path / "my-spellbook")
        monkeypatch.setenv("SPELLBOOK_DIR", expected)

        result = get_spellbook_dir()
        assert result == Path(expected)

    def test_falls_back_when_env_var_not_set(self, monkeypatch):
        """Test fallback when SPELLBOOK_DIR not set - finds via __file__ or defaults."""
        from spellbook_mcp.config_tools import get_spellbook_dir

        monkeypatch.delenv("SPELLBOOK_DIR", raising=False)

        # Should not raise - falls back to finding via __file__ or default
        result = get_spellbook_dir()
        assert isinstance(result, Path)
        # Should find the actual spellbook dir (running from repo or worktree) or default
        # Worktrees live under .claude/worktrees/ or .worktrees/
        assert result.name == "spellbook" or "/worktrees/" in str(result)


class TestSessionIsolation:
    """Tests for multi-session isolation in HTTP daemon mode."""

    def test_different_sessions_have_isolated_state(self, tmp_path, monkeypatch):
        """Test that different session IDs have isolated mode state."""
        from spellbook_mcp.config_tools import (
            session_mode_set, session_mode_get, _session_states
        )

        # Reset global state
        _session_states.clear()

        # Session A sets mode to fun
        session_mode_set("fun", permanent=False, session_id="session-a")

        # Session B sets mode to tarot
        session_mode_set("tarot", permanent=False, session_id="session-b")

        # Verify each session sees its own mode
        result_a = session_mode_get(session_id="session-a")
        result_b = session_mode_get(session_id="session-b")

        assert result_a["mode"] == "fun"
        assert result_a["source"] == "session"
        assert result_b["mode"] == "tarot"
        assert result_b["source"] == "session"

        # Clean up
        _session_states.clear()

    def test_session_init_respects_session_id(self, tmp_path, monkeypatch):
        """Test that session_init uses session-specific state."""
        from spellbook_mcp.config_tools import (
            session_init, session_mode_set, _session_states
        )

        # No config file
        config_path = tmp_path / "nonexistent" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset global state
        _session_states.clear()

        # Session A sets mode to tarot
        session_mode_set("tarot", permanent=False, session_id="session-a")

        # Session B has no mode set

        # Verify session_init returns session-specific state
        result_a = session_init(session_id="session-a")
        result_b = session_init(session_id="session-b")

        assert result_a["mode"]["type"] == "tarot"
        assert result_b["mode"]["type"] == "unset"

        # Clean up
        _session_states.clear()

    def test_permanent_mode_affects_all_sessions(self, tmp_path, monkeypatch):
        """Test that permanent mode (config) is shared across sessions.

        Also verifies that session A's local override is cleared when
        setting permanent mode (production line 208: session_state["mode"] = None).
        """
        from spellbook_mcp.config_tools import (
            session_mode_set, session_mode_get, _session_states
        )

        config_path = tmp_path / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset global state
        _session_states.clear()

        # Session A sets permanent mode
        session_mode_set("fun", permanent=True, session_id="session-a")

        # Session B (without session override) should see config
        result_b = session_mode_get(session_id="session-b")

        assert result_b["mode"] == "fun"
        assert result_b["source"] == "config"
        assert result_b["permanent"] is True

        # Verify session A also sees config (local override was cleared)
        result_a = session_mode_get(session_id="session-a")
        assert result_a["mode"] == "fun"
        assert result_a["source"] == "config", "Session A's local override should be cleared"
        assert result_a["permanent"] is True

        # Clean up
        _session_states.clear()

    def test_session_override_takes_precedence_over_config(self, tmp_path, monkeypatch):
        """Test that session-only mode overrides config-based mode."""
        from spellbook_mcp.config_tools import (
            session_mode_set, session_mode_get, _session_states
        )

        # Set up config with fun mode
        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"session_mode": "fun"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset global state
        _session_states.clear()

        # Session A overrides with tarot
        session_mode_set("tarot", permanent=False, session_id="session-a")

        # Session A sees its override, Session B sees config
        result_a = session_mode_get(session_id="session-a")
        result_b = session_mode_get(session_id="session-b")

        assert result_a["mode"] == "tarot"
        assert result_a["source"] == "session"
        assert result_b["mode"] == "fun"
        assert result_b["source"] == "config"

        # Clean up
        _session_states.clear()

    def test_default_session_id_for_backward_compatibility(self, tmp_path, monkeypatch):
        """Test that None session_id uses default for backward compatibility."""
        from spellbook_mcp.config_tools import (
            session_mode_set, session_mode_get, _session_states, DEFAULT_SESSION_ID
        )

        # Reset global state
        _session_states.clear()

        # Set mode without session_id (should use default)
        session_mode_set("fun", permanent=False)

        # Get without session_id (should use default)
        result = session_mode_get()

        assert result["mode"] == "fun"
        assert result["source"] == "session"

        # Verify it's in the default session
        from spellbook_mcp.config_tools import _get_session_state
        assert _get_session_state(DEFAULT_SESSION_ID)["mode"] == "fun"

        # Clean up
        _session_states.clear()


class TestSessionCleanup:
    """Tests for session cleanup/garbage collection."""

    def test_stale_sessions_are_cleaned_up(self, tmp_path, monkeypatch):
        """Test that stale sessions are cleaned up during normal API access.

        This test would FAIL if _cleanup_stale_sessions() was removed from
        _get_session_state(), because the stale session would persist.
        """
        from datetime import datetime, timedelta
        from spellbook_mcp.config_tools import (
            session_mode_set, session_mode_get, _session_states,
            _session_activity, SESSION_TTL_DAYS
        )

        # Reset global state
        _session_states.clear()
        _session_activity.clear()

        # Create an old session via PUBLIC API
        session_mode_set("fun", permanent=False, session_id="old-session")

        # Artificially age the session (this is acceptable test setup)
        _session_activity["old-session"] = datetime.now() - timedelta(days=SESSION_TTL_DAYS + 1)

        # Create a recent session via PUBLIC API
        session_mode_set("tarot", permanent=False, session_id="recent-session")

        # Access via PUBLIC API - this should trigger cleanup as side effect
        session_mode_get(session_id="any-session")

        # Old session should be gone (cleaned up as side effect of access)
        assert "old-session" not in _session_states, "Stale session should be cleaned on access"
        assert "old-session" not in _session_activity, "Stale session activity should be cleaned"

        # Recent session should remain
        assert "recent-session" in _session_states, "Recent session should be preserved"
        assert "recent-session" in _session_activity, "Recent session activity should be preserved"

        # Clean up
        _session_states.clear()
        _session_activity.clear()

    def test_activity_timestamp_updated_on_access(self, tmp_path, monkeypatch):
        """Test that accessing session state via public API updates activity timestamp.

        Uses session_mode_get (public API) instead of _get_session_state (internal).
        """
        from datetime import datetime
        from spellbook_mcp.config_tools import (
            session_mode_get, _session_states, _session_activity
        )

        # Reset global state
        _session_states.clear()
        _session_activity.clear()

        session_id = "test-session"

        # Access via PUBLIC API
        before = datetime.now()
        session_mode_get(session_id=session_id)
        after = datetime.now()

        # Verify timestamp was updated
        assert session_id in _session_activity
        assert before <= _session_activity[session_id] <= after

        # Clean up
        _session_states.clear()
        _session_activity.clear()

    def test_new_session_gets_default_state(self, tmp_path, monkeypatch):
        """Test that new sessions have no mode set by default.

        Uses session_mode_get (public API) instead of _get_session_state (internal).
        Verifies public API returns expected default state.
        """
        from spellbook_mcp.config_tools import (
            session_mode_get, _session_states, _session_activity
        )

        config_path = tmp_path / "nonexistent" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        # Reset global state
        _session_states.clear()
        _session_activity.clear()

        session_id = "brand-new-session"

        # Use PUBLIC API
        result = session_mode_get(session_id=session_id)

        # Verify public API returns expected default
        assert result["mode"] is None
        assert result["source"] == "unset"

        # Session should now be tracked
        assert session_id in _session_states
        assert session_id in _session_activity

        # Clean up
        _session_states.clear()
        _session_activity.clear()

    def test_cleanup_integrated_with_session_access(self, tmp_path, monkeypatch):
        """Mutation-catching test: cleanup must be integrated with session access.

        This test would FAIL if _cleanup_stale_sessions() was removed from
        _get_session_state(). It verifies that cleanup happens as a side effect
        of accessing ANY session, not just the stale one.

        Key insight: Create a stale session, then access a DIFFERENT session.
        The stale session should be cleaned up as a side effect. This proves
        cleanup is integrated into the access path, not just working in isolation.
        """
        from datetime import datetime, timedelta
        from spellbook_mcp.config_tools import (
            session_mode_set, session_mode_get, _session_states,
            _session_activity, SESSION_TTL_DAYS
        )

        # Reset global state
        _session_states.clear()
        _session_activity.clear()

        # Create a stale session via public API
        session_mode_set("fun", permanent=False, session_id="stale-session")
        _session_activity["stale-session"] = datetime.now() - timedelta(days=SESSION_TTL_DAYS + 1)

        # Verify the stale session exists before access
        assert "stale-session" in _session_states, "Precondition: stale session should exist"

        # Access a DIFFERENT session - this should trigger cleanup as side effect
        session_mode_get(session_id="different-session")

        # The stale session should be gone - this is the mutation-catching assertion
        # If _cleanup_stale_sessions() was removed from _get_session_state(), this fails
        assert "stale-session" not in _session_states, (
            "Cleanup did not run during session access. "
            "This indicates _cleanup_stale_sessions() may not be called in _get_session_state()."
        )
        assert "stale-session" not in _session_activity

        # Clean up
        _session_states.clear()
        _session_activity.clear()


class TestTelemetryConfig:
    """Tests for telemetry configuration functions."""

    def test_telemetry_enable_creates_config(self, tmp_path, monkeypatch):
        """Test that telemetry_enable creates config record."""
        from spellbook_mcp.config_tools import telemetry_enable, telemetry_status
        from spellbook_mcp.db import init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        result = telemetry_enable(db_path=db_path)

        assert result["status"] == "enabled"
        assert result["endpoint_url"] is None

        # Verify via status
        status = telemetry_status(db_path=db_path)
        assert status["enabled"] is True

    def test_telemetry_enable_with_custom_endpoint(self, tmp_path, monkeypatch):
        """Test telemetry_enable with custom endpoint URL."""
        from spellbook_mcp.config_tools import telemetry_enable, telemetry_status
        from spellbook_mcp.db import init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        result = telemetry_enable(
            endpoint_url="https://custom.endpoint.com/telemetry",
            db_path=db_path,
        )

        assert result["status"] == "enabled"
        assert result["endpoint_url"] == "https://custom.endpoint.com/telemetry"

    def test_telemetry_disable(self, tmp_path, monkeypatch):
        """Test that telemetry_disable sets enabled to False."""
        from spellbook_mcp.config_tools import (
            telemetry_enable, telemetry_disable, telemetry_status
        )
        from spellbook_mcp.db import init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Enable first
        telemetry_enable(db_path=db_path)

        # Then disable
        result = telemetry_disable(db_path=db_path)
        assert result["status"] == "disabled"

        # Verify via status
        status = telemetry_status(db_path=db_path)
        assert status["enabled"] is False

    def test_telemetry_status_when_not_configured(self, tmp_path, monkeypatch):
        """Test telemetry_status when no config exists."""
        from spellbook_mcp.config_tools import telemetry_status
        from spellbook_mcp.db import init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        status = telemetry_status(db_path=db_path)

        assert status["enabled"] is False
        assert status["endpoint_url"] is None
        assert status["last_sync"] is None

    def test_telemetry_preserves_endpoint_on_disable(self, tmp_path, monkeypatch):
        """Test that disabling telemetry preserves the endpoint URL."""
        from spellbook_mcp.config_tools import (
            telemetry_enable, telemetry_disable, telemetry_status
        )
        from spellbook_mcp.db import init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Enable with endpoint
        telemetry_enable(endpoint_url="https://example.com", db_path=db_path)

        # Disable
        telemetry_disable(db_path=db_path)

        # Endpoint should still be there
        status = telemetry_status(db_path=db_path)
        assert status["enabled"] is False
        assert status["endpoint_url"] == "https://example.com"
