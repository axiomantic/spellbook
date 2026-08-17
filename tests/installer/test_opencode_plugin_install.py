"""Tests for OpenCode gate-plugin deployment.

The plugin (`hooks/opencode-plugin.ts`) ships in the repo, is documented in
AGENTS.md, and has its own TypeScript tests. Commit 7a8e9ab1 removed its
install path as collateral of the gates-subsystem removal; these tests pin the
restored path so it cannot be lost again silently.
"""

from pathlib import Path

import pytest

from installer.platforms.opencode import OpenCodeInstaller

SPELLBOOK_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def installer(tmp_path):
    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    return OpenCodeInstaller(SPELLBOOK_DIR, config_dir, "0.1.0")


class TestGatePluginPaths:
    def test_source_points_at_shipped_plugin(self, installer):
        assert installer.gate_plugin_source == SPELLBOOK_DIR / "hooks" / "opencode-plugin.ts"
        assert installer.gate_plugin_source.is_file()

    def test_target_lives_in_plugins_dir(self, installer):
        assert installer.gate_plugin_target.parent == installer.plugins_dir


class TestGatePluginInstall:
    def test_install_writes_plugin(self, installer):
        installer.install()
        assert installer.gate_plugin_target.is_file()
        assert (
            installer.gate_plugin_target.read_text(encoding="utf-8")
            == installer.gate_plugin_source.read_text(encoding="utf-8")
        )

    def test_install_overwrites_stale_copy(self, installer):
        installer.plugins_dir.mkdir(parents=True)
        installer.gate_plugin_target.write_text("stale broken gate", encoding="utf-8")
        installer.install()
        assert "stale broken gate" not in installer.gate_plugin_target.read_text(encoding="utf-8")

    def test_dry_run_writes_nothing(self, tmp_path):
        config_dir = tmp_path / "opencode"
        config_dir.mkdir()
        dry = OpenCodeInstaller(SPELLBOOK_DIR, config_dir, "0.1.0", dry_run=True)
        dry.install()
        assert not dry.gate_plugin_target.exists()

    def test_install_reports_the_component(self, installer):
        results = installer.install()
        assert any(r.component == "gate_plugin" and r.success for r in results)


class TestGatePluginUninstall:
    def test_uninstall_removes_plugin(self, installer):
        installer.install()
        assert installer.gate_plugin_target.is_file()
        installer.uninstall()
        assert not installer.gate_plugin_target.exists()

    def test_uninstall_reports_the_component(self, installer):
        installer.install()
        results = installer.uninstall()
        assert any(r.component == "gate_plugin" for r in results)


class TestGatePluginDetect:
    def test_detect_reports_plugin_state(self, installer):
        assert installer.detect().details["gate_plugin_installed"] is False
        installer.install()
        assert installer.detect().details["gate_plugin_installed"] is True
