"""Tests for OpenCode platform installer.

OpenCode (anomalyco/opencode) uses HTTP transport to connect to the spellbook MCP daemon.
"""

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

    # Create spellbook-forged plugin directory
    plugin_dir = spellbook / "extensions" / "opencode" / "spellbook-forged"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "index.ts").write_text("// Plugin stub")
    (plugin_dir / "package.json").write_text('{"name": "spellbook-forged"}')

    return spellbook


@pytest.fixture
def opencode_config_dir(tmp_path):
    """Create a mock OpenCode config directory."""
    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    return config_dir


class TestOpenCodeInstaller:
    """Tests for OpenCodeInstaller class."""

    def test_platform_properties(self, spellbook_dir, opencode_config_dir):
        """Test platform name and id properties."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")

        assert installer.platform_name == "OpenCode"
        assert installer.platform_id == "opencode"

    def test_detect_not_installed(self, spellbook_dir, opencode_config_dir):
        """Test detection when OpenCode is available but spellbook not installed."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        status = installer.detect()

        assert status.platform == "opencode"
        assert status.available is True
        assert status.installed is False
        assert status.version is None
        assert status.details["mcp_registered"] is False

    def test_detect_not_available(self, spellbook_dir, tmp_path):
        """Test detection when OpenCode config directory doesn't exist."""
        from installer.platforms.opencode import OpenCodeInstaller

        nonexistent_dir = tmp_path / "nonexistent"
        installer = OpenCodeInstaller(spellbook_dir, nonexistent_dir, "0.1.0")
        status = installer.detect()

        assert status.available is False
        assert status.installed is False

    def test_detect_installed_with_mcp(self, spellbook_dir, opencode_config_dir):
        """Test detection when MCP is already configured."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Create existing config with spellbook MCP
        config_file = opencode_config_dir / "opencode.json"
        config_file.write_text(json.dumps({
            "mcp": {
                "spellbook": {
                    "type": "remote",
                    "url": "http://127.0.0.1:8765/mcp",
                    "enabled": True,
                }
            }
        }))

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        status = installer.detect()

        assert status.available is True
        assert status.installed is True
        assert status.details["mcp_registered"] is True

    def test_install_creates_agents_md(self, spellbook_dir, opencode_config_dir):
        """Test that install creates AGENTS.md."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        results = installer.install()

        # Check AGENTS.md was created
        agents_md = opencode_config_dir / "AGENTS.md"
        assert agents_md.exists()

        # Check results contain AGENTS.md component
        agents_result = next((r for r in results if r.component == "AGENTS.md"), None)
        assert agents_result is not None
        assert agents_result.success is True

    def test_install_creates_opencode_json_with_http_mcp(self, spellbook_dir, opencode_config_dir):
        """Test that install creates opencode.json with HTTP MCP config."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        results = installer.install()

        # Check opencode.json was created
        opencode_json = opencode_config_dir / "opencode.json"
        assert opencode_json.exists()

        # Check config content
        config = json.loads(opencode_json.read_text())
        assert "$schema" in config
        assert config["$schema"] == "https://opencode.ai/config.json"

        # Check MCP server configured with HTTP transport
        assert "mcp" in config
        assert "spellbook" in config["mcp"]
        assert config["mcp"]["spellbook"]["type"] == "remote"
        assert config["mcp"]["spellbook"]["url"] == "http://127.0.0.1:8765/mcp"
        assert config["mcp"]["spellbook"]["enabled"] is True

    def test_install_preserves_existing_config(self, spellbook_dir, opencode_config_dir):
        """Test that install preserves existing opencode.json content."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Create existing config with user settings
        opencode_json = opencode_config_dir / "opencode.json"
        existing_config = {
            "$schema": "https://opencode.ai/config.json",
            "options": {
                "model": "claude-sonnet-4-20250514",
            },
            "mcp": {
                "other-server": {"type": "local", "command": ["other"]},
            },
        }
        opencode_json.write_text(json.dumps(existing_config, indent=2))

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        installer.install()

        # Check existing config preserved
        config = json.loads(opencode_json.read_text())
        assert config["options"]["model"] == "claude-sonnet-4-20250514"
        assert "other-server" in config["mcp"]

        # Check spellbook added with correct HTTP config
        assert "spellbook" in config["mcp"]
        assert config["mcp"]["spellbook"]["type"] == "remote"

    def test_install_updates_existing_spellbook_config(self, spellbook_dir, opencode_config_dir):
        """Test that install updates existing spellbook MCP config to HTTP."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Create existing config with old stdio-style spellbook config
        opencode_json = opencode_config_dir / "opencode.json"
        existing_config = {
            "mcp": {
                "spellbook": {
                    "type": "local",
                    "command": ["python3", "/old/path/server.py"],
                },
            },
        }
        opencode_json.write_text(json.dumps(existing_config, indent=2))

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        installer.install()

        # Check spellbook updated to HTTP
        config = json.loads(opencode_json.read_text())
        assert config["mcp"]["spellbook"]["type"] == "remote"
        assert config["mcp"]["spellbook"]["url"] == "http://127.0.0.1:8765/mcp"
        # Old command should be gone
        assert "command" not in config["mcp"]["spellbook"]

    def test_install_skips_if_no_config_dir(self, spellbook_dir, tmp_path):
        """Test that install skips if OpenCode config directory doesn't exist."""
        from installer.platforms.opencode import OpenCodeInstaller

        nonexistent_dir = tmp_path / "nonexistent"
        installer = OpenCodeInstaller(spellbook_dir, nonexistent_dir, "0.1.0")
        results = installer.install()

        assert len(results) == 1
        assert results[0].action == "skipped"
        assert "not found" in results[0].message

    def test_uninstall_removes_agents_md_section(self, spellbook_dir, opencode_config_dir):
        """Test that uninstall removes spellbook section from AGENTS.md."""
        from installer.platforms.opencode import OpenCodeInstaller

        # First install
        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        installer.install()

        # Then uninstall
        results = installer.uninstall()

        # Check AGENTS.md section removed
        agents_result = next((r for r in results if r.component == "AGENTS.md"), None)
        assert agents_result is not None
        assert agents_result.success is True

    def test_uninstall_removes_mcp_config(self, spellbook_dir, opencode_config_dir):
        """Test that uninstall removes spellbook MCP server from opencode.json."""
        from installer.platforms.opencode import OpenCodeInstaller

        # First install
        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        installer.install()

        # Then uninstall
        installer.uninstall()

        # Check opencode.json updated
        opencode_json = opencode_config_dir / "opencode.json"
        config = json.loads(opencode_json.read_text())

        assert "spellbook" not in config.get("mcp", {})

    def test_uninstall_preserves_other_mcp_servers(self, spellbook_dir, opencode_config_dir):
        """Test that uninstall preserves other MCP servers."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Create config with multiple MCP servers
        opencode_json = opencode_config_dir / "opencode.json"
        existing_config = {
            "mcp": {
                "spellbook": {"type": "remote", "url": "http://127.0.0.1:8765/mcp"},
                "other-server": {"type": "local", "command": ["other"]},
            },
        }
        opencode_json.write_text(json.dumps(existing_config, indent=2))

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        installer.uninstall()

        # Check other server preserved
        config = json.loads(opencode_json.read_text())
        assert "other-server" in config["mcp"]
        assert "spellbook" not in config["mcp"]

    def test_dry_run_makes_no_changes(self, spellbook_dir, opencode_config_dir):
        """Test that dry_run=True makes no changes."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0", dry_run=True)
        results = installer.install()

        # Check no files created
        assert not (opencode_config_dir / "AGENTS.md").exists()
        assert not (opencode_config_dir / "opencode.json").exists()

        # Check results show what would happen
        assert len(results) > 0
        assert all(r.success for r in results)

    def test_get_context_files(self, spellbook_dir, opencode_config_dir):
        """Test get_context_files returns AGENTS.md."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        files = installer.get_context_files()

        assert len(files) == 1
        assert files[0] == opencode_config_dir / "AGENTS.md"

    def test_get_symlinks_returns_empty_before_install(self, spellbook_dir, opencode_config_dir):
        """Test get_symlinks returns empty list before installation."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        symlinks = installer.get_symlinks()

        assert symlinks == []


class TestOpenCodeConfig:
    """Tests for OpenCode config helper functions."""

    def test_update_opencode_config_creates_new(self, tmp_path):
        """Test _update_opencode_config creates new config file."""
        from installer.platforms.opencode import _update_opencode_config

        config_path = tmp_path / "opencode.json"

        success, msg = _update_opencode_config(config_path)

        assert success is True
        assert config_path.exists()
        assert "registered" in msg
        assert "HTTP" in msg

        config = json.loads(config_path.read_text())
        assert config["mcp"]["spellbook"]["type"] == "remote"
        assert config["mcp"]["spellbook"]["url"] == "http://127.0.0.1:8765/mcp"

    def test_update_opencode_config_updates_existing(self, tmp_path):
        """Test _update_opencode_config updates existing config."""
        from installer.platforms.opencode import _update_opencode_config

        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps({"existing": True}))

        _update_opencode_config(config_path)

        config = json.loads(config_path.read_text())
        assert config["existing"] is True  # Preserved
        assert "spellbook" in config["mcp"]  # Added
        assert config["mcp"]["spellbook"]["type"] == "remote"

    def test_update_opencode_config_dry_run(self, tmp_path):
        """Test _update_opencode_config with dry_run=True."""
        from installer.platforms.opencode import _update_opencode_config

        config_path = tmp_path / "opencode.json"

        success, msg = _update_opencode_config(config_path, dry_run=True)

        assert success is True
        assert "would register" in msg
        assert not config_path.exists()

    def test_remove_opencode_mcp_config(self, tmp_path):
        """Test _remove_opencode_mcp_config removes spellbook entry."""
        from installer.platforms.opencode import _update_opencode_config, _remove_opencode_mcp_config

        config_path = tmp_path / "opencode.json"

        # First add
        _update_opencode_config(config_path)

        # Then remove
        success, msg = _remove_opencode_mcp_config(config_path)

        assert success is True
        assert "removed" in msg

        config = json.loads(config_path.read_text())
        assert "spellbook" not in config.get("mcp", {})

    def test_remove_opencode_mcp_config_not_found(self, tmp_path):
        """Test _remove_opencode_mcp_config when config doesn't exist."""
        from installer.platforms.opencode import _remove_opencode_mcp_config

        config_path = tmp_path / "nonexistent.json"

        success, msg = _remove_opencode_mcp_config(config_path)

        assert success is True
        assert "not found" in msg

    def test_remove_opencode_mcp_config_not_configured(self, tmp_path):
        """Test _remove_opencode_mcp_config when spellbook not in config."""
        from installer.platforms.opencode import _remove_opencode_mcp_config

        config_path = tmp_path / "opencode.json"
        config_path.write_text(json.dumps({"mcp": {}}))

        success, msg = _remove_opencode_mcp_config(config_path)

        assert success is True
        assert "was not configured" in msg


class TestOpenCodePlugin:
    """Tests for OpenCode plugin installation."""

    def test_install_creates_plugin_symlink(self, spellbook_dir, opencode_config_dir):
        """Test that install creates spellbook-forged plugin symlink."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        results = installer.install()

        # Check plugins directory was created
        plugins_dir = opencode_config_dir / "plugins"
        assert plugins_dir.exists()

        # Check plugin symlink was created
        plugin_symlink = plugins_dir / "spellbook-forged"
        assert plugin_symlink.is_symlink()
        assert plugin_symlink.resolve() == (spellbook_dir / "extensions" / "opencode" / "spellbook-forged").resolve()

        # Check results contain plugin component
        plugin_result = next((r for r in results if r.component == "plugin"), None)
        assert plugin_result is not None
        assert plugin_result.success is True
        assert "spellbook-forged" in plugin_result.message

    def test_install_updates_existing_plugin_symlink(self, spellbook_dir, opencode_config_dir):
        """Test that install updates existing plugin symlink."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Create existing symlink pointing elsewhere
        plugins_dir = opencode_config_dir / "plugins"
        plugins_dir.mkdir(parents=True)
        plugin_symlink = plugins_dir / "spellbook-forged"
        plugin_symlink.symlink_to("/tmp/old-plugin")

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        results = installer.install()

        # Check symlink was updated
        assert plugin_symlink.is_symlink()
        assert plugin_symlink.resolve() == (spellbook_dir / "extensions" / "opencode" / "spellbook-forged").resolve()

        # Check results show update
        plugin_result = next((r for r in results if r.component == "plugin"), None)
        assert plugin_result is not None
        assert plugin_result.action == "updated"

    def test_detect_shows_plugin_status(self, spellbook_dir, opencode_config_dir):
        """Test that detect shows plugin installation status."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")

        # Before install
        status = installer.detect()
        assert status.details["plugin_installed"] is False

        # After install
        installer.install()
        status = installer.detect()
        assert status.details["plugin_installed"] is True

    def test_uninstall_removes_plugin_symlink(self, spellbook_dir, opencode_config_dir):
        """Test that uninstall removes plugin symlink."""
        from installer.platforms.opencode import OpenCodeInstaller

        # First install
        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")
        installer.install()

        # Verify plugin exists
        plugin_symlink = opencode_config_dir / "plugins" / "spellbook-forged"
        assert plugin_symlink.is_symlink()

        # Uninstall
        results = installer.uninstall()

        # Check plugin was removed
        assert not plugin_symlink.exists()

        # Check results contain plugin component
        plugin_result = next((r for r in results if r.component == "plugin"), None)
        assert plugin_result is not None
        assert plugin_result.action == "removed"

    def test_get_symlinks_includes_plugin(self, spellbook_dir, opencode_config_dir):
        """Test that get_symlinks returns plugin symlink."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0")

        # Before install - no symlinks
        symlinks = installer.get_symlinks()
        assert len(symlinks) == 0

        # After install - plugin symlink included
        installer.install()
        symlinks = installer.get_symlinks()
        assert len(symlinks) == 1
        assert symlinks[0].name == "spellbook-forged"

    def test_install_skips_plugin_if_source_missing(self, tmp_path, opencode_config_dir):
        """Test that install skips plugin if source directory doesn't exist."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Create spellbook dir WITHOUT plugin
        spellbook = tmp_path / "spellbook"
        spellbook.mkdir()
        (spellbook / ".version").write_text("0.1.0")
        (spellbook / "AGENTS.spellbook.md").write_text("# Test")

        installer = OpenCodeInstaller(spellbook, opencode_config_dir, "0.1.0")
        results = installer.install()

        # Check no plugin result (it's skipped silently)
        plugin_result = next((r for r in results if r.component == "plugin"), None)
        assert plugin_result is None

        # Check plugins directory was NOT created
        assert not (opencode_config_dir / "plugins").exists()

    def test_dry_run_does_not_create_plugin(self, spellbook_dir, opencode_config_dir):
        """Test that dry_run=True does not create plugin symlink."""
        from installer.platforms.opencode import OpenCodeInstaller

        installer = OpenCodeInstaller(spellbook_dir, opencode_config_dir, "0.1.0", dry_run=True)
        results = installer.install()

        # Check plugins directory was NOT created
        assert not (opencode_config_dir / "plugins").exists()

        # Check results show what would happen
        plugin_result = next((r for r in results if r.component == "plugin"), None)
        assert plugin_result is not None
        assert plugin_result.success is True


class TestOpenCodeInConfig:
    """Tests for OpenCode in installer/config.py."""

    def test_opencode_in_supported_platforms(self):
        """Test OpenCode is in SUPPORTED_PLATFORMS."""
        from installer.config import SUPPORTED_PLATFORMS

        assert "opencode" in SUPPORTED_PLATFORMS

    def test_opencode_platform_config(self):
        """Test OpenCode platform configuration."""
        from installer.config import PLATFORM_CONFIG

        assert "opencode" in PLATFORM_CONFIG

        opencode_config = PLATFORM_CONFIG["opencode"]
        assert opencode_config["name"] == "OpenCode"
        assert opencode_config["context_file"] == "AGENTS.md"
        assert opencode_config["mcp_supported"] is True

    def test_get_platform_config_dir(self):
        """Test get_platform_config_dir for OpenCode."""
        from installer.config import get_platform_config_dir

        # OpenCode uses a fixed default path (no env var override)
        config_dir = get_platform_config_dir("opencode")
        assert config_dir.name == "opencode"
        assert config_dir.parent.name == ".config"


class TestOpenCodeInCore:
    """Tests for OpenCode in installer/core.py."""

    def test_get_platform_installer_opencode(self, spellbook_dir, tmp_path, monkeypatch):
        """Test get_platform_installer returns OpenCodeInstaller."""
        from installer.core import get_platform_installer
        from installer.platforms.opencode import OpenCodeInstaller

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        installer = get_platform_installer("opencode", spellbook_dir, "0.1.0")

        assert isinstance(installer, OpenCodeInstaller)
