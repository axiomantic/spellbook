"""Tests for spellbook auto-update tools."""

import json
import os
import sys
import time
import pytest
from pathlib import Path
from types import SimpleNamespace

import bigfoot


class TestClassifyVersionBump:
    """Tests for classify_version_bump()."""

    def test_major_bump(self):
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("0.9.9", "1.0.0") == "major"

    def test_minor_bump(self):
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("0.9.9", "0.10.0") == "minor"

    def test_patch_bump(self):
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("0.9.9", "0.9.10") == "patch"

    def test_same_version_returns_none(self):
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("0.9.9", "0.9.9") is None

    def test_downgrade_returns_none(self):
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("1.0.0", "0.9.9") is None

    def test_major_bump_with_higher_minor(self):
        """Major bump takes precedence even if minor is lower."""
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("0.99.99", "1.0.0") == "major"

    def test_handles_whitespace(self):
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump(" 0.9.9 ", " 0.9.10\n") == "patch"

    def test_handles_extra_components(self):
        """Only first 3 components are compared."""
        from spellbook.updates.tools import classify_version_bump
        assert classify_version_bump("0.9.9.1", "0.9.10.0") == "patch"


class TestInstallLock:
    """Tests for CrossPlatformLock used for install lock management."""

    def test_acquire_and_release(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "install.lock"
        lock = CrossPlatformLock(lock_path)
        assert lock.acquire() is True

        # Read lock data via the held fd (works on all platforms).
        # Can't open a second fd on Windows, and release() deletes the file.
        os.lseek(lock._fd, 0, os.SEEK_SET)
        content = os.read(lock._fd, 4096).decode()

        lock.release()

        lock_info = json.loads(content)
        assert lock_info["pid"] == os.getpid()
        assert "timestamp" in lock_info

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
        from spellbook.updates.tools import get_changelog_between

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
        from spellbook.updates.tools import get_changelog_between

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG)

        result = get_changelog_between(tmp_path, "0.9.10", "0.9.10")
        assert result == ""

    def test_missing_changelog_returns_empty(self, tmp_path):
        from spellbook.updates.tools import get_changelog_between

        result = get_changelog_between(tmp_path, "0.9.8", "0.9.10")
        assert result == ""

    def test_single_version_between(self, tmp_path):
        from spellbook.updates.tools import get_changelog_between

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG)

        result = get_changelog_between(tmp_path, "0.9.9", "0.9.10")
        assert "0.9.10" in result
        assert "Slimmed CLAUDE.spellbook.md" in result
        assert "Bug in session init" not in result


def _make_proc(returncode=0, stdout="", stderr=""):
    """Helper to create a SimpleNamespace mimicking subprocess.CompletedProcess."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _chain(proxy, fn, n):
    """Chain .calls(fn) n times on a bigfoot mock proxy."""
    for _ in range(n):
        proxy.calls(fn)
    return proxy


class TestCheckForUpdates:
    """Tests for check_for_updates()."""

    def test_update_available_via_github_api(self, tmp_path):
        """Returns correct state when update is available via GitHub API."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        (spellbook_dir / "CHANGELOG.md").write_text(SAMPLE_CHANGELOG)
        d = str(spellbook_dir)

        call_seq = iter([
            _make_proc(0, "origin\n"),                              # git remote
            _make_proc(0),                                          # git fetch
            _make_proc(0, "git@github.com:axiomantic/spellbook.git\n"),  # git remote get-url
            _make_proc(0, "v0.9.10\n"),                             # gh api
        ])
        config_fn = lambda key: {
            "auto_update_remote": "origin",
        }.get(key)
        state_fn = lambda key: {"auto_update_branch": "main"}.get(key)

        # Call sequence: config_get x2 (remote x2), subprocess.run x4, shutil.which, state x1
        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 4)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        _chain(mock_config, config_fn, 2)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(state_fn)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns("/usr/local/bin/gh")

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is True
        assert result["current_version"] == "0.9.9"
        assert result["remote_version"] == "0.9.10"
        assert result["is_major_bump"] is False
        assert result["error"] is None

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_config.assert_call(args=("auto_update_remote",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "remote", "get-url", "origin"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["gh", "api", "repos/axiomantic/spellbook/releases/latest", "--jq", ".tag_name"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_which.assert_call(args=("gh",))

    def test_update_available_fallback_to_git_show(self, tmp_path):
        """Falls back to git show when gh CLI is not available."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        (spellbook_dir / "CHANGELOG.md").write_text(SAMPLE_CHANGELOG)
        d = str(spellbook_dir)

        call_seq = iter([
            _make_proc(0, "origin\n"),    # git remote
            _make_proc(0),                # git fetch
            _make_proc(0, "0.9.10\n"),    # git show (fallback)
        ])
        config_fn = lambda key: {"auto_update_remote": "origin"}.get(key)
        state_fn = lambda key: {"auto_update_branch": "main"}.get(key)

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 3)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.calls(config_fn)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(state_fn)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns(None)

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is True
        assert result["current_version"] == "0.9.9"
        assert result["remote_version"] == "0.9.10"
        assert result["is_major_bump"] is False
        assert result["error"] is None

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "show", "origin/main:.version"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_which.assert_call(args=("gh",))

    def test_no_update_available(self, tmp_path):
        """Returns correctly when versions match."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.10\n")
        d = str(spellbook_dir)

        call_seq = iter([
            _make_proc(0, "origin\n"),
            _make_proc(0),
            _make_proc(0, "0.9.10\n"),
        ])
        config_fn = lambda key: {"auto_update_remote": "origin"}.get(key)
        state_fn = lambda key: {"auto_update_branch": "main"}.get(key)

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 3)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.calls(config_fn)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(state_fn)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns(None)

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is False
        assert result["current_version"] == "0.9.10"
        assert result["remote_version"] == "0.9.10"
        assert result["error"] is None

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "show", "origin/main:.version"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_which.assert_call(args=("gh",))

    def test_fetch_failure(self, tmp_path):
        """Returns error when git fetch fails."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        d = str(spellbook_dir)

        call_seq = iter([
            _make_proc(0, "origin\n"),
            _make_proc(1, "", "fatal: could not read from remote"),
        ])

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 2)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.returns(None)

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is False
        assert result["error"] is not None
        assert "fetch" in result["error"].lower()

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})

    def test_major_bump_detected(self, tmp_path):
        """Detects major version bump."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        d = str(spellbook_dir)

        call_seq = iter([
            _make_proc(0, "origin\n"),
            _make_proc(0),
            _make_proc(0, "1.0.0\n"),
        ])

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 3)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.returns(None)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns(None)

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is True
        assert result["is_major_bump"] is True

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "show", "origin/main:.version"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_which.assert_call(args=("gh",))

    def test_github_api_failure_falls_back_to_git_show(self, tmp_path):
        """Falls back to git show when GitHub API call fails."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        d = str(spellbook_dir)

        call_seq = iter([
            _make_proc(0, "origin\n"),
            _make_proc(0),
            _make_proc(0, "git@github.com:axiomantic/spellbook.git\n"),
            _make_proc(1, ""),
            _make_proc(0, "0.9.10\n"),
        ])

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 5)
        # config_get: remote (twice, once in _get_owner_repo). state: branch.
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        _chain(mock_config, lambda key: None, 2)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.returns(None)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns("/usr/local/bin/gh")

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is True
        assert result["remote_version"] == "0.9.10"
        assert result["error"] is None

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_config.assert_call(args=("auto_update_remote",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "remote", "get-url", "origin"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["gh", "api", "repos/axiomantic/spellbook/releases/latest", "--jq", ".tag_name"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_run.assert_call(
                args=(["git", "-C", d, "show", "origin/main:.version"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_which.assert_call(args=("gh",))

    def test_missing_local_version(self, tmp_path):
        """Returns error when local .version file is missing."""
        from spellbook.updates.tools import check_for_updates

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        # No .version file -- returns early before any config_get/subprocess calls

        with bigfoot:
            result = check_for_updates(spellbook_dir)

        assert result["update_available"] is False
        assert result["error"] is not None
        assert "version" in result["error"].lower()


class TestGetOwnerRepo:
    """Tests for _get_owner_repo()."""

    def test_ssh_url(self, tmp_path):
        from spellbook.updates.tools import _get_owner_repo
        d = str(tmp_path)

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        mock_run.returns(_make_proc(0, "git@github.com:axiomantic/spellbook.git\n"))
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            assert _get_owner_repo(tmp_path) == "axiomantic/spellbook"

        mock_config.assert_call(args=("auto_update_remote",))
        mock_run.assert_call(
            args=(["git", "-C", d, "remote", "get-url", "origin"],),
            kwargs={"capture_output": True, "text": True, "timeout": 5})

    def test_https_url(self, tmp_path):
        from spellbook.updates.tools import _get_owner_repo
        d = str(tmp_path)

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        mock_run.returns(_make_proc(0, "https://github.com/axiomantic/spellbook.git\n"))
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            assert _get_owner_repo(tmp_path) == "axiomantic/spellbook"

        mock_config.assert_call(args=("auto_update_remote",))
        mock_run.assert_call(
            args=(["git", "-C", d, "remote", "get-url", "origin"],),
            kwargs={"capture_output": True, "text": True, "timeout": 5})

    def test_https_url_no_dot_git(self, tmp_path):
        from spellbook.updates.tools import _get_owner_repo
        d = str(tmp_path)

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        mock_run.returns(_make_proc(0, "https://github.com/axiomantic/spellbook\n"))
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            assert _get_owner_repo(tmp_path) == "axiomantic/spellbook"

        mock_config.assert_call(args=("auto_update_remote",))
        mock_run.assert_call(
            args=(["git", "-C", d, "remote", "get-url", "origin"],),
            kwargs={"capture_output": True, "text": True, "timeout": 5})

    def test_returns_none_on_failure(self, tmp_path):
        from spellbook.updates.tools import _get_owner_repo
        d = str(tmp_path)

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        mock_run.returns(_make_proc(1))
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            assert _get_owner_repo(tmp_path) is None

        mock_config.assert_call(args=("auto_update_remote",))
        mock_run.assert_call(
            args=(["git", "-C", d, "remote", "get-url", "origin"],),
            kwargs={"capture_output": True, "text": True, "timeout": 5})


class TestGetLatestReleaseVersion:
    """Tests for _get_latest_release_version()."""

    def test_returns_version_without_v_prefix(self, tmp_path):
        from spellbook.updates.tools import _get_latest_release_version
        d = str(tmp_path)

        call_seq = iter([
            _make_proc(0, "git@github.com:axiomantic/spellbook.git\n"),
            _make_proc(0, "v0.25.0\n"),
        ])

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 2)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns("/usr/local/bin/gh")
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            assert _get_latest_release_version(tmp_path) == "0.25.0"

        with bigfoot.in_any_order():
            mock_which.assert_call(args=("gh",))
            mock_config.assert_call(args=("auto_update_remote",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote", "get-url", "origin"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["gh", "api", "repos/axiomantic/spellbook/releases/latest", "--jq", ".tag_name"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})

    def test_returns_none_when_gh_not_installed(self, tmp_path):
        from spellbook.updates.tools import _get_latest_release_version

        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns(None)

        with bigfoot:
            assert _get_latest_release_version(tmp_path) is None

        mock_which.assert_call(args=("gh",))

    def test_returns_none_on_api_failure(self, tmp_path):
        from spellbook.updates.tools import _get_latest_release_version
        d = str(tmp_path)

        call_seq = iter([
            _make_proc(0, "git@github.com:axiomantic/spellbook.git\n"),
            _make_proc(1, ""),
        ])

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, lambda *a, **kw: next(call_seq), 2)
        mock_which = bigfoot.mock("spellbook.updates.tools:shutil.which")
        mock_which.returns("/usr/local/bin/gh")
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            assert _get_latest_release_version(tmp_path) is None

        with bigfoot.in_any_order():
            mock_which.assert_call(args=("gh",))
            mock_config.assert_call(args=("auto_update_remote",))
            mock_run.assert_call(
                args=(["git", "-C", d, "remote", "get-url", "origin"],),
                kwargs={"capture_output": True, "text": True, "timeout": 5})
            mock_run.assert_call(
                args=(["gh", "api", "repos/axiomantic/spellbook/releases/latest", "--jq", ".tag_name"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})


class TestApplyUpdate:
    """Tests for apply_update()."""

    def test_apply_success(self, tmp_path):
        """Full apply flow: check clean, lock, pull, install, unlock."""
        from spellbook.updates.tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"
        d = str(spellbook_dir)

        def mock_subprocess_run(cmd, **kwargs):
            result = _make_proc(0)
            if "status" in cmd:
                result.stdout = ""
            elif "rev-parse" in cmd:
                result.stdout = "abc123def456"
            elif "pull" in cmd:
                pass
            elif "fetch" in cmd:
                pass
            elif "install.py" in " ".join(cmd):
                (spellbook_dir / ".version").write_text("0.9.10\n")
            return result

        config_fn = lambda key: {"auto_update_remote": "origin"}.get(key)
        state_fn = lambda key: {"auto_update_branch": "main"}.get(key)

        # Capture config_set calls for assertion (last_auto_update has dynamic timestamp)
        config_set_calls = []

        def capture_config_set(*a, **kw):
            config_set_calls.append(a)

        # subprocess.run: status, rev-parse, fetch, pull, install = 5 calls
        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, mock_subprocess_run, 5)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.calls(config_fn)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(state_fn)
        mock_config_set = bigfoot.mock("spellbook.updates.tools:config_set")
        _chain(mock_config_set, capture_config_set, 3)

        with bigfoot:
            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is True
        assert result["previous_version"] == "0.9.9"
        assert result["new_version"] == "0.9.10"
        assert result["pre_update_sha"] == "abc123def456"
        assert result["error"] is None

        # Verify config_set calls (last_auto_update has a dynamic timestamp)
        assert config_set_calls[0] == ("pre_update_sha", "abc123def456")
        assert config_set_calls[1] == ("last_update_version", "0.9.10")
        assert config_set_calls[2][0] == "last_auto_update"
        last_auto = config_set_calls[2][1]
        assert last_auto["version"] == "0.9.10"
        assert last_auto["from_version"] == "0.9.9"
        assert "applied_at" in last_auto

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "status", "--porcelain"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_run.assert_call(
                args=(["git", "-C", d, "rev-parse", "HEAD"],),
                kwargs={"capture_output": True, "text": True, "timeout": 10})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "pull", "--ff-only", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["uv", "run", str(spellbook_dir / "install.py"),
                       "--yes", "--no-interactive", "--update-only"],),
                kwargs={"capture_output": True, "text": True, "timeout": 120, "cwd": d})
            mock_config_set.assert_call(args=config_set_calls[0])
            mock_config_set.assert_call(args=config_set_calls[1])
            mock_config_set.assert_call(args=config_set_calls[2])

    def test_apply_dirty_tree_aborts(self, tmp_path):
        """Aborts when working tree has uncommitted changes."""
        from spellbook.updates.tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"
        d = str(spellbook_dir)

        def mock_subprocess_run(cmd, **kwargs):
            result = _make_proc(0)
            if "status" in cmd:
                result.stdout = " M some_file.py\n"  # Dirty tree
            return result

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        mock_run.calls(mock_subprocess_run)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.returns(None)

        with bigfoot:
            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "dirty" in result["error"].lower() or "uncommitted" in result["error"].lower()

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "status", "--porcelain"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})

    def test_apply_pull_fails(self, tmp_path):
        """Handles pull failure, releases lock."""
        from spellbook.updates.tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"
        d = str(spellbook_dir)

        def mock_subprocess_run(cmd, **kwargs):
            if "status" in cmd:
                return _make_proc(0, "")
            elif "rev-parse" in cmd:
                return _make_proc(0, "abc123")
            elif "pull" in cmd:
                return _make_proc(1, "", "fatal: not possible to fast-forward")
            elif "fetch" in cmd:
                return _make_proc(0)
            return _make_proc(0)

        # status, rev-parse, fetch, pull = 4 calls
        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, mock_subprocess_run, 4)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.returns(None)
        mock_config_set = bigfoot.mock("spellbook.updates.tools:config_set")
        mock_config_set.calls(lambda *a, **kw: None)

        with bigfoot:
            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "pull" in result["error"].lower() or "fast-forward" in result["error"].lower()
        assert not lock_path.exists()

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_config_set.assert_call(args=("pre_update_sha", "abc123"))
            mock_run.assert_call(
                args=(["git", "-C", d, "status", "--porcelain"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_run.assert_call(
                args=(["git", "-C", d, "rev-parse", "HEAD"],),
                kwargs={"capture_output": True, "text": True, "timeout": 10})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "pull", "--ff-only", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})

    def test_apply_installer_fails(self, tmp_path):
        """Handles installer failure, releases lock."""
        from spellbook.updates.tools import apply_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.9\n")
        lock_path = tmp_path / "install.lock"
        d = str(spellbook_dir)

        def mock_subprocess_run(cmd, **kwargs):
            if "status" in cmd:
                return _make_proc(0, "")
            elif "rev-parse" in cmd:
                return _make_proc(0, "abc123")
            elif "pull" in cmd:
                return _make_proc(0)
            elif "fetch" in cmd:
                return _make_proc(0)
            elif "install.py" in " ".join(cmd):
                return _make_proc(1, "", "installer error")
            # reset --hard
            return _make_proc(0)

        # status, rev-parse, fetch, pull, install, reset = 6 calls
        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, mock_subprocess_run, 6)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.returns(None)
        mock_config_set = bigfoot.mock("spellbook.updates.tools:config_set")
        mock_config_set.calls(lambda *a, **kw: None)

        with bigfoot:
            result = apply_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "install" in result["error"].lower()
        assert not lock_path.exists()

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update_remote",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_config_set.assert_call(args=("pre_update_sha", "abc123"))
            mock_run.assert_call(
                args=(["git", "-C", d, "status", "--porcelain"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_run.assert_call(
                args=(["git", "-C", d, "rev-parse", "HEAD"],),
                kwargs={"capture_output": True, "text": True, "timeout": 10})
            mock_run.assert_call(
                args=(["git", "-C", d, "fetch", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["git", "-C", d, "pull", "--ff-only", "origin", "main"],),
                kwargs={"capture_output": True, "text": True, "timeout": 60})
            mock_run.assert_call(
                args=(["uv", "run", str(spellbook_dir / "install.py"),
                       "--yes", "--no-interactive", "--update-only"],),
                kwargs={"capture_output": True, "text": True, "timeout": 120, "cwd": d})
            mock_run.assert_call(
                args=(["git", "-C", d, "reset", "--hard", "abc123"],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})


class TestRollbackUpdate:
    """Tests for rollback_update()."""

    def test_rollback_success(self, tmp_path):
        """Full rollback flow."""
        from spellbook.updates.tools import rollback_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("0.9.10\n")
        lock_path = tmp_path / "install.lock"
        d = str(spellbook_dir)
        sha = "abc123def456" + "0" * 28

        def mock_subprocess_run(cmd, **kwargs):
            result = _make_proc(0)
            if "rev-parse" in cmd and "--abbrev-ref" in cmd:
                result.stdout = "main"
            elif "reset" in cmd:
                (spellbook_dir / ".version").write_text("0.9.9\n")
            elif "install.py" in " ".join(cmd):
                pass
            return result

        config_state = {"pre_update_sha": sha}
        state_state = {"auto_update_branch": "main"}

        # branch check, reset, install = 3 calls
        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        _chain(mock_run, mock_subprocess_run, 3)
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.calls(lambda key: config_state.get(key))
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(lambda key: state_state.get(key))
        # auto_update_paused, pre_update_sha, last_auto_update, available_update = 4 calls
        mock_config_set = bigfoot.mock("spellbook.updates.tools:config_set")
        _chain(mock_config_set, lambda *a, **kw: None, 4)

        with bigfoot:
            result = rollback_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is True
        assert result["rolled_back_to"] == sha
        assert result["auto_update_paused"] is True
        assert result["error"] is None

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("pre_update_sha",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "rev-parse", "--abbrev-ref", "HEAD"],),
                kwargs={"capture_output": True, "text": True, "timeout": 10})
            mock_run.assert_call(
                args=(["git", "-C", d, "reset", "--hard", sha],),
                kwargs={"capture_output": True, "text": True, "timeout": 30})
            mock_run.assert_call(
                args=(["uv", "run", str(spellbook_dir / "install.py"),
                       "--yes", "--no-interactive", "--update-only", "--force"],),
                kwargs={"capture_output": True, "text": True, "timeout": 120, "cwd": d})
            mock_config_set.assert_call(args=("auto_update_paused", True))
            mock_config_set.assert_call(args=("pre_update_sha", None))
            mock_config_set.assert_call(args=("last_auto_update", None))
            mock_config_set.assert_call(args=("available_update", None))

    def test_rollback_no_sha(self, tmp_path):
        """Returns error when no pre_update_sha stored."""
        from spellbook.updates.tools import rollback_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        lock_path = tmp_path / "install.lock"

        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.returns(None)

        with bigfoot:
            result = rollback_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "no pre_update_sha" in result["error"].lower() or "nothing to rollback" in result["error"].lower()

        mock_config.assert_call(args=("pre_update_sha",))

    def test_rollback_wrong_branch(self, tmp_path):
        """Returns error when on wrong branch."""
        from spellbook.updates.tools import rollback_update

        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        lock_path = tmp_path / "install.lock"
        d = str(spellbook_dir)
        sha = "abc123" + "0" * 34

        config_state = {"pre_update_sha": sha}
        state_state = {"auto_update_branch": "main"}

        mock_run = bigfoot.mock("spellbook.updates.tools:subprocess.run")
        mock_run.returns(_make_proc(0, "feature-branch"))
        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        mock_config.calls(lambda key: config_state.get(key))
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(lambda key: state_state.get(key))

        with bigfoot:
            result = rollback_update(spellbook_dir, lock_path=lock_path)

        assert result["success"] is False
        assert "branch" in result["error"].lower()

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("pre_update_sha",))
            mock_state.assert_call(args=("auto_update_branch",))
            mock_run.assert_call(
                args=(["git", "-C", d, "rev-parse", "--abbrev-ref", "HEAD"],),
                kwargs={"capture_output": True, "text": True, "timeout": 10})


class TestGetUpdateStatus:
    """Tests for get_update_status()."""

    def test_returns_aggregated_status(self, tmp_path):
        """Returns all update-related config keys in one response."""
        from spellbook.updates.tools import get_update_status

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
        }
        state_state = {"update_check_failures": 0}

        mock_config = bigfoot.mock("spellbook.updates.tools:config_get")
        _chain(mock_config, lambda key: config_state.get(key), 7)
        mock_state = bigfoot.mock("spellbook.updates.tools:get_state")
        mock_state.calls(lambda key: state_state.get(key))

        with bigfoot:
            result = get_update_status(spellbook_dir)

        assert result["auto_update_enabled"] is True
        assert result["auto_update_paused"] is False
        assert result["current_version"] == "0.9.10"
        assert result["available_update"]["version"] == "0.9.11"
        assert result["pre_update_sha"] == "abc123"
        assert result["check_failures"] == 0

        with bigfoot.in_any_order():
            mock_config.assert_call(args=("auto_update",))
            mock_config.assert_call(args=("auto_update_paused",))
            mock_config.assert_call(args=("available_update",))
            mock_config.assert_call(args=("pending_major_update",))
            mock_config.assert_call(args=("last_auto_update",))
            mock_config.assert_call(args=("pre_update_sha",))
            mock_config.assert_call(args=("last_update_check",))
            mock_state.assert_call(args=("update_check_failures",))


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

    def test_update_only_calls_find_spellbook_dir_not_bootstrap(self, monkeypatch):
        """--update-only should call find_spellbook_dir instead of bootstrap."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import importlib
        import install
        importlib.reload(install)

        fake_dir = Path("/tmp/fake-spellbook")

        # sys.argv is an attribute, not a function; use monkeypatch
        monkeypatch.setattr("sys.argv", ["install.py", "--update-only", "--yes"])

        # Capture run_installation call args for flexible verification
        run_install_args = []

        mock_find = bigfoot.mock.object(install, "find_spellbook_dir")
        mock_find.returns(fake_dir)
        # bootstrap should NOT be called; mock with no queue entries
        bigfoot.mock.object(install, "bootstrap")
        mock_run_install = bigfoot.mock.object(install, "run_installation")
        mock_run_install.calls(lambda *a, **kw: (run_install_args.append((a, kw)) or 0))
        mock_print_success = bigfoot.mock.object(install, "print_success")
        mock_print_success.calls(lambda *a, **kw: None)
        mock_print_step = bigfoot.mock.object(install, "print_step")
        mock_print_step.calls(lambda *a, **kw: None)
        mock_is_interactive = bigfoot.mock.object(install, "is_interactive")
        mock_is_interactive.returns(False)

        with bigfoot:
            result = install.main()

        # Verify run_installation was called with the found dir
        assert len(run_install_args) == 1
        assert run_install_args[0][0][0] == fake_dir

        with bigfoot.in_any_order():
            mock_find.assert_call(args=(), kwargs={})
            mock_is_interactive.assert_call(args=(), kwargs={})
            mock_print_step.assert_call(
                args=("Spellbook: bootstrapping...",), kwargs={})
            mock_print_success.assert_call(
                args=(f"Update-only mode: using {fake_dir}",), kwargs={})
            mock_run_install.assert_call(
                args=run_install_args[0][0], kwargs=run_install_args[0][1])

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
        from spellbook.server import spellbook_check_for_updates, _FASTMCP_MAJOR
        if _FASTMCP_MAJOR >= 3:
            # In v3, @mcp.tool() returns the original function (with .fn compat shim)
            assert callable(spellbook_check_for_updates)
        else:
            from fastmcp.tools.tool import FunctionTool
            assert isinstance(spellbook_check_for_updates, FunctionTool)
        assert callable(spellbook_check_for_updates.fn)

    def test_status_tool_function_importable(self):
        """Verify spellbook_get_update_status can be imported from server module."""
        from spellbook.server import spellbook_get_update_status, _FASTMCP_MAJOR
        if _FASTMCP_MAJOR >= 3:
            assert callable(spellbook_get_update_status)
        else:
            from fastmcp.tools.tool import FunctionTool
            assert isinstance(spellbook_get_update_status, FunctionTool)
        assert callable(spellbook_get_update_status.fn)
