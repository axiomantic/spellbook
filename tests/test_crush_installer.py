"""Tests for Crush platform installer."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def spellbook_dir(tmp_path):
    """Create a mock spellbook directory."""
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()

    # Create version file
    (spellbook / ".version").write_text("0.1.0")

    # Create MCP server path
    mcp_dir = spellbook / "spellbook_mcp"
    mcp_dir.mkdir()
    (mcp_dir / "server.py").write_text("# MCP server stub")

    # Create AGENTS.spellbook.md for context generation
    (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook Context\n\nTest content.")

    return spellbook


@pytest.fixture
def crush_config_dir(tmp_path):
    """Create a mock Crush config directory."""
    config_dir = tmp_path / ".config" / "crush"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def claude_skills_dir(tmp_path):
    """Create a mock Claude skills directory."""
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    return skills_dir


class TestCrushInstaller:
    """Tests for CrushInstaller class."""

    def test_platform_properties(self, spellbook_dir, crush_config_dir):
        """Test platform name and id properties."""
        from installer.platforms.crush import CrushInstaller

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")

        assert installer.platform_name == "Crush"
        assert installer.platform_id == "crush"

    def test_detect_not_installed(self, spellbook_dir, crush_config_dir):
        """Test detection when Crush is available but spellbook not installed."""
        from installer.platforms.crush import CrushInstaller

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        status = installer.detect()

        assert status.platform == "crush"
        assert status.available is True
        assert status.installed is False
        assert status.version is None

    def test_detect_not_available(self, spellbook_dir, tmp_path):
        """Test detection when Crush config directory doesn't exist."""
        from installer.platforms.crush import CrushInstaller

        nonexistent_dir = tmp_path / "nonexistent"
        installer = CrushInstaller(spellbook_dir, nonexistent_dir, "0.1.0")
        status = installer.detect()

        assert status.available is False
        assert status.installed is False

    def test_install_creates_agents_md(self, spellbook_dir, crush_config_dir, monkeypatch):
        """Test that install creates AGENTS.md."""
        from installer.platforms.crush import CrushInstaller

        # Mock home to use our tmp dirs
        monkeypatch.setattr(Path, "home", lambda: crush_config_dir.parent.parent)

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        results = installer.install()

        # Check AGENTS.md was created
        agents_md = crush_config_dir / "AGENTS.md"
        assert agents_md.exists()

        # Check results contain AGENTS.md component
        agents_result = next((r for r in results if r.component == "AGENTS.md"), None)
        assert agents_result is not None
        assert agents_result.success is True

    def test_install_creates_crush_json(self, spellbook_dir, crush_config_dir, monkeypatch):
        """Test that install creates/updates crush.json."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: crush_config_dir.parent.parent)

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        results = installer.install()

        # Check crush.json was created
        crush_json = crush_config_dir / "crush.json"
        assert crush_json.exists()

        # Check config content
        config = json.loads(crush_json.read_text())
        assert "$schema" in config
        assert config["$schema"] == "https://charm.land/crush.json"

        # Check MCP server configured
        assert "mcp" in config
        assert "spellbook" in config["mcp"]
        assert config["mcp"]["spellbook"]["type"] == "stdio"

    def test_install_configures_skills_path(self, spellbook_dir, crush_config_dir, monkeypatch, tmp_path):
        """Test that install adds Claude skills path to options.skills_paths."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        installer.install()

        crush_json = crush_config_dir / "crush.json"
        config = json.loads(crush_json.read_text())

        assert "options" in config
        assert "skills_paths" in config["options"]
        assert str(tmp_path / ".claude" / "skills") in config["options"]["skills_paths"]

    def test_install_configures_context_path(self, spellbook_dir, crush_config_dir, monkeypatch, tmp_path):
        """Test that install adds AGENTS.md to options.context_paths."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        installer.install()

        crush_json = crush_config_dir / "crush.json"
        config = json.loads(crush_json.read_text())

        assert "options" in config
        assert "context_paths" in config["options"]
        assert str(crush_config_dir / "AGENTS.md") in config["options"]["context_paths"]

    def test_install_preserves_existing_config(self, spellbook_dir, crush_config_dir, monkeypatch, tmp_path):
        """Test that install preserves existing crush.json content."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create existing config with user settings
        crush_json = crush_config_dir / "crush.json"
        existing_config = {
            "$schema": "https://charm.land/crush.json",
            "options": {
                "model": "claude-3-opus",
                "skills_paths": ["/custom/skills"],
            },
            "mcp": {
                "other-server": {"type": "stdio", "command": "other"},
            },
        }
        crush_json.write_text(json.dumps(existing_config, indent=2))

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        installer.install()

        # Check existing config preserved
        config = json.loads(crush_json.read_text())
        assert config["options"]["model"] == "claude-3-opus"
        assert "/custom/skills" in config["options"]["skills_paths"]
        assert "other-server" in config["mcp"]

        # Check spellbook added
        assert "spellbook" in config["mcp"]

    def test_install_skips_if_no_config_dir(self, spellbook_dir, tmp_path):
        """Test that install skips if Crush config directory doesn't exist."""
        from installer.platforms.crush import CrushInstaller

        nonexistent_dir = tmp_path / "nonexistent"
        installer = CrushInstaller(spellbook_dir, nonexistent_dir, "0.1.0")
        results = installer.install()

        assert len(results) == 1
        assert results[0].action == "skipped"
        assert "not found" in results[0].message

    def test_uninstall_removes_agents_md_section(self, spellbook_dir, crush_config_dir, monkeypatch, tmp_path):
        """Test that uninstall removes spellbook section from AGENTS.md."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # First install
        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        installer.install()

        # Then uninstall
        results = installer.uninstall()

        # Check AGENTS.md section removed
        agents_result = next((r for r in results if r.component == "AGENTS.md"), None)
        assert agents_result is not None
        assert agents_result.success is True

    def test_uninstall_removes_mcp_config(self, spellbook_dir, crush_config_dir, monkeypatch, tmp_path):
        """Test that uninstall removes spellbook MCP server from crush.json."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # First install
        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        installer.install()

        # Then uninstall
        installer.uninstall()

        # Check crush.json updated
        crush_json = crush_config_dir / "crush.json"
        config = json.loads(crush_json.read_text())

        assert "spellbook" not in config.get("mcp", {})

    def test_uninstall_removes_paths_from_config(self, spellbook_dir, crush_config_dir, monkeypatch, tmp_path):
        """Test that uninstall removes skills and context paths from crush.json."""
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # First install
        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        installer.install()

        # Then uninstall
        installer.uninstall()

        # Check paths removed
        crush_json = crush_config_dir / "crush.json"
        config = json.loads(crush_json.read_text())

        skills_paths = config.get("options", {}).get("skills_paths", [])
        context_paths = config.get("options", {}).get("context_paths", [])

        assert str(tmp_path / ".claude" / "skills") not in skills_paths
        assert str(crush_config_dir / "AGENTS.md") not in context_paths

    def test_dry_run_makes_no_changes(self, spellbook_dir, crush_config_dir):
        """Test that dry_run=True makes no changes."""
        from installer.platforms.crush import CrushInstaller

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0", dry_run=True)
        results = installer.install()

        # Check no files created
        assert not (crush_config_dir / "AGENTS.md").exists()
        assert not (crush_config_dir / "crush.json").exists()

        # Check results show what would happen
        assert len(results) > 0
        assert all(r.success for r in results)

    def test_get_context_files(self, spellbook_dir, crush_config_dir):
        """Test get_context_files returns AGENTS.md."""
        from installer.platforms.crush import CrushInstaller

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        files = installer.get_context_files()

        assert len(files) == 1
        assert files[0] == crush_config_dir / "AGENTS.md"

    def test_get_symlinks_returns_empty(self, spellbook_dir, crush_config_dir):
        """Test get_symlinks returns empty list (Crush doesn't use symlinks)."""
        from installer.platforms.crush import CrushInstaller

        installer = CrushInstaller(spellbook_dir, crush_config_dir, "0.1.0")
        symlinks = installer.get_symlinks()

        assert symlinks == []


class TestCrushConfig:
    """Tests for Crush config helper functions."""

    def test_update_crush_config_creates_new(self, tmp_path):
        """Test _update_crush_config creates new config file."""
        from installer.platforms.crush import _update_crush_config

        config_path = tmp_path / "crush.json"
        server_path = tmp_path / "server.py"
        context_path = tmp_path / "AGENTS.md"
        skills_path = tmp_path / ".claude" / "skills"

        success, msg = _update_crush_config(config_path, server_path, context_path, skills_path)

        assert success is True
        assert config_path.exists()

        config = json.loads(config_path.read_text())
        assert config["mcp"]["spellbook"]["type"] == "stdio"

    def test_update_crush_config_updates_existing(self, tmp_path):
        """Test _update_crush_config updates existing config."""
        from installer.platforms.crush import _update_crush_config

        config_path = tmp_path / "crush.json"
        config_path.write_text(json.dumps({"existing": True}))

        server_path = tmp_path / "server.py"
        context_path = tmp_path / "AGENTS.md"
        skills_path = tmp_path / ".claude" / "skills"

        _update_crush_config(config_path, server_path, context_path, skills_path)

        config = json.loads(config_path.read_text())
        assert config["existing"] is True  # Preserved
        assert "spellbook" in config["mcp"]  # Added

    def test_remove_crush_config(self, tmp_path):
        """Test _remove_crush_config removes spellbook entries."""
        from installer.platforms.crush import _update_crush_config, _remove_crush_config

        config_path = tmp_path / "crush.json"
        server_path = tmp_path / "server.py"
        context_path = tmp_path / "AGENTS.md"
        skills_path = tmp_path / ".claude" / "skills"

        # First add
        _update_crush_config(config_path, server_path, context_path, skills_path)

        # Then remove
        success, msg = _remove_crush_config(config_path, context_path, skills_path)

        assert success is True

        config = json.loads(config_path.read_text())
        assert "spellbook" not in config.get("mcp", {})


class TestCrushInConfig:
    """Tests for Crush in installer/config.py."""

    def test_crush_in_supported_platforms(self):
        """Test Crush is in SUPPORTED_PLATFORMS."""
        from installer.config import SUPPORTED_PLATFORMS

        assert "crush" in SUPPORTED_PLATFORMS

    def test_crush_platform_config(self):
        """Test Crush platform configuration."""
        from installer.config import PLATFORM_CONFIG

        assert "crush" in PLATFORM_CONFIG

        crush_config = PLATFORM_CONFIG["crush"]
        assert crush_config["name"] == "Crush"
        assert crush_config["context_file"] == "AGENTS.md"
        assert crush_config["mcp_supported"] is True

    def test_get_platform_config_dir(self, tmp_path, monkeypatch):
        """Test get_platform_config_dir for Crush."""
        from installer.config import get_platform_config_dir

        # Clear any existing env var first
        monkeypatch.delenv("CRUSH_GLOBAL_CONFIG", raising=False)

        # Without env var, should return default (contains .config/crush)
        config_dir = get_platform_config_dir("crush")
        assert config_dir.name == "crush"
        assert config_dir.parent.name == ".config"

        # With env var, should return that
        monkeypatch.setenv("CRUSH_GLOBAL_CONFIG", str(tmp_path / "custom"))
        config_dir = get_platform_config_dir("crush")
        assert config_dir == tmp_path / "custom"


class TestCrushInCore:
    """Tests for Crush in installer/core.py."""

    def test_get_platform_installer_crush(self, spellbook_dir, tmp_path, monkeypatch):
        """Test get_platform_installer returns CrushInstaller."""
        from installer.core import get_platform_installer
        from installer.platforms.crush import CrushInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        installer = get_platform_installer("crush", spellbook_dir, "0.1.0")

        assert isinstance(installer, CrushInstaller)
