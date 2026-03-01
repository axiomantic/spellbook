"""Tests for the OpenCode security plugin and its installer integration.

The plugin is a TypeScript file (hooks/opencode-plugin.ts) that:
- Registers tool.execute.before and tool.execute.after hooks
- Shells out to python3 -m spellbook_mcp.security.check for security scanning
- Reads SPELLBOOK_DIR from environment

The installer (OpenCodeInstaller) should:
- Copy the plugin to ~/.config/opencode/plugins/spellbook-security.ts
- Be idempotent (re-running produces identical file)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from installer.platforms.opencode import OpenCodeInstaller


# --- Helpers ---


WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_SOURCE = WORKTREE_ROOT / "hooks" / "opencode-plugin.ts"


def _read_plugin_source():
    """Read the plugin TypeScript source file."""
    return PLUGIN_SOURCE.read_text(encoding="utf-8")


def _make_opencode_installer(tmp_path, dry_run=False):
    """Create an OpenCodeInstaller with a mock environment."""
    spellbook_dir = tmp_path / "spellbook"
    spellbook_dir.mkdir()

    # Create the plugin source
    hooks_dir = spellbook_dir / "hooks"
    hooks_dir.mkdir()
    # Copy the actual plugin source into the mock spellbook dir
    actual_source = PLUGIN_SOURCE
    if actual_source.exists():
        (hooks_dir / "opencode-plugin.ts").write_text(
            actual_source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        # Fail early if source doesn't exist yet
        pytest.fail(
            f"Plugin source file not found at {actual_source}. "
            "Create hooks/opencode-plugin.ts first."
        )

    # Create minimal required structure
    (spellbook_dir / ".version").write_text("1.0.0")
    (spellbook_dir / "AGENTS.spellbook.md").write_text("# Spellbook")
    (spellbook_dir / "skills").mkdir()
    (spellbook_dir / "commands").mkdir()

    # Opencode extensions directory (for existing plugin)
    ext_dir = spellbook_dir / "extensions" / "opencode" / "spellbook-forged"
    ext_dir.mkdir(parents=True)
    (ext_dir / "index.ts").write_text("// stub")
    # System prompt
    prompt_dir = spellbook_dir / "extensions" / "opencode"
    (prompt_dir / "claude-code-system-prompt.md").write_text("# Stub")

    config_dir = tmp_path / ".config" / "opencode"
    config_dir.mkdir(parents=True)

    installer = OpenCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=dry_run)
    return installer, config_dir


# --- Plugin Source Structure Tests ---


class TestPluginSourceStructure:
    """The TypeScript plugin source should have the required structure."""

    def test_plugin_source_file_exists(self):
        """hooks/opencode-plugin.ts must exist in the repository."""
        assert PLUGIN_SOURCE.exists(), (
            f"Plugin source file not found at {PLUGIN_SOURCE}"
        )

    def test_exports_default_object(self):
        """Plugin must export a default object."""
        content = _read_plugin_source()
        assert "export default" in content

    def test_has_name_property(self):
        """Plugin must declare name 'spellbook-security'."""
        content = _read_plugin_source()
        assert "'spellbook-security'" in content or '"spellbook-security"' in content

    def test_has_setup_function(self):
        """Plugin must have a setup() function."""
        content = _read_plugin_source()
        assert "setup(" in content

    def test_registers_before_hook(self):
        """Plugin must register a tool.execute.before hook."""
        content = _read_plugin_source()
        assert "tool.execute.before" in content

    def test_registers_after_hook(self):
        """Plugin must register a tool.execute.after hook."""
        content = _read_plugin_source()
        assert "tool.execute.after" in content

    def test_shells_out_to_check_module(self):
        """Plugin must shell out to python3 -m spellbook_mcp.security.check."""
        content = _read_plugin_source()
        assert "spellbook_mcp.security.check" in content
        assert "python3" in content

    def test_uses_check_output_flag(self):
        """Plugin's after hook must use --check-output flag."""
        content = _read_plugin_source()
        assert "--check-output" in content

    def test_reads_spellbook_dir_from_env(self):
        """Plugin must read SPELLBOOK_DIR from environment."""
        content = _read_plugin_source()
        assert "SPELLBOOK_DIR" in content
        # Should use process.env
        assert "process.env" in content

    def test_known_limitation_comment_exists(self):
        """Plugin must document the known limitation about subagent hooks."""
        content = _read_plugin_source()
        assert "subagent" in content.lower()
        assert "5894" in content or "issue" in content.lower()

    def test_handles_errors_gracefully(self):
        """Plugin must have error handling (try/catch or similar)."""
        content = _read_plugin_source()
        assert "catch" in content or "try" in content

    def test_uses_execsync_or_spawn(self):
        """Plugin must use child_process for subprocess execution."""
        content = _read_plugin_source()
        assert "child_process" in content or "execSync" in content or "spawnSync" in content

    def test_sends_json_via_stdin(self):
        """Plugin must send JSON to the check module via stdin."""
        content = _read_plugin_source()
        assert "stdin" in content.lower() or "input" in content.lower()
        assert "JSON.stringify" in content


# --- Installer Plugin Installation Tests ---


class TestInstallerPluginInstallation:
    """OpenCodeInstaller should install the security plugin."""

    def test_installer_has_security_plugin_source_property(self, tmp_path):
        """Installer should have a property for the security plugin source path."""
        installer, _ = _make_opencode_installer(tmp_path)
        source = installer.security_plugin_source
        assert isinstance(source, Path)
        assert source.name == "opencode-plugin.ts"

    def test_installer_has_security_plugin_target_property(self, tmp_path):
        """Installer should have a property for the security plugin target path."""
        installer, config_dir = _make_opencode_installer(tmp_path)
        target = installer.security_plugin_target
        assert isinstance(target, Path)
        assert target.name == "spellbook-security.ts"
        assert "plugins" in str(target)

    def test_install_creates_plugin_file(self, tmp_path):
        """install() should create the plugin at the expected path."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            results = installer.install()

        target = config_dir / "plugins" / "spellbook-security.ts"
        assert target.exists(), f"Plugin not found at {target}"

    def test_install_result_includes_security_plugin(self, tmp_path):
        """install() results should include a security_plugin component."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            results = installer.install()

        plugin_results = [r for r in results if r.component == "security_plugin"]
        assert len(plugin_results) == 1
        assert plugin_results[0].success

    def test_installed_plugin_matches_source(self, tmp_path):
        """The installed plugin file should match the source file."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            installer.install()

        target = config_dir / "plugins" / "spellbook-security.ts"
        source = installer.security_plugin_source
        assert target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    def test_idempotent_produces_identical_file(self, tmp_path):
        """Running install twice should produce an identical plugin file."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            installer.install()
            content_after_first = (config_dir / "plugins" / "spellbook-security.ts").read_text(
                encoding="utf-8"
            )
            installer.install()
            content_after_second = (config_dir / "plugins" / "spellbook-security.ts").read_text(
                encoding="utf-8"
            )

        assert content_after_first == content_after_second

    def test_idempotent_no_duplicate_results(self, tmp_path):
        """Running install twice should not produce error results for the plugin."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            results = installer.install()
            results2 = installer.install()

        plugin_results = [r for r in results2 if r.component == "security_plugin"]
        assert len(plugin_results) == 1
        assert plugin_results[0].success

    def test_dry_run_does_not_create_file(self, tmp_path):
        """In dry_run mode, the plugin file should not be created."""
        installer, config_dir = _make_opencode_installer(tmp_path, dry_run=True)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            results = installer.install()

        target = config_dir / "plugins" / "spellbook-security.ts"
        assert not target.exists()

    def test_creates_plugins_directory(self, tmp_path):
        """install() should create the plugins directory if it doesn't exist."""
        installer, config_dir = _make_opencode_installer(tmp_path)
        # Remove the plugins dir if it was created
        plugins_dir = config_dir / "plugins"
        if plugins_dir.exists():
            import shutil
            shutil.rmtree(plugins_dir)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            installer.install()

        assert plugins_dir.exists()

    def test_uninstall_removes_plugin(self, tmp_path):
        """uninstall() should remove the security plugin file."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            installer.install()

        target = config_dir / "plugins" / "spellbook-security.ts"
        assert target.exists()

        installer.uninstall()

        assert not target.exists()

    def test_detect_reports_security_plugin(self, tmp_path):
        """detect() should include security plugin status in details."""
        installer, config_dir = _make_opencode_installer(tmp_path)

        with patch("installer.platforms.opencode.generate_codex_context", return_value="# Context"):
            installer.install()

        status = installer.detect()
        assert "security_plugin_installed" in status.details
        assert status.details["security_plugin_installed"] is True

    def test_detect_reports_missing_security_plugin(self, tmp_path):
        """detect() should report False when security plugin is not installed."""
        installer, config_dir = _make_opencode_installer(tmp_path)
        status = installer.detect()
        assert "security_plugin_installed" in status.details
        assert status.details["security_plugin_installed"] is False
