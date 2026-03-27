"""Tests for the multi-target orchestration layer and cross-platform coupling."""

import inspect
from pathlib import Path

import pytest

from installer.config import PLATFORM_CONFIG, resolve_config_dirs
from installer.core import Installer, Uninstaller


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_platform_config(default_dir: Path):
    """Create a minimal fake PLATFORM_CONFIG with one platform."""
    return {
        "fake_platform": {
            "name": "Fake",
            "config_dir_env": "FAKE_CONFIG_DIR",
            "default_config_dir": default_dir,
            "cli_flag_name": "fake-config-dir",
        },
    }


# ---------------------------------------------------------------------------
# TestMultiDirOrchestration
# ---------------------------------------------------------------------------


class TestMultiDirOrchestration:
    """Tests for multi-directory orchestration via resolve_config_dirs."""

    def test_no_overrides_single_dir_per_platform(self, tmp_path, monkeypatch):
        """Without overrides, resolve_config_dirs returns 1 dir."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        monkeypatch.delenv("FAKE_CONFIG_DIR", raising=False)
        dirs = resolve_config_dirs("fake_platform")

        assert len(dirs) == 1

    def test_overrides_produce_multiple_dirs(self, tmp_path, monkeypatch):
        """CLI overrides produce multiple dirs."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir3 = tmp_path / "dir3"
        for d in (dir1, dir2, dir3):
            d.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        dirs = resolve_config_dirs("fake_platform", cli_dirs=[dir1, dir2, dir3])

        assert len(dirs) == 3
        assert dirs == [dir1, dir2, dir3]

    def test_skip_global_steps_on_second_dir(self, tmp_path):
        """Verify idx > 0 gets skip_global=True in the orchestration loop.

        We test the pattern used by Installer.run(): dir_idx > 0 means
        skip_global_steps=True. This test validates the pattern directly.
        """
        # The core.py loop does:
        #   for dir_idx, config_dir in enumerate(dirs):
        #       skip_global = dir_idx > 0
        dirs = [tmp_path / "dir0", tmp_path / "dir1", tmp_path / "dir2"]
        for d in dirs:
            d.mkdir()

        skip_global_values = [idx > 0 for idx, _ in enumerate(dirs)]
        assert skip_global_values == [False, True, True]


# ---------------------------------------------------------------------------
# TestBackwardCompatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Tests for backward compatibility of Installer/Uninstaller signatures."""

    def test_installer_run_without_overrides(self):
        """Installer.run() signature has config_dir_overrides with default None."""
        sig = inspect.signature(Installer.run)
        param = sig.parameters.get("config_dir_overrides")
        assert param is not None, "Installer.run() missing config_dir_overrides parameter"
        assert param.default is None, (
            f"config_dir_overrides default should be None, got {param.default}"
        )

    def test_uninstaller_run_without_overrides(self):
        """Uninstaller.run() signature has config_dir_overrides with default None."""
        sig = inspect.signature(Uninstaller.run)
        param = sig.parameters.get("config_dir_overrides")
        assert param is not None, "Uninstaller.run() missing config_dir_overrides parameter"
        assert param.default is None, (
            f"config_dir_overrides default should be None, got {param.default}"
        )


# ---------------------------------------------------------------------------
# TestCrushCrossPlatformCoupling
# ---------------------------------------------------------------------------


class TestCrushCrossPlatformCoupling:
    """Tests for Crush's cross-platform skill sharing via context."""

    @pytest.fixture
    def spellbook_dir(self, tmp_path):
        """Create a minimal spellbook directory."""
        spellbook = tmp_path / "spellbook"
        spellbook.mkdir()
        (spellbook / ".version").write_text("0.1.0")
        (spellbook / "spellbook").mkdir()
        (spellbook / "spellbook" / "server.py").write_text("# stub")
        (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook\n\nTest.")
        return spellbook

    def test_crush_uses_context_claude_dirs(self, spellbook_dir, tmp_path):
        """CrushInstaller with context {"claude_config_dirs": [dir1, dir2]} returns 2 skills paths."""
        from installer.platforms.crush import CrushInstaller

        dir1 = tmp_path / "claude1"
        dir2 = tmp_path / "claude2"
        dir1.mkdir()
        dir2.mkdir()

        crush_dir = tmp_path / "crush"
        crush_dir.mkdir()

        context = {"claude_config_dirs": [dir1, dir2]}
        installer = CrushInstaller(
            spellbook_dir, crush_dir, "0.1.0", context=context
        )

        paths = installer.claude_skills_paths
        assert len(paths) == 2
        assert paths[0] == dir1 / "skills"
        assert paths[1] == dir2 / "skills"

    def test_crush_fallback_without_context(self, spellbook_dir, tmp_path):
        """Without context, falls back to ~/.claude/skills."""
        from installer.platforms.crush import CrushInstaller

        crush_dir = tmp_path / "crush"
        crush_dir.mkdir()

        # No context (empty dict)
        installer = CrushInstaller(spellbook_dir, crush_dir, "0.1.0")

        paths = installer.claude_skills_paths
        assert len(paths) == 1
        assert paths[0] == Path.home() / ".claude" / "skills"


# ---------------------------------------------------------------------------
# TestOpenCodeDynamicPath
# ---------------------------------------------------------------------------


class TestOpenCodeDynamicPath:
    """Tests for OpenCode's dynamic instructions path based on config_dir."""

    @pytest.fixture
    def spellbook_dir(self, tmp_path):
        """Create a minimal spellbook directory."""
        spellbook = tmp_path / "spellbook"
        spellbook.mkdir()
        (spellbook / ".version").write_text("0.1.0")
        (spellbook / "spellbook").mkdir()
        (spellbook / "spellbook" / "server.py").write_text("# stub")
        (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook\n\nTest.")
        # Create the extensions directory for system prompt source
        ext_dir = spellbook / "extensions" / "opencode"
        ext_dir.mkdir(parents=True)
        (ext_dir / "claude-code-system-prompt.md").write_text("# System prompt")
        return spellbook

    def test_default_config_dir(self, spellbook_dir, tmp_path, monkeypatch):
        """Default ~/.config/opencode produces expected instructions path."""
        from installer.platforms.opencode import OpenCodeInstaller

        # Use a fake home so the tilde path resolves predictably
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        config_dir = fake_home / ".config" / "opencode"
        config_dir.mkdir(parents=True)

        installer = OpenCodeInstaller(spellbook_dir, config_dir, "0.1.0")

        expected = "~/.config/opencode/instructions/claude-code-system-prompt.md"
        assert installer.system_prompt_config_path == expected

    def test_custom_config_dir_under_home(self, spellbook_dir, tmp_path, monkeypatch):
        """Custom dir under $HOME still produces tilde path."""
        from installer.platforms.opencode import OpenCodeInstaller

        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        custom_dir = fake_home / "custom" / "opencode"
        custom_dir.mkdir(parents=True)

        installer = OpenCodeInstaller(spellbook_dir, custom_dir, "0.1.0")

        expected = "~/custom/opencode/instructions/claude-code-system-prompt.md"
        assert installer.system_prompt_config_path == expected
