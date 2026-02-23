"""Tests for spellbook-start.py session initialization script."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# All tests in this module invoke spellbook-start.py with Unix-specific
# environment patterns (HOME, minimal env) that fail on Windows.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Bash scripts not available on Windows",
)

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "spellbook-start.py"


class TestFunModeDisabled:
    """Tests for when fun_mode is explicitly disabled."""

    def test_fun_mode_false_outputs_only_no(self, tmp_path, monkeypatch):
        """When fun_mode=false, should output only 'fun_mode=no' with no persona/context/undertow."""
        # Setup config with fun_mode=false
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": False}))

        # Mock home directory
        monkeypatch.setenv("HOME", str(tmp_path))

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={**dict(monkeypatch._ENV_ITEMS if hasattr(monkeypatch, '_ENV_ITEMS') else []), "HOME": str(tmp_path)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines == ["fun_mode=no"]
        assert "persona=" not in result.stdout
        assert "context=" not in result.stdout
        assert "undertow=" not in result.stdout


class TestFunModeEnabled:
    """Tests for when fun_mode is enabled."""

    def test_fun_mode_true_outputs_all_fields(self, tmp_path, monkeypatch):
        """When fun_mode=true, should output fun_mode=yes plus persona, context, undertow."""
        # Setup config with fun_mode=true
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        # Setup fun-mode assets
        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("Test Persona 1\nTest Persona 2\n")
        (fun_assets / "contexts.txt").write_text("Test Context 1\nTest Context 2\n")
        (fun_assets / "undertows.txt").write_text("Test Undertow 1\nTest Undertow 2\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert lines[0] == "fun_mode=yes"
        assert lines[1].startswith("persona=Test Persona ")
        assert lines[2].startswith("context=Test Context ")
        assert lines[3].startswith("undertow=Test Undertow ")

    def test_fun_mode_selects_from_available_options(self, tmp_path, monkeypatch):
        """Persona/context/undertow should be selected from the text files."""
        # Setup config
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        # Setup fun-mode assets with single options
        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("The Only Persona\n")
        (fun_assets / "contexts.txt").write_text("The Only Context\n")
        (fun_assets / "undertows.txt").write_text("The Only Undertow\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert "persona=The Only Persona" in lines
        assert "context=The Only Context" in lines
        assert "undertow=The Only Undertow" in lines


class TestConfigMissing:
    """Tests for when config file is missing."""

    def test_config_missing_outputs_unset(self, tmp_path, monkeypatch):
        """When config file doesn't exist, should output 'fun_mode=unset'."""
        # Don't create config file - just use empty tmp_path as HOME
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines == ["fun_mode=unset"]
        assert "persona=" not in result.stdout
        assert "context=" not in result.stdout
        assert "undertow=" not in result.stdout


class TestConfigMalformed:
    """Tests for when config file contains invalid JSON."""

    def test_malformed_json_treated_as_missing(self, tmp_path, monkeypatch):
        """Malformed JSON should be treated as missing config (fun_mode=unset)."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text("{ this is not valid json }")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        # Malformed JSON returns empty dict, so fun_mode key is missing -> unset
        assert lines == ["fun_mode=unset"]

    def test_empty_json_file_treated_as_missing(self, tmp_path, monkeypatch):
        """Empty JSON file should be treated as missing fun_mode (unset)."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text("")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines == ["fun_mode=unset"]

    def test_valid_json_without_fun_mode_key(self, tmp_path, monkeypatch):
        """Valid JSON without fun_mode key should output unset."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"other_setting": "value"}))

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines == ["fun_mode=unset"]


class TestPersonaFilesMissing:
    """Tests for when persona/context/undertow files don't exist."""

    def test_missing_persona_files_outputs_empty_values(self, tmp_path, monkeypatch):
        """Missing text files should result in empty values for persona/context/undertow."""
        # Setup config with fun_mode=true
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        # Setup spellbook dir but don't create the text files
        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        # Don't create personas.txt, contexts.txt, undertows.txt

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert lines[0] == "fun_mode=yes"
        assert lines[1] == "persona="
        assert lines[2] == "context="
        assert lines[3] == "undertow="

    def test_partial_missing_files(self, tmp_path, monkeypatch):
        """Some files existing, some missing should handle gracefully."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        # Only create personas.txt
        (fun_assets / "personas.txt").write_text("Existing Persona\n")
        # contexts.txt and undertows.txt don't exist

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert lines[0] == "fun_mode=yes"
        assert lines[1] == "persona=Existing Persona"
        assert lines[2] == "context="
        assert lines[3] == "undertow="


class TestEmptyPersonaFiles:
    """Tests for when persona/context/undertow files exist but are empty."""

    def test_empty_files_output_empty_values(self, tmp_path, monkeypatch):
        """Empty text files should result in empty values."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("")
        (fun_assets / "contexts.txt").write_text("")
        (fun_assets / "undertows.txt").write_text("")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert lines[0] == "fun_mode=yes"
        assert lines[1] == "persona="
        assert lines[2] == "context="
        assert lines[3] == "undertow="

    def test_whitespace_only_files_treated_as_empty(self, tmp_path, monkeypatch):
        """Files with only whitespace should be treated as empty."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("   \n\n   \n")
        (fun_assets / "contexts.txt").write_text("\t\t\n")
        (fun_assets / "undertows.txt").write_text("\n\n\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 4
        assert lines[0] == "fun_mode=yes"
        assert lines[1] == "persona="
        assert lines[2] == "context="
        assert lines[3] == "undertow="


class TestSpellbookDirResolution:
    """Tests for SPELLBOOK_DIR environment variable and fallback behavior."""

    def test_spellbook_dir_env_respected(self, tmp_path, monkeypatch):
        """SPELLBOOK_DIR environment variable should be used for asset location."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        # Create assets in a custom location
        custom_spellbook = tmp_path / "custom" / "location"
        fun_assets = custom_spellbook / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("Custom Persona\n")
        (fun_assets / "contexts.txt").write_text("Custom Context\n")
        (fun_assets / "undertows.txt").write_text("Custom Undertow\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(custom_spellbook)},
        )

        assert result.returncode == 0
        assert "persona=Custom Persona" in result.stdout
        assert "context=Custom Context" in result.stdout
        assert "undertow=Custom Undertow" in result.stdout


class TestOutputFormat:
    """Tests for exact output format compliance."""

    def test_output_format_key_value_pairs(self, tmp_path, monkeypatch):
        """Output should be key=value pairs, one per line."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": True}))

        spellbook_dir = tmp_path / "spellbook"
        fun_assets = spellbook_dir / "skills" / "fun-mode"
        fun_assets.mkdir(parents=True)
        (fun_assets / "personas.txt").write_text("A persona with = equals sign\n")
        (fun_assets / "contexts.txt").write_text("Context value\n")
        (fun_assets / "undertows.txt").write_text("Undertow value\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path), "SPELLBOOK_DIR": str(spellbook_dir)},
        )

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")

        # Each line should be parseable as key=value
        for line in lines:
            assert "=" in line
            key, value = line.split("=", 1)
            assert key in ["fun_mode", "persona", "context", "undertow"]

    def test_no_trailing_newline_issues(self, tmp_path, monkeypatch):
        """Output should not have extra trailing newlines."""
        config_dir = tmp_path / ".config" / "spellbook"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "spellbook.json"
        config_file.write_text(json.dumps({"fun_mode": False}))

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            env={"HOME": str(tmp_path)},
        )

        # Should have exactly one trailing newline (from print)
        assert result.stdout == "fun_mode=no\n"
