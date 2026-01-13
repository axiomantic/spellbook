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
    """Tests for session_init function - legacy fun_mode backwards compatibility."""

    def test_returns_unset_when_no_config(self, tmp_path, monkeypatch):
        """Test that missing config returns mode.type=unset."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "nonexistent" / "spellbook.json"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result == {"mode": {"type": "unset"}}

    def test_returns_unset_when_fun_mode_not_set(self, tmp_path, monkeypatch):
        """Test that config without fun_mode or mode returns unset."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"other_key": "value"}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result == {"mode": {"type": "unset"}}

    def test_returns_none_when_legacy_fun_mode_false(self, tmp_path, monkeypatch):
        """Test that legacy fun_mode=false returns mode.type=none."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": false}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()
        assert result == {"mode": {"type": "none"}}

    def test_returns_fun_with_selections_when_legacy_fun_mode_true(self, tmp_path, monkeypatch):
        """Test that legacy fun_mode=true returns fun mode with persona/context/undertow."""
        from spellbook_mcp.config_tools import session_init

        # Set up config
        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": true}')
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
        assert result["persona"] in ["Test Persona 1", "Test Persona 2"]
        assert result["context"] in ["Test Context 1", "Test Context 2"]
        assert result["undertow"] in ["Test Undertow 1", "Test Undertow 2"]

    def test_handles_missing_assets_dir(self, tmp_path, monkeypatch):
        """Test error when fun-mode assets directory doesn't exist."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": true}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        fake_spellbook = tmp_path / "fake_spellbook"
        fake_spellbook.mkdir()
        monkeypatch.setattr("spellbook_mcp.config_tools.get_spellbook_dir", lambda: fake_spellbook)

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert "error" in result
        assert "fun-mode assets not found" in result["error"]

    def test_handles_empty_asset_files(self, tmp_path, monkeypatch):
        """Test handling of empty persona/context/undertow files."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": true}')
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
        assert result["persona"] == ""
        assert result["context"] == ""
        assert result["undertow"] == ""

    def test_handles_missing_asset_files(self, tmp_path, monkeypatch):
        """Test handling of missing persona/context/undertow files."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text('{"fun_mode": true}')
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        monkeypatch.setenv("SPELLBOOK_DIR", str(spellbook_dir))

        result = session_init()

        assert result["mode"]["type"] == "fun"
        assert result["persona"] == ""
        assert result["context"] == ""
        assert result["undertow"] == ""

    def test_mode_object_takes_precedence_over_legacy(self, tmp_path, monkeypatch):
        """Test that mode object is used even if fun_mode is also present."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({
            "fun_mode": True,  # Legacy key
            "mode": {"type": "none"}  # New key takes precedence
        }))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()

        assert result == {"mode": {"type": "none"}}


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


class TestSessionInitModeObject:
    """Tests for session_init with mode object config."""

    def test_returns_tarot_config_when_mode_type_tarot(self, tmp_path, monkeypatch):
        """Test that mode.type=tarot returns full tarot config."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({
            "mode": {
                "type": "tarot",
                "active_personas": ["magician", "priestess", "hermit", "fool"],
                "debate_rounds_max": 3
            }
        }))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()

        assert result["mode"]["type"] == "tarot"
        assert result["mode"]["active_personas"] == ["magician", "priestess", "hermit", "fool"]
        assert result["mode"]["debate_rounds_max"] == 3

    def test_returns_tarot_defaults_when_minimal_config(self, tmp_path, monkeypatch):
        """Test that minimal tarot config gets defaults."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({
            "mode": {"type": "tarot"}
        }))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()

        assert result["mode"]["type"] == "tarot"
        assert result["mode"]["active_personas"] == ["magician", "priestess", "hermit", "fool"]
        assert result["mode"]["debate_rounds_max"] == 3

    def test_returns_none_mode_when_mode_type_none(self, tmp_path, monkeypatch):
        """Test that mode.type=none returns simple none response."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({"mode": {"type": "none"}}))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()

        assert result == {"mode": {"type": "none"}}

    def test_returns_fun_mode_with_selections_when_mode_type_fun(self, tmp_path, monkeypatch):
        """Test that mode.type=fun returns fun mode response with persona/context/undertow."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({"mode": {"type": "fun"}}))
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
        assert result["persona"] == "Test Persona"
        assert result["context"] == "Test Context"
        assert result["undertow"] == "Test Undertow"

    def test_returns_unset_when_no_mode_and_no_fun_mode(self, tmp_path, monkeypatch):
        """Test that missing both mode and fun_mode returns unset."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({"other_key": "value"}))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()

        assert result == {"mode": {"type": "unset"}}

    def test_returns_custom_active_personas_when_configured(self, tmp_path, monkeypatch):
        """Test that custom active_personas list is respected."""
        from spellbook_mcp.config_tools import session_init

        config_path = tmp_path / "spellbook.json"
        config_path.write_text(json.dumps({
            "mode": {
                "type": "tarot",
                "active_personas": ["magician", "hermit"]  # Custom subset
            }
        }))
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)

        result = session_init()

        assert result["mode"]["active_personas"] == ["magician", "hermit"]


class TestModeValidation:
    """Tests for mode configuration validation."""

    def test_valid_mode_types(self):
        """Test that valid mode types are accepted."""
        from spellbook_mcp.config_tools import validate_mode_config

        assert validate_mode_config({"type": "tarot"}) is True
        assert validate_mode_config({"type": "fun"}) is True
        assert validate_mode_config({"type": "none"}) is True

    def test_invalid_mode_type_rejected(self):
        """Test that invalid mode types are rejected."""
        from spellbook_mcp.config_tools import validate_mode_config

        assert validate_mode_config({"type": "invalid"}) is False
        assert validate_mode_config({"type": ""}) is False
        assert validate_mode_config({}) is False

    def test_tarot_mode_requires_active_personas(self):
        """Test that tarot mode validates active_personas when present."""
        from spellbook_mcp.config_tools import validate_mode_config

        # Valid: type only (defaults apply)
        assert validate_mode_config({"type": "tarot"}) is True

        # Valid: with active_personas
        assert validate_mode_config({
            "type": "tarot",
            "active_personas": ["magician", "hermit"]
        }) is True

        # Invalid: unknown persona
        assert validate_mode_config({
            "type": "tarot",
            "active_personas": ["magician", "unknown"]
        }) is False

        # Invalid: empty active_personas
        assert validate_mode_config({
            "type": "tarot",
            "active_personas": []
        }) is False

    def test_non_dict_rejected(self):
        """Test that non-dict values are rejected."""
        from spellbook_mcp.config_tools import validate_mode_config

        assert validate_mode_config("tarot") is False
        assert validate_mode_config(True) is False
        assert validate_mode_config(None) is False


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
        # Should find the actual spellbook dir (or worktree) containing expected files
        # When running in worktree, directory name may be worktree name, not "spellbook"
        assert (result / "skills").is_dir() or result.name == "spellbook"
