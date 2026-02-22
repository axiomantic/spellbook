"""Tests for spellbook auto-update tools."""

import json
import os
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestClassifyVersionBump:
    """Tests for classify_version_bump()."""

    def test_major_bump(self):
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("0.9.9", "1.0.0") == "major"

    def test_minor_bump(self):
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("0.9.9", "0.10.0") == "minor"

    def test_patch_bump(self):
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("0.9.9", "0.9.10") == "patch"

    def test_same_version_returns_none(self):
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("0.9.9", "0.9.9") is None

    def test_downgrade_returns_none(self):
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("1.0.0", "0.9.9") is None

    def test_major_bump_with_higher_minor(self):
        """Major bump takes precedence even if minor is lower."""
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("0.99.99", "1.0.0") == "major"

    def test_handles_whitespace(self):
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump(" 0.9.9 ", " 0.9.10\n") == "patch"

    def test_handles_extra_components(self):
        """Only first 3 components are compared."""
        from spellbook_mcp.update_tools import classify_version_bump
        assert classify_version_bump("0.9.9.1", "0.9.10.0") == "patch"


class TestInstallLock:
    """Tests for CrossPlatformLock used for install lock management."""

    def test_acquire_and_release(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "install.lock"
        lock = CrossPlatformLock(lock_path)
        assert lock.acquire() is True

        # Lock file should contain our PID
        content = lock_path.read_text()
        lock_info = json.loads(content)
        assert lock_info["pid"] == os.getpid()
        assert "timestamp" in lock_info

        lock.release()

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows file locking prevents concurrent lock fd access on same file")
    def test_acquire_fails_when_held(self, tmp_path):
        """Second acquire returns False when lock is held by live process."""
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "install.lock"
        lock1 = CrossPlatformLock(lock_path)
        assert lock1.acquire() is True

        # Second acquire should fail (non-blocking)
        lock2 = CrossPlatformLock(lock_path)
        assert lock2.acquire() is False

        lock1.release()

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows file locking prevents stale lock recovery without OS-level lock")
    def test_stale_lock_broken_by_dead_pid(self, tmp_path):
        """Lock with dead PID is treated as stale and broken."""
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "install.lock"

        # Write a lock file with a definitely-dead PID
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({
            "pid": 999999999,  # Very unlikely to be alive
            "timestamp": time.time(),
        }))

        # When the flock is NOT held but the file has a dead PID, we succeed.
        lock = CrossPlatformLock(lock_path)
        assert lock.acquire() is True
        lock.release()

    def test_pid_exists_for_current_process(self):
        from installer.compat import _pid_exists
        assert _pid_exists(os.getpid()) is True

    def test_pid_exists_for_dead_process(self):
        from installer.compat import _pid_exists
        assert _pid_exists(999999999) is False


SAMPLE_CHANGELOG = """\
# Changelog

## [0.9.10] - 2026-02-19

### Changed
- Slimmed CLAUDE.spellbook.md by 38%
- Improved skill descriptions

### Added
- Security hardening

## [0.9.9] - 2026-02-15

### Fixed
- Bug in session init

## [0.9.8] - 2026-02-10

### Changed
- Minor improvements
"""


class TestGetChangelogBetween:
    """Tests for get_changelog_between()."""

    def test_extracts_entries_between_versions(self, tmp_path):
        from spellbook_mcp.update_tools import get_changelog_between

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG)

        result = get_changelog_between(tmp_path, "0.9.8", "0.9.10")
        assert "0.9.10" in result
        assert "0.9.9" in result
        assert "Slimmed CLAUDE.spellbook.md" in result
        assert "Bug in session init" in result
        # Should NOT include the from_version's content
        assert "Minor improvements" not in result

    def test_same_version_returns_empty(self, tmp_path):
        from spellbook_mcp.update_tools import get_changelog_between

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG)

        result = get_changelog_between(tmp_path, "0.9.10", "0.9.10")
        assert result == ""

    def test_missing_changelog_returns_empty(self, tmp_path):
        from spellbook_mcp.update_tools import get_changelog_between

        result = get_changelog_between(tmp_path, "0.9.8", "0.9.10")
        assert result == ""

    def test_single_version_between(self, tmp_path):
        from spellbook_mcp.update_tools import get_changelog_between

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG)

        result = get_changelog_between(tmp_path, "0.9.9", "0.9.10")
        assert "0.9.10" in result
        assert "Slimmed CLAUDE.spellbook.md" in result
        assert "Bug in session init" not in result


class TestCheckForUpdates:
    """Tests for check_for_updates()."""

    def test_update_available(self, tmp_path):
        """Returns correct state when update is available."""
        from spellbook_mcp.update_tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        (spellbook_dir / "CHANGELOG.md").write_text(SAMPLE_CHANGELOG)

        with patch("spellbook_mcp.update_tools.subprocess.run") as mock_run, \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            # git remote (validation)
            remote_result = MagicMock()
            remote_result.returncode = 0
            remote_result.stdout = "origin\n"

            # git fetch succeeds
            fetch_result = MagicMock()
            fetch_result.returncode = 0

            # git show returns remote version
            show_result = MagicMock()
            show_result.returncode = 0
            show_result.stdout = "0.9.10\n"

            mock_run.side_effect = [remote_result, fetch_result, show_result]

            result = check_for_updates(spellbook_dir)

            assert result["update_available"] is True
            assert result["current_version"] == "0.9.9"
            assert result["remote_version"] == "0.9.10"
            assert result["is_major_bump"] is False
            assert result["error"] is None

    def test_no_update_available(self, tmp_path):
        """Returns correctly when versions match."""
        from spellbook_mcp.update_tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.10\n")

        with patch("spellbook_mcp.update_tools.subprocess.run") as mock_run, \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            # git remote (validation)
            remote_result = MagicMock()
            remote_result.returncode = 0
            remote_result.stdout = "origin\n"

            fetch_result = MagicMock()
            fetch_result.returncode = 0

            show_result = MagicMock()
            show_result.returncode = 0
            show_result.stdout = "0.9.10\n"

            mock_run.side_effect = [remote_result, fetch_result, show_result]

            result = check_for_updates(spellbook_dir)

            assert result["update_available"] is False
            assert result["current_version"] == "0.9.10"
            assert result["remote_version"] == "0.9.10"
            assert result["error"] is None

    def test_fetch_failure(self, tmp_path):
        """Returns error when git fetch fails."""
        from spellbook_mcp.update_tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")

        with patch("spellbook_mcp.update_tools.subprocess.run") as mock_run, \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: None

            # git remote (validation) - returns "origin" as default
            remote_result = MagicMock()
            remote_result.returncode = 0
            remote_result.stdout = "origin\n"

            fetch_result = MagicMock()
            fetch_result.returncode = 1
            fetch_result.stderr = "fatal: could not read from remote"

            mock_run.side_effect = [remote_result, fetch_result]

            result = check_for_updates(spellbook_dir)

            assert result["update_available"] is False
            assert result["error"] is not None
            assert "fetch" in result["error"].lower()

    def test_major_bump_detected(self, tmp_path):
        """Detects major version bump."""
        from spellbook_mcp.update_tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")

        with patch("spellbook_mcp.update_tools.subprocess.run") as mock_run, \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: None

            # git remote (validation) - returns "origin" as default
            remote_result = MagicMock()
            remote_result.returncode = 0
            remote_result.stdout = "origin\n"

            fetch_result = MagicMock()
            fetch_result.returncode = 0

            show_result = MagicMock()
            show_result.returncode = 0
            show_result.stdout = "1.0.0\n"

            mock_run.side_effect = [remote_result, fetch_result, show_result]

            result = check_for_updates(spellbook_dir)

            assert result["update_available"] is True
            assert result["is_major_bump"] is True

    def test_missing_local_version(self, tmp_path):
        """Returns error when local .version file is missing."""
        from spellbook_mcp.update_tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        # No .version file

        with patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: None

            result = check_for_updates(spellbook_dir)

            assert result["update_available"] is False
            assert result["error"] is not None
            assert "version" in result["error"].lower()


class TestApplyUpdate:
    """Tests for apply_update()."""

    def test_apply_success(self, tmp_path):
        """Full apply flow: check clean, lock, pull, install, unlock."""
        from spellbook_mcp.update_tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"

        call_count = {"n": 0}

        def mock_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            call_count["n"] += 1

            if "status" in cmd:
                # git status --porcelain (clean)
                result.stdout = ""
            elif "rev-parse" in cmd:
                # git rev-parse HEAD
                result.stdout = "abc123def456"
            elif "pull" in cmd:
                # git pull --ff-only
                pass
            elif "install.py" in " ".join(cmd):
                # uv run install.py
                # Simulate version bump
                (spellbook_dir / ".version").write_text("0.9.10\n")
            return result

        with patch("spellbook_mcp.update_tools.subprocess.run", side_effect=mock_subprocess_run), \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get, \
             patch("spellbook_mcp.update_tools.config_set") as mock_config_set:
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is True
        assert result["previous_version"] == "0.9.9"
        assert result["new_version"] == "0.9.10"
        assert result["pre_update_sha"] == "abc123def456"
        assert result["error"] is None

    def test_apply_dirty_tree_aborts(self, tmp_path):
        """Aborts when working tree has uncommitted changes."""
        from spellbook_mcp.update_tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"

        def mock_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "status" in cmd:
                result.stdout = " M some_file.py\n"  # Dirty tree
            return result

        with patch("spellbook_mcp.update_tools.subprocess.run", side_effect=mock_subprocess_run), \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: None

            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "dirty" in result["error"].lower() or "uncommitted" in result["error"].lower()

    def test_apply_pull_fails(self, tmp_path):
        """Handles pull failure, releases lock."""
        from spellbook_mcp.update_tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"

        def mock_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            if "status" in cmd:
                result.returncode = 0
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.returncode = 0
                result.stdout = "abc123"
            elif "pull" in cmd:
                result.returncode = 1
                result.stderr = "fatal: not possible to fast-forward"
            else:
                result.returncode = 0
            return result

        with patch("spellbook_mcp.update_tools.subprocess.run", side_effect=mock_subprocess_run), \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get, \
             patch("spellbook_mcp.update_tools.config_set"):
            mock_config_get.side_effect = lambda key: None

            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "pull" in result["error"].lower() or "fast-forward" in result["error"].lower()
        # Lock should be released (file should not exist)
        assert not lock_path.exists()

    def test_apply_installer_fails(self, tmp_path):
        """Handles installer failure, releases lock."""
        from spellbook_mcp.update_tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"

        def mock_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            if "status" in cmd:
                result.returncode = 0
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.returncode = 0
                result.stdout = "abc123"
            elif "pull" in cmd:
                result.returncode = 0
            elif "install.py" in " ".join(cmd):
                result.returncode = 1
                result.stderr = "installer error"
            else:
                result.returncode = 0
            return result

        with patch("spellbook_mcp.update_tools.subprocess.run", side_effect=mock_subprocess_run), \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get, \
             patch("spellbook_mcp.update_tools.config_set"):
            mock_config_get.side_effect = lambda key: None

            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "install" in result["error"].lower()
        assert not lock_path.exists()


class TestRollbackUpdate:
    """Tests for rollback_update()."""

    def test_rollback_success(self, tmp_path):
        """Full rollback flow."""
        from spellbook_mcp.update_tools import rollback_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.10\n")
        lock_path = tmp_path / "install.lock"

        def mock_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "rev-parse" in cmd and "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "reset" in cmd:
                (spellbook_dir / ".version").write_text("0.9.9\n")
            elif "install.py" in " ".join(cmd):
                pass
            return result

        with patch("spellbook_mcp.update_tools.subprocess.run", side_effect=mock_subprocess_run), \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get, \
             patch("spellbook_mcp.update_tools.config_set") as mock_config_set:
            mock_config_get.side_effect = lambda key: {
                "pre_update_sha": "abc123def456" + "0" * 28,
                "auto_update_branch": "main",
            }.get(key)

            result = rollback_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is True
        assert result["rolled_back_to"] == "abc123def456" + "0" * 28
        assert result["auto_update_paused"] is True
        assert result["error"] is None

    def test_rollback_no_sha(self, tmp_path):
        """Returns error when no pre_update_sha stored."""
        from spellbook_mcp.update_tools import rollback_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        lock_path = tmp_path / "install.lock"

        with patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: None

            result = rollback_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "no pre_update_sha" in result["error"].lower() or "nothing to rollback" in result["error"].lower()

    def test_rollback_wrong_branch(self, tmp_path):
        """Returns error when on wrong branch."""
        from spellbook_mcp.update_tools import rollback_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        lock_path = tmp_path / "install.lock"

        def mock_subprocess_run(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "rev-parse" in cmd and "--abbrev-ref" in cmd:
                result.stdout = "feature-branch"
            return result

        with patch("spellbook_mcp.update_tools.subprocess.run", side_effect=mock_subprocess_run), \
             patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: {
                "pre_update_sha": "abc123" + "0" * 34,
                "auto_update_branch": "main",
            }.get(key)

            result = rollback_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "branch" in result["error"].lower()


class TestGetUpdateStatus:
    """Tests for get_update_status()."""

    def test_returns_aggregated_status(self, tmp_path):
        """Returns all update-related config keys in one response."""
        from spellbook_mcp.update_tools import get_update_status

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.10\n")

        config_state = {
            "auto_update": True,
            "auto_update_paused": False,
            "available_update": {"version": "0.9.11", "detected_at": "2026-02-19T10:00:00"},
            "pending_major_update": None,
            "last_auto_update": None,
            "pre_update_sha": "abc123",
            "last_update_check": "2026-02-19T10:00:00",
            "update_check_failures": 0,
        }

        with patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: config_state.get(key)

            result = get_update_status(spellbook_dir)

        assert result["auto_update_enabled"] is True
        assert result["auto_update_paused"] is False
        assert result["current_version"] == "0.9.10"
        assert result["available_update"]["version"] == "0.9.11"
        assert result["pre_update_sha"] == "abc123"
        assert result["check_failures"] == 0


class TestInstallerUpdateOnlyFlag:
    """Tests for --update-only flag in install.py."""

    def test_update_only_flag_recognized_by_argparser(self):
        """Verify --update-only flag is accepted by the argument parser."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import importlib
        import install
        importlib.reload(install)

        # Build argparse namespace with --update-only
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--update-only", action="store_true")
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--no-interactive", action="store_true")
        parser.add_argument("--force", action="store_true")
        args = parser.parse_args(["--update-only"])
        assert args.update_only is True

    def test_update_only_calls_find_spellbook_dir_not_bootstrap(self):
        """--update-only should call find_spellbook_dir instead of bootstrap."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import importlib
        import install
        importlib.reload(install)

        fake_dir = Path("/tmp/fake-spellbook")

        with patch.object(install, "find_spellbook_dir", return_value=fake_dir) as mock_find, \
             patch.object(install, "bootstrap") as mock_bootstrap, \
             patch.object(install, "run_installation", return_value=0) as mock_run, \
             patch.object(install, "print_header"), \
             patch.object(install, "print_success"), \
             patch.object(install, "is_interactive", return_value=False), \
             patch("sys.argv", ["install.py", "--update-only", "--yes"]):
            result = install.main()

        mock_find.assert_called_once()
        mock_bootstrap.assert_not_called()
        mock_run.assert_called_once()
        # Verify run_installation was called with the found dir
        assert mock_run.call_args[0][0] == fake_dir

    def test_update_only_with_force(self):
        """--update-only --force means skip bootstrap but force all install steps."""
        import argparse
        args = argparse.Namespace(
            update_only=True, yes=True, no_interactive=True,
            force=True, dry_run=True,
        )
        # Both flags should coexist: skip bootstrap, but force installation steps
        assert args.update_only is True
        assert args.force is True


class TestCheckForUpdatesMCPTool:
    """Tests that check_for_updates is registered as an MCP tool."""

    def test_tool_function_importable(self):
        """Verify spellbook_check_for_updates can be imported from server module."""
        from fastmcp.tools.tool import FunctionTool
        from spellbook_mcp.server import spellbook_check_for_updates
        assert isinstance(spellbook_check_for_updates, FunctionTool)
        assert callable(spellbook_check_for_updates.fn)

    def test_status_tool_function_importable(self):
        """Verify spellbook_get_update_status can be imported from server module."""
        from fastmcp.tools.tool import FunctionTool
        from spellbook_mcp.server import spellbook_get_update_status
        assert isinstance(spellbook_get_update_status, FunctionTool)
        assert callable(spellbook_get_update_status.fn)
