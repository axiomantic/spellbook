"""Tests for multi-target config resolution: resolve_config_dirs() and PLATFORM_CONFIG entries."""

from pathlib import Path

import pytest

from installer.config import PLATFORM_CONFIG, resolve_config_dirs


class TestPlatformConfigEntries:
    """Tests for PLATFORM_CONFIG structure and values."""

    def test_all_platforms_have_config_dir_env(self):
        """All 5 platforms in PLATFORM_CONFIG have non-None config_dir_env."""
        assert len(PLATFORM_CONFIG) == 5
        for platform_id, config in PLATFORM_CONFIG.items():
            assert config["config_dir_env"] is not None, (
                f"{platform_id} has None config_dir_env"
            )
            assert isinstance(config["config_dir_env"], str), (
                f"{platform_id} config_dir_env is not a string"
            )

    def test_all_platforms_have_cli_flag_name(self):
        """All 5 platforms have string cli_flag_name using hyphens (not underscores)."""
        for platform_id, config in PLATFORM_CONFIG.items():
            flag = config["cli_flag_name"]
            assert isinstance(flag, str), (
                f"{platform_id} cli_flag_name is not a string"
            )
            assert "_" not in flag, (
                f"{platform_id} cli_flag_name '{flag}' contains underscores; use hyphens"
            )
            assert "-" in flag, (
                f"{platform_id} cli_flag_name '{flag}' has no hyphens"
            )

    def test_specific_env_var_names(self):
        """Verify exact env var names for each platform."""
        expected = {
            "claude_code": "CLAUDE_CONFIG_DIR",
            "opencode": "OPENCODE_CONFIG_DIR",
            "codex": "CODEX_CONFIG_DIR",
            "gemini": "GEMINI_CONFIG_DIR",
            "forgecode": "FORGE_CONFIG",
        }
        for platform_id, expected_env in expected.items():
            assert PLATFORM_CONFIG[platform_id]["config_dir_env"] == expected_env, (
                f"{platform_id}: expected {expected_env}, "
                f"got {PLATFORM_CONFIG[platform_id]['config_dir_env']}"
            )

    def test_specific_cli_flag_names(self):
        """Verify exact CLI flag names for each platform."""
        expected = {
            "claude_code": "claude-config-dir",
            "opencode": "opencode-config-dir",
            "codex": "codex-config-dir",
            "gemini": "gemini-config-dir",
            "forgecode": "forge-config-dir",
        }
        for platform_id, expected_flag in expected.items():
            assert PLATFORM_CONFIG[platform_id]["cli_flag_name"] == expected_flag, (
                f"{platform_id}: expected {expected_flag}, "
                f"got {PLATFORM_CONFIG[platform_id]['cli_flag_name']}"
            )


# Build a minimal fake PLATFORM_CONFIG for resolve_config_dirs tests.
# Each test patches installer.config.PLATFORM_CONFIG with this so that
# default_config_dir points into the test's tmp_path.

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


class TestResolveConfigDirs:
    """Tests for resolve_config_dirs() with patched PLATFORM_CONFIG."""

    @pytest.fixture(autouse=True)
    def _patch_config(self, monkeypatch):
        """Ensure FAKE_CONFIG_DIR is not set in environment for all tests."""
        monkeypatch.delenv("FAKE_CONFIG_DIR", raising=False)

    def test_default_behavior_returns_single_default_dir(self, tmp_path, monkeypatch):
        """No CLI, no env -> single default dir (created if missing)."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform")

        assert len(result) == 1
        assert result[0] == default_dir
        # Default dir should have been created
        assert default_dir.exists()

    def test_cli_single_dir(self, tmp_path, monkeypatch):
        """Single CLI dir returns that dir."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        cli_dir = tmp_path / "cli_config"
        cli_dir.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform", cli_dirs=[cli_dir])

        assert len(result) == 1
        assert result[0] == cli_dir

    def test_cli_multiple_dirs(self, tmp_path, monkeypatch):
        """Multiple CLI dirs returns all."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform", cli_dirs=[dir1, dir2])

        assert len(result) == 2
        assert result[0] == dir1
        assert result[1] == dir2

    def test_cli_overrides_env_var(self, tmp_path, monkeypatch):
        """CLI dirs override env var."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        cli_dir = tmp_path / "cli_config"
        env_dir = tmp_path / "env_config"
        cli_dir.mkdir()
        env_dir.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        monkeypatch.setenv("FAKE_CONFIG_DIR", str(env_dir))
        result = resolve_config_dirs("fake_platform", cli_dirs=[cli_dir])

        # CLI should win over env
        assert len(result) == 1
        assert result[0] == cli_dir

    def test_env_var_overrides_default(self, tmp_path, monkeypatch):
        """Env var replaces default."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        env_dir = tmp_path / "env_config"
        env_dir.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        monkeypatch.setenv("FAKE_CONFIG_DIR", str(env_dir))
        result = resolve_config_dirs("fake_platform")

        assert len(result) == 1
        assert result[0] == env_dir
        # Default dir should NOT have been created
        assert not default_dir.exists()

    def test_env_override_param(self, tmp_path, monkeypatch):
        """The env_override parameter bypasses os.environ."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        override_dir = tmp_path / "override_config"
        env_dir = tmp_path / "env_config"
        override_dir.mkdir()
        env_dir.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        monkeypatch.setenv("FAKE_CONFIG_DIR", str(env_dir))
        result = resolve_config_dirs(
            "fake_platform", env_override=str(override_dir)
        )

        # env_override should win over os.environ
        assert len(result) == 1
        assert result[0] == override_dir

    def test_deduplication(self, tmp_path, monkeypatch):
        """Same dir twice -> deduplicated to 1."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        cli_dir = tmp_path / "cli_config"
        cli_dir.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs(
            "fake_platform", cli_dirs=[cli_dir, cli_dir]
        )

        assert len(result) == 1
        assert result[0] == cli_dir

    def test_nonexistent_cli_dir_skipped(self, tmp_path, monkeypatch):
        """Non-existent CLI dir skipped (returns empty)."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        missing_dir = tmp_path / "does_not_exist"
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform", cli_dirs=[missing_dir])

        assert result == []

    def test_nonexistent_default_dir_created(self, tmp_path, monkeypatch):
        """Default dir auto-created."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        assert not default_dir.exists()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform")

        assert len(result) == 1
        assert default_dir.exists()

    def test_all_cli_dirs_invalid_returns_empty(self, tmp_path, monkeypatch):
        """All invalid CLI dirs -> empty."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        bad1 = tmp_path / "nope1"
        bad2 = tmp_path / "nope2"
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform", cli_dirs=[bad1, bad2])

        assert result == []

    def test_mixed_valid_invalid_cli_dirs(self, tmp_path, monkeypatch):
        """Mix of valid/invalid -> only valid returned."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        good = tmp_path / "good"
        bad = tmp_path / "bad"
        good.mkdir()
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        result = resolve_config_dirs("fake_platform", cli_dirs=[bad, good])

        assert len(result) == 1
        assert result[0] == good

    def test_nonexistent_env_dir_skipped(self, tmp_path, monkeypatch):
        """Non-existent env dir -> empty (not fallen back to default)."""
        import installer.config as config_mod

        default_dir = tmp_path / "default_config"
        missing_env = tmp_path / "env_missing"
        fake_config = _fake_platform_config(default_dir)

        monkeypatch.setattr(config_mod, "PLATFORM_CONFIG", fake_config)
        monkeypatch.setenv("FAKE_CONFIG_DIR", str(missing_env))
        result = resolve_config_dirs("fake_platform")

        # Should be empty because env dir doesn't exist, and since it was
        # explicit, it should NOT fall back to the default dir
        assert result == []
        # Default dir should NOT have been created
        assert not default_dir.exists()
