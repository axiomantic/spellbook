"""Auto-update detection and application tools for spellbook.

This module provides:
- Version comparison and classification (major/minor/patch)
- On-demand update checking via git fetch
- Update application via subprocess (git pull + install.py)
- Rollback to previous version via stored SHA
- Install lock file management via fcntl.flock()
- Update status aggregation from config

Architecture: Detection is read-only (git fetch + git show). Application
runs as a subprocess to avoid self-modifying code. spellbook_mcp/ never
imports from installer/; the only interaction is shelling out to install.py.
"""

import fcntl
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from spellbook_mcp.config_tools import config_get, config_set

logger = logging.getLogger(__name__)


def classify_version_bump(installed: str, available: str) -> Optional[str]:
    """Classify the version bump between installed and available versions.

    Compares the first three components of semantic version strings.

    Args:
        installed: Current installed version (e.g., "0.9.9")
        available: Available remote version (e.g., "1.0.0")

    Returns:
        "major" if the first component increased,
        "minor" if the second component increased (first unchanged),
        "patch" if only the third component increased,
        None if no upgrade is needed (same version or downgrade).
    """
    def parse(v: str) -> Optional[tuple[int, ...]]:
        try:
            parts = tuple(int(x) for x in v.strip().split(".")[:3])
        except ValueError:
            return None
        # Pad to 3 components
        return (parts + (0, 0, 0))[:3]

    inst = parse(installed)
    avail = parse(available)

    if inst is None or avail is None:
        return None

    if avail <= inst:
        return None

    if avail[0] > inst[0]:
        return "major"
    elif avail[1] > inst[1]:
        return "minor"
    else:
        return "patch"


# Lock file constants
LOCK_STALE_SECONDS = 3600  # 1 hour


def _pid_exists(pid: int) -> bool:
    """Check if a process with given PID exists.

    Args:
        pid: Process ID to check

    Returns:
        True if the process exists, False otherwise
    """
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_install_lock(lock_path: Path) -> Optional[int]:
    """Acquire exclusive install lock. Returns fd on success, None if held.

    Uses fcntl.flock() for cross-process synchronization. If the lock is
    already held by another live process, returns None immediately (non-blocking).
    If the lock file has a dead PID or is older than LOCK_STALE_SECONDS, the
    lock is considered stale and will be broken.

    Args:
        lock_path: Path to the lock file

    Returns:
        File descriptor on success, None if lock is held by active process
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Lock is held. Check if stale.
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            content = os.read(fd, 1024).decode()
            lock_info = json.loads(content)
            pid = lock_info.get("pid")
            timestamp = lock_info.get("timestamp", 0)

            if pid and not _pid_exists(pid):
                # Stale lock (dead PID), break it
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(fd)
                    return None
            elif time.time() - timestamp > LOCK_STALE_SECONDS:
                # Stale lock (too old), break it
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    os.close(fd)
                    return None
            else:
                # Lock is held by a live process
                os.close(fd)
                return None
        except (json.JSONDecodeError, OSError):
            os.close(fd)
            return None

    # Write our lock info
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    lock_data = json.dumps({"pid": os.getpid(), "timestamp": time.time()})
    os.write(fd, lock_data.encode())
    return fd


def release_install_lock(fd: int, lock_path: Path) -> None:
    """Release install lock and clean up lock file.

    Args:
        fd: File descriptor from acquire_install_lock()
        lock_path: Path to the lock file
    """
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
    try:
        lock_path.unlink()
    except OSError:
        pass


def get_changelog_between(
    spellbook_dir: Path, from_version: str, to_version: str
) -> str:
    """Extract changelog entries between two version headers.

    Parses CHANGELOG.md for entries between from_version (exclusive) and
    to_version (inclusive). Uses regex matching on ``## [X.Y.Z]`` patterns.

    Args:
        spellbook_dir: Path to spellbook directory containing CHANGELOG.md
        from_version: Starting version (exclusive, entries after this)
        to_version: Ending version (inclusive, entries up to and including)

    Returns:
        Extracted changelog text, or empty string if not found or same version
    """
    if from_version == to_version:
        return ""

    changelog_path = spellbook_dir / "CHANGELOG.md"
    if not changelog_path.exists():
        return ""

    try:
        content = changelog_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    # Find all version headers and their positions
    version_pattern = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)
    matches = list(version_pattern.finditer(content))

    if not matches:
        return ""

    # Find indices of from_version and to_version
    to_idx = None
    from_idx = None

    for i, m in enumerate(matches):
        if m.group(1) == to_version:
            to_idx = i
        if m.group(1) == from_version:
            from_idx = i

    if to_idx is None:
        return ""

    # Extract content from to_version header to from_version header (exclusive)
    start_pos = matches[to_idx].start()

    if from_idx is not None:
        end_pos = matches[from_idx].start()
    else:
        # from_version not found in changelog; return only the to_version entry
        if to_idx + 1 < len(matches):
            end_pos = matches[to_idx + 1].start()
        else:
            end_pos = len(content)

    # Only include entries between to and from (to is newer, from is older)
    # Changelog is newest-first, so to_idx < from_idx
    if from_idx is not None and to_idx >= from_idx:
        return ""  # to_version is not newer than from_version

    result = content[start_pos:end_pos].strip()
    return result


def check_for_updates(spellbook_dir: Path) -> dict:
    """Perform an on-demand update check via git fetch.

    Fetches the configured remote/branch, reads the remote .version file
    via ``git show``, and compares it to the local .version file. Does NOT
    modify the working tree.

    Args:
        spellbook_dir: Path to the spellbook git repository

    Returns:
        Dict with keys: update_available, current_version, remote_version,
        is_major_bump, changelog, error
    """
    result = {
        "update_available": False,
        "current_version": None,
        "remote_version": None,
        "is_major_bump": False,
        "changelog": None,
        "error": None,
    }

    # Read local version
    version_path = spellbook_dir / ".version"
    try:
        local_version = version_path.read_text().strip()
        result["current_version"] = local_version
    except (FileNotFoundError, OSError) as e:
        result["error"] = f"Could not read local .version file: {e}"
        return result

    # Determine remote and branch
    remote = config_get("auto_update_remote") or "origin"
    branch = config_get("auto_update_branch") or "main"

    # Validate remote exists
    try:
        remote_proc = subprocess.run(
            ["git", "-C", str(spellbook_dir), "remote"],
            capture_output=True, text=True, timeout=5
        )
        known_remotes = remote_proc.stdout.strip().split('\n') if remote_proc.stdout.strip() else []
        if remote not in known_remotes:
            result["error"] = f"Unknown git remote: {remote}"
            return result
    except subprocess.SubprocessError:
        pass  # If we can't list remotes, proceed anyway

    # Git fetch
    try:
        fetch_proc = subprocess.run(
            ["git", "-C", str(spellbook_dir), "fetch", remote, branch],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if fetch_proc.returncode != 0:
            result["error"] = f"git fetch failed: {fetch_proc.stderr.strip()}"
            return result
    except subprocess.TimeoutExpired:
        result["error"] = "git fetch timed out (60s)"
        return result
    except OSError as e:
        result["error"] = f"git fetch error: {e}"
        return result

    # Read remote version
    try:
        show_proc = subprocess.run(
            ["git", "-C", str(spellbook_dir), "show",
             f"{remote}/{branch}:.version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if show_proc.returncode != 0:
            result["error"] = f"Could not read remote .version: {show_proc.stderr.strip()}"
            return result
        remote_version = show_proc.stdout.strip()
        result["remote_version"] = remote_version
    except subprocess.TimeoutExpired:
        result["error"] = "git show timed out (30s)"
        return result
    except OSError as e:
        result["error"] = f"git show error: {e}"
        return result

    # Compare versions
    bump_type = classify_version_bump(local_version, remote_version)
    if bump_type is not None:
        result["update_available"] = True
        result["is_major_bump"] = bump_type == "major"

        # Try to get changelog
        try:
            changelog = get_changelog_between(spellbook_dir, local_version, remote_version)
            if changelog:
                result["changelog"] = changelog
        except Exception:
            pass  # Changelog is optional

    return result


# Default lock file path. This is the canonical lock location for all
# install/update operations. apply_update() and rollback_update() default
# to this path. ~/.config/spellbook/install.lock is the production lock path.
DEFAULT_LOCK_PATH = Path.home() / ".config" / "spellbook" / "install.lock"


def apply_update(
    spellbook_dir: Path,
    target_version: Optional[str] = None,
    lock_path: Optional[Path] = None,  # lock_path is for testing; production callers use DEFAULT_LOCK_PATH
) -> dict:
    """Apply a spellbook update as a subprocess.

    Performs pre-flight checks (clean working tree, lock acquisition), then
    runs ``git pull --ff-only`` followed by ``uv run install.py --yes
    --no-interactive --update-only``. Records pre-update SHA for rollback.

    Args:
        spellbook_dir: Path to the spellbook git repository
        target_version: Target version (unused, for future pinned updates)
        lock_path: Path to lock file (default: ~/.config/spellbook/install.lock)

    Returns:
        Dict with keys: success, previous_version, new_version,
        pre_update_sha, error
    """
    if lock_path is None:
        lock_path = DEFAULT_LOCK_PATH

    result = {
        "success": False,
        "previous_version": None,
        "new_version": None,
        "pre_update_sha": None,
        "error": None,
    }

    # Read current version
    try:
        result["previous_version"] = (spellbook_dir / ".version").read_text().strip()
    except (FileNotFoundError, OSError) as e:
        result["error"] = f"Could not read .version: {e}"
        return result

    remote = config_get("auto_update_remote") or "origin"
    branch = config_get("auto_update_branch") or "main"

    # Pre-flight: check clean working tree
    try:
        status_proc = subprocess.run(
            ["git", "-C", str(spellbook_dir), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if status_proc.returncode != 0 or status_proc.stdout.strip():
            result["error"] = (
                "Working tree has uncommitted changes. "
                "Please commit or stash changes before updating."
            )
            return result
    except (subprocess.TimeoutExpired, OSError) as e:
        result["error"] = f"git status check failed: {e}"
        return result

    # Record pre-update SHA
    try:
        sha_proc = subprocess.run(
            ["git", "-C", str(spellbook_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if sha_proc.returncode == 0:
            result["pre_update_sha"] = sha_proc.stdout.strip()
            config_set("pre_update_sha", result["pre_update_sha"])
    except (subprocess.TimeoutExpired, OSError):
        pass  # Non-fatal; rollback just won't be available

    # Acquire lock
    fd = acquire_install_lock(lock_path)
    if fd is None:
        result["error"] = "Update already in progress (lock held by another process)"
        return result

    try:
        # Fetch remote refs before pull
        try:
            fetch_proc = subprocess.run(
                ["git", "-C", str(spellbook_dir), "fetch", remote, branch],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if fetch_proc.returncode != 0:
                result["error"] = f"git fetch failed: {fetch_proc.stderr.strip()}"
                return result
        except subprocess.TimeoutExpired:
            result["error"] = "git fetch timed out (60s)"
            return result
        except OSError as e:
            result["error"] = f"git fetch error: {e}"
            return result

        # Git pull --ff-only
        try:
            pull_proc = subprocess.run(
                ["git", "-C", str(spellbook_dir), "pull", "--ff-only",
                 remote, branch],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if pull_proc.returncode != 0:
                result["error"] = f"git pull --ff-only failed: {pull_proc.stderr.strip()}"
                return result
        except subprocess.TimeoutExpired:
            result["error"] = "git pull timed out (60s)"
            return result
        except OSError as e:
            result["error"] = f"git pull error: {e}"
            return result

        # Run installer
        install_script = spellbook_dir / "install.py"
        installer_error = None
        try:
            install_proc = subprocess.run(
                ["uv", "run", str(install_script),
                 "--yes", "--no-interactive", "--update-only"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(spellbook_dir),
            )
            if install_proc.returncode != 0:
                installer_error = f"Installer failed: {install_proc.stderr.strip()}"
        except subprocess.TimeoutExpired:
            installer_error = "Installer timed out (120s)"
        except OSError as e:
            installer_error = f"Installer error: {e}"

        if installer_error and result["pre_update_sha"]:
            try:
                subprocess.run(
                    ["git", "-C", str(spellbook_dir), "reset", "--hard",
                     result["pre_update_sha"]],
                    capture_output=True, text=True, timeout=30,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass
            result["error"] = (
                f"{installer_error}. Rolled back git tree to {result['pre_update_sha']}."
            )
            return result
        elif installer_error:
            result["error"] = installer_error
            return result

        # Post-flight: read new version
        try:
            result["new_version"] = (spellbook_dir / ".version").read_text().strip()
        except (FileNotFoundError, OSError):
            result["new_version"] = result["previous_version"]

        # Store state in config
        config_set("last_update_version", result["new_version"])
        # Set last_auto_update so session greeting notification fires
        # (covers both the watcher path and the MCP tool path)
        config_set("last_auto_update", {
            "version": result["new_version"],
            "applied_at": datetime.now().isoformat(),
            "from_version": result["previous_version"],
        })

        result["success"] = True
        return result

    finally:
        release_install_lock(fd, lock_path)


def rollback_update(
    spellbook_dir: Path,
    lock_path: Optional[Path] = None,  # lock_path is for testing; production callers use DEFAULT_LOCK_PATH
) -> dict:
    """Rollback to the previous version using stored pre-update SHA.

    Uses ``git reset --hard <sha>`` to revert (stays on branch, no detached
    HEAD). Re-runs the installer to restore correct state. Pauses auto-update
    to prevent re-applying the broken version.

    Args:
        spellbook_dir: Path to the spellbook git repository
        lock_path: Path to lock file (default: ~/.config/spellbook/install.lock)

    Returns:
        Dict with keys: success, rolled_back_to, version_after_rollback,
        auto_update_paused, error
    """
    if lock_path is None:
        lock_path = DEFAULT_LOCK_PATH

    result = {
        "success": False,
        "rolled_back_to": None,
        "version_after_rollback": None,
        "auto_update_paused": False,
        "error": None,
    }

    # Get stored SHA
    pre_update_sha = config_get("pre_update_sha")
    if not pre_update_sha:
        result["error"] = "No pre_update_sha stored. Nothing to rollback."
        return result

    if not re.match(r"^[0-9a-f]{40}$", pre_update_sha):
        result["error"] = f"Invalid pre_update_sha format: {pre_update_sha!r}"
        return result

    # Get expected branch
    expected_branch = config_get("auto_update_branch") or "main"

    # Verify current branch matches expected
    try:
        branch_proc = subprocess.run(
            ["git", "-C", str(spellbook_dir), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        current_branch = branch_proc.stdout.strip()
        if current_branch != expected_branch:
            result["error"] = (
                f"Current branch '{current_branch}' does not match "
                f"expected branch '{expected_branch}'. Aborting rollback."
            )
            return result
    except (subprocess.TimeoutExpired, OSError) as e:
        result["error"] = f"Could not verify branch: {e}"
        return result

    # Acquire lock
    fd = acquire_install_lock(lock_path)
    if fd is None:
        result["error"] = "Lock held by another process"
        return result

    try:
        # Git reset --hard <sha>
        try:
            reset_proc = subprocess.run(
                ["git", "-C", str(spellbook_dir), "reset", "--hard", pre_update_sha],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if reset_proc.returncode != 0:
                result["error"] = f"git reset failed: {reset_proc.stderr.strip()}"
                return result
        except (subprocess.TimeoutExpired, OSError) as e:
            result["error"] = f"git reset error: {e}"
            return result

        # Re-run installer
        install_script = spellbook_dir / "install.py"
        try:
            install_proc = subprocess.run(
                ["uv", "run", str(install_script),
                 "--yes", "--no-interactive", "--update-only", "--force"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(spellbook_dir),
            )
            if install_proc.returncode != 0:
                logger.warning(f"Installer failed during rollback: {install_proc.stderr}")
                # Continue anyway; the git reset was the critical part
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"Installer error during rollback: {e}")

        # Read version after rollback
        try:
            result["version_after_rollback"] = (
                spellbook_dir / ".version"
            ).read_text().strip()
        except (FileNotFoundError, OSError):
            pass

        # Pause auto-update
        config_set("auto_update_paused", True)

        # Clear update state
        config_set("pre_update_sha", None)
        config_set("last_auto_update", None)
        config_set("available_update", None)

        result["success"] = True
        result["rolled_back_to"] = pre_update_sha
        result["auto_update_paused"] = True
        return result

    finally:
        release_install_lock(fd, lock_path)


def get_update_status(spellbook_dir: Path) -> dict:
    """Return the current update state aggregated from config.

    Provides a single snapshot of all update-related config keys. Used by
    agents to get a summary without triggering a new check.

    Args:
        spellbook_dir: Path to the spellbook git repository

    Returns:
        Dict with keys: auto_update_enabled, auto_update_paused,
        current_version, available_update, pending_major_update,
        last_auto_update, pre_update_sha, last_check, check_failures
    """
    # Read current version
    try:
        current_version = (spellbook_dir / ".version").read_text().strip()
    except (FileNotFoundError, OSError):
        current_version = "unknown"

    return {
        "auto_update_enabled": bool(config_get("auto_update")),
        "auto_update_paused": bool(config_get("auto_update_paused")),
        "current_version": current_version,
        "available_update": config_get("available_update"),
        "pending_major_update": config_get("pending_major_update"),
        "last_auto_update": config_get("last_auto_update"),
        "pre_update_sha": config_get("pre_update_sha"),
        "last_check": config_get("last_update_check"),
        "check_failures": config_get("update_check_failures") or 0,
    }
