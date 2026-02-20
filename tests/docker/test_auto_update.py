"""Tests for the auto-update system (check, apply, rollback, locking).

Exercises update_tools.py end-to-end using real git repos provided by the
``spellbook_repo`` and ``committed_repo`` fixtures. Tests cover:
- Update detection (no update, update available)
- Update application (success, rollback on installer failure)
- Rollback to previous version
- Lock file concurrency (multiprocessing, stale lock handling)
- SHA validation
- Config persistence after update checks
- Version bump classification
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import time
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from spellbook_mcp.update_tools import (
    LOCK_STALE_SECONDS,
    acquire_install_lock,
    apply_update,
    check_for_updates,
    classify_version_bump,
    release_install_lock,
    rollback_update,
)

# Capture the real subprocess.run at import time, before any patching.
_real_subprocess_run = subprocess.run


def _get_head_sha(repo_dir: Path) -> str:
    """Return the full HEAD SHA for a git repo.

    Args:
        repo_dir: Path to the git working directory.

    Returns:
        40-character hex SHA string.
    """
    result = _real_subprocess_run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _get_latest_sha(repo_dir: Path) -> str:
    """Return the SHA at the tip of origin/main for a git repo.

    Args:
        repo_dir: Path to the git working directory.

    Returns:
        40-character hex SHA string.
    """
    _real_subprocess_run(
        ["git", "-C", str(repo_dir), "fetch", "origin"],
        capture_output=True,
        check=True,
    )
    result = _real_subprocess_run(
        ["git", "-C", str(repo_dir), "rev-parse", "origin/main"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _make_installer_interceptor(
    *, installer_returncode: int = 0, installer_stderr: str = ""
):
    """Create a subprocess.run interceptor that fakes the installer step.

    All git commands pass through to real subprocess.run. Only the
    ``uv run install.py ...`` invocation is intercepted and returns a
    ``CompletedProcess`` with the given return code and stderr.

    Args:
        installer_returncode: Return code for the faked installer.
        installer_stderr: Stderr text for the faked installer.

    Returns:
        A callable suitable for use as ``side_effect`` on a patched
        ``subprocess.run``.
    """

    def _intercept(*args, **kwargs):  # type: ignore[no-untyped-def]
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, list) and "install.py" in " ".join(cmd):
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=installer_returncode,
                stdout="",
                stderr=installer_stderr,
            )
        return _real_subprocess_run(*args, **kwargs)

    return _intercept


@pytest.fixture()
def config_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create an isolated config directory and patch HOME so config_tools uses it.

    The spellbook config path is derived from ``Path.home() / ".config" / "spellbook"``.
    By overriding HOME we redirect all config reads and writes to a temp directory.

    Yields:
        Path to the isolated config directory (``$HOME/.config/spellbook``).
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    cfg = fake_home / ".config" / "spellbook"
    cfg.mkdir(parents=True)

    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(fake_home)
    try:
        yield cfg
    finally:
        if original_home is not None:
            os.environ["HOME"] = original_home
        else:
            os.environ.pop("HOME", None)


@pytest.fixture()
def lock_file(tmp_path: Path) -> Path:
    """Provide a path for a temporary lock file.

    Returns:
        Path suitable for use as a lock file (does not pre-exist).
    """
    return tmp_path / "test-install.lock"


class TestCheckForUpdates:
    """Tests for check_for_updates()."""

    def test_no_update_when_at_latest(
        self, spellbook_repo: Path, tmp_path: Path, config_dir: Path
    ) -> None:
        """When local repo is at the same commit as remote, no update is reported."""
        # Clone the bare repo and stay at HEAD (which includes the version bump)
        work_dir = tmp_path / "up-to-date"
        _real_subprocess_run(
            ["git", "clone", str(spellbook_repo), str(work_dir)],
            capture_output=True,
            check=True,
        )

        result = check_for_updates(work_dir)

        assert result["error"] is None, f"Unexpected error: {result['error']}"
        assert result["update_available"] is False
        assert result["current_version"] == result["remote_version"]

    def test_update_available_when_behind(
        self, committed_repo: Path, config_dir: Path
    ) -> None:
        """When remote has newer commits, check_for_updates detects the update."""
        result = check_for_updates(committed_repo)

        assert result["error"] is None, f"Unexpected error: {result['error']}"
        assert result["update_available"] is True
        assert result["current_version"] is not None
        assert result["remote_version"] is not None
        assert result["current_version"] != result["remote_version"]


class TestApplyUpdate:
    """Tests for apply_update()."""

    def test_apply_update_success(
        self, committed_repo: Path, config_dir: Path, lock_file: Path
    ) -> None:
        """Applying an update pulls new commits and advances HEAD to the latest SHA."""
        sha_before = _get_head_sha(committed_repo)
        latest_sha = _get_latest_sha(committed_repo)

        with patch(
            "spellbook_mcp.update_tools.subprocess.run",
            side_effect=_make_installer_interceptor(installer_returncode=0),
        ):
            result = apply_update(committed_repo, lock_path=lock_file)

        assert result["success"] is True, f"Update failed: {result['error']}"
        assert result["pre_update_sha"] == sha_before
        assert result["error"] is None

        sha_after = _get_head_sha(committed_repo)
        assert sha_after == latest_sha
        assert sha_after != sha_before

    def test_apply_update_rollback_on_installer_failure(
        self, committed_repo: Path, config_dir: Path, lock_file: Path
    ) -> None:
        """When the installer step fails, git is reset to the pre-update SHA."""
        sha_before = _get_head_sha(committed_repo)

        with patch(
            "spellbook_mcp.update_tools.subprocess.run",
            side_effect=_make_installer_interceptor(
                installer_returncode=1, installer_stderr="Installer crashed"
            ),
        ):
            result = apply_update(committed_repo, lock_path=lock_file)

        assert result["success"] is False
        assert result["error"] is not None
        assert "Rolled back" in result["error"]

        sha_after = _get_head_sha(committed_repo)
        assert sha_after == sha_before


class TestRollbackUpdate:
    """Tests for rollback_update()."""

    def test_rollback_restores_previous_sha(
        self, committed_repo: Path, config_dir: Path, lock_file: Path
    ) -> None:
        """After a successful update, rollback restores the previous SHA."""
        sha_before = _get_head_sha(committed_repo)

        interceptor = _make_installer_interceptor(installer_returncode=0)

        # Apply update first (with mocked installer)
        with patch(
            "spellbook_mcp.update_tools.subprocess.run",
            side_effect=interceptor,
        ):
            apply_result = apply_update(committed_repo, lock_path=lock_file)

        assert apply_result["success"] is True, f"Setup failed: {apply_result['error']}"
        sha_after_update = _get_head_sha(committed_repo)
        assert sha_after_update != sha_before

        # Now rollback (also with mocked installer)
        with patch(
            "spellbook_mcp.update_tools.subprocess.run",
            side_effect=interceptor,
        ):
            rollback_result = rollback_update(committed_repo, lock_path=lock_file)

        assert rollback_result["success"] is True, (
            f"Rollback failed: {rollback_result['error']}"
        )
        assert rollback_result["rolled_back_to"] == sha_before
        assert rollback_result["auto_update_paused"] is True

        sha_after_rollback = _get_head_sha(committed_repo)
        assert sha_after_rollback == sha_before


def _hold_lock_in_child(
    lock_path_str: str,
    ready_event: multiprocessing.synchronize.Event,
    stop_event: multiprocessing.synchronize.Event,
) -> None:
    """Child process target: acquire the lock, signal readiness, wait for stop.

    Must be at module level so it is picklable by the "spawn" start method
    used by default on macOS.

    Args:
        lock_path_str: String path to the lock file.
        ready_event: Set once the lock is acquired.
        stop_event: Wait on this before releasing the lock.
    """
    lock_path = Path(lock_path_str)
    fd = acquire_install_lock(lock_path)
    if fd is None:
        return  # Could not acquire; test will detect this
    ready_event.set()
    stop_event.wait(timeout=30)
    release_install_lock(fd, lock_path)


class TestLockFile:
    """Tests for install lock file concurrency."""

    @pytest.mark.integration
    def test_lock_prevents_concurrent_acquisition(self, lock_file: Path) -> None:
        """When one process holds the lock, another is rejected (via multiprocessing)."""
        ready = multiprocessing.Event()
        stop = multiprocessing.Event()
        child = multiprocessing.Process(
            target=_hold_lock_in_child,
            args=(str(lock_file), ready, stop),
        )
        started = False
        try:
            child.start()
            started = True
            # Wait for the child to acquire the lock
            assert ready.wait(timeout=10), "Child process did not acquire lock in time"

            # Parent attempts to acquire the same lock -- should fail
            fd = acquire_install_lock(lock_file)
            assert fd is None, (
                "Expected lock acquisition to fail while held by another process"
            )
        finally:
            stop.set()
            if started:
                child.join(timeout=10)
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=5)

    def test_stale_lock_is_broken(self, lock_file: Path) -> None:
        """A lock file with an old timestamp is treated as stale and broken."""
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        # First acquire and release a real lock so the file exists
        fd = acquire_install_lock(lock_file)
        assert fd is not None, "Could not acquire initial lock"
        release_install_lock(fd, lock_file)

        # Now manually create a lock file with stale metadata and a dead PID.
        # The OS-level flock is not held by any process, so the flock() call
        # will succeed.  The stale-PID check is the code path we exercise here.
        stale_data = json.dumps({
            "pid": 999999999,  # Almost certainly not a running PID
            "timestamp": time.time() - LOCK_STALE_SECONDS - 100,
        })
        lock_file.write_text(stale_data)

        fd2 = acquire_install_lock(lock_file)
        try:
            assert fd2 is not None, (
                "Expected stale lock to be broken, but acquisition failed"
            )
        finally:
            if fd2 is not None:
                release_install_lock(fd2, lock_file)


class TestSHAValidation:
    """Tests for SHA format validation in rollback_update()."""

    def test_invalid_sha_rejected(
        self, committed_repo: Path, config_dir: Path, lock_file: Path
    ) -> None:
        """Passing an invalid SHA (not 40 hex chars) to rollback is rejected."""
        from spellbook_mcp.config_tools import config_set

        # Store an invalid SHA in config
        config_set("pre_update_sha", "not-a-valid-sha")

        result = rollback_update(committed_repo, lock_path=lock_file)

        assert result["success"] is False
        assert result["error"] is not None
        assert "invalid" in result["error"].lower()

    def test_short_sha_rejected(
        self, committed_repo: Path, config_dir: Path, lock_file: Path
    ) -> None:
        """A SHA shorter than 40 characters is rejected."""
        from spellbook_mcp.config_tools import config_set

        # Store a short (7-char abbreviated) SHA
        config_set("pre_update_sha", "abc1234")

        result = rollback_update(committed_repo, lock_path=lock_file)

        assert result["success"] is False
        assert result["error"] is not None
        assert "invalid" in result["error"].lower()


class TestUpdateConfigPersistence:
    """Tests for config persistence after update operations."""

    def test_check_for_updates_populates_versions(
        self, committed_repo: Path, config_dir: Path
    ) -> None:
        """After check_for_updates finds an update, version info is returned."""
        result = check_for_updates(committed_repo)

        assert result["error"] is None, f"Unexpected error: {result['error']}"
        assert result["update_available"] is True
        assert result["current_version"] is not None
        assert result["remote_version"] is not None
        # The remote version should be a patch bump of the current
        current_parts = result["current_version"].split(".")
        remote_parts = result["remote_version"].split(".")
        assert int(remote_parts[-1]) == int(current_parts[-1]) + 1

    def test_apply_update_persists_state_to_config(
        self, committed_repo: Path, config_dir: Path, lock_file: Path
    ) -> None:
        """After a successful apply_update, update state is persisted in config."""
        from spellbook_mcp.config_tools import config_get

        with patch(
            "spellbook_mcp.update_tools.subprocess.run",
            side_effect=_make_installer_interceptor(installer_returncode=0),
        ):
            result = apply_update(committed_repo, lock_path=lock_file)

        assert result["success"] is True, f"Update failed: {result['error']}"

        # Verify config was written
        stored_sha = config_get("pre_update_sha")
        assert stored_sha is not None
        assert len(stored_sha) == 40

        last_update = config_get("last_auto_update")
        assert last_update is not None
        assert "version" in last_update
        assert "applied_at" in last_update
        assert "from_version" in last_update


class TestVersionBumpClassification:
    """Tests for classify_version_bump()."""

    def test_patch_bump(self) -> None:
        """Patch bump: only the third component increases."""
        assert classify_version_bump("0.9.10", "0.9.11") == "patch"

    def test_minor_bump(self) -> None:
        """Minor bump: second component increases, first unchanged."""
        assert classify_version_bump("0.9.10", "0.10.0") == "minor"
        assert classify_version_bump("0.9.99", "0.10.0") == "minor"

    def test_major_bump(self) -> None:
        """Major bump: first component increases."""
        assert classify_version_bump("0.9.10", "1.0.0") == "major"
        assert classify_version_bump("0.99.99", "1.0.0") == "major"

    def test_same_version_returns_none(self) -> None:
        """Same version returns None (no upgrade needed)."""
        assert classify_version_bump("1.0.0", "1.0.0") is None

    def test_downgrade_returns_none(self) -> None:
        """Downgrade (available < installed) returns None."""
        assert classify_version_bump("1.0.0", "0.9.0") is None
        assert classify_version_bump("0.10.0", "0.9.99") is None

    def test_two_component_version(self) -> None:
        """Versions with only two components are padded to three."""
        assert classify_version_bump("1.0", "1.1") == "minor"
        assert classify_version_bump("1.0", "2.0") == "major"

    def test_invalid_version_returns_none(self) -> None:
        """Non-numeric version strings return None."""
        assert classify_version_bump("abc", "1.0.0") is None
        assert classify_version_bump("1.0.0", "xyz") is None
