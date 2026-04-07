"""Cross-platform compatibility layer for spellbook.

All OS-specific logic converges into this single module. Callers ask for
capabilities ("create a link", "acquire a lock", "get config directory")
and this module handles the OS-specific implementation.

No external dependencies beyond the Python standard library.
"""

import errno
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection (canonical source: spellbook.core.services)
# ---------------------------------------------------------------------------

from spellbook.core.services import (
    LockHeldError,
    Platform,
    UnsupportedPlatformError,
    get_platform,
)


# ---------------------------------------------------------------------------
# Link creation results
# ---------------------------------------------------------------------------


@dataclass
class LinkResult:
    """Result of a link creation operation."""

    source: Path
    target: Path
    success: bool
    action: str  # "created", "updated", "failed"
    link_mode: str  # "symlink", "junction", "copy", "none"
    message: str


def _create_junction(source: Path, target: Path) -> bool:
    """Create a Windows NTFS junction.

    Args:
        source: The directory the junction points TO (the actual content).
        target: WHERE the junction is created (the link location).

    Note: Parameter order matches create_link() convention.
        _winapi.CreateJunction(src_path, dst_path) where src_path is the
        target directory the junction points to, and dst_path is where the
        junction is created.

    Tries _winapi.CreateJunction first, falls back to mklink /J.
    Always returns False on non-Windows platforms.
    """
    if sys.platform != "win32":
        return False
    try:
        import _winapi

        _winapi.CreateJunction(str(source), str(target))
        return True
    except (OSError, AttributeError):
        try:
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def _is_dir_empty(path: Path) -> bool:
    """Check if a directory is empty."""
    try:
        return not any(path.iterdir())
    except (OSError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Link inspection and removal
# ---------------------------------------------------------------------------


def is_junction(path: Path) -> bool:
    """Check if path is a Windows junction point.

    Returns False on non-Windows platforms. On Windows, uses
    GetFileAttributesW to check the reparse point attribute.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == -1:
            return False
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT) and not path.is_symlink()
    except (OSError, AttributeError):
        return False


def remove_link(target: Path) -> bool:
    """Remove a symlink, junction, or copied directory/file.

    Handles all link types created by create_link():
    - Symlinks: unlink()
    - Junctions: os.rmdir() (junctions are removed with rmdir)
    - Copied dirs: shutil.rmtree()
    - Copied files: unlink()

    Returns:
        True if removed, False if target did not exist or removal failed.
    """
    try:
        if target.is_symlink():
            target.unlink()
            return True
        elif is_junction(target):
            os.rmdir(str(target))
            return True
        elif target.is_dir():
            shutil.rmtree(str(target))
            return True
        elif target.is_file():
            target.unlink()
            return True
        return False
    except OSError:
        return False


def normalize_path_for_comparison(path: Path) -> str:
    """Normalize a path for cross-platform string comparison.

    On Windows: case-folded, forward slashes.
    On Unix: resolved path as-is.

    Args:
        path: Path to normalize.

    Returns:
        Normalized path string suitable for comparison.
    """
    result = str(path.resolve())
    if get_platform() == Platform.WINDOWS:
        return result.casefold().replace("\\", "/")
    return result


# ---------------------------------------------------------------------------
# Cross-platform link creation
# ---------------------------------------------------------------------------


def create_link(
    source: Path,
    target: Path,
    dry_run: bool = False,
    remove_empty_dirs: bool = False,
) -> LinkResult:
    """Create a link from target pointing to source.

    On macOS/Linux: always uses os.symlink().
    On Windows: tries symlink -> junction (dirs only) -> copy.

    Args:
        source: The actual file/directory to link to.
        target: Where the link will be created.
        dry_run: If True, don't actually create the link.
        remove_empty_dirs: If True, remove empty directories blocking link creation.

    Returns:
        LinkResult with status, link_mode, and message.
    """
    if not source.exists():
        return LinkResult(
            source=source,
            target=target,
            success=False,
            action="failed",
            link_mode="none",
            message=f"Source does not exist: {source}",
        )

    if dry_run:
        action = "updated" if (target.exists() or target.is_symlink()) else "created"
        return LinkResult(
            source=source,
            target=target,
            success=True,
            action=action,
            link_mode="symlink",
            message=f"Would {action} link: {target.name}",
        )

    try:
        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing (file, dir, or symlink)
        action = "created"
        if target.is_symlink() or is_junction(target) or target.exists():
            if target.is_dir() and not target.is_symlink() and not is_junction(target):
                if remove_empty_dirs and _is_dir_empty(target):
                    target.rmdir()
                    action = "updated"
                else:
                    return LinkResult(
                        source=source,
                        target=target,
                        success=False,
                        action="failed",
                        link_mode="none",
                        message=f"Target is a non-empty directory: {target}. Remove it manually.",
                    )
            else:
                remove_link(target)
                action = "updated"

        # Attempt symlink first (all platforms)
        try:
            target.symlink_to(source)
            return LinkResult(
                source=source,
                target=target,
                success=True,
                action=action,
                link_mode="symlink",
                message=f"{action.capitalize()} symlink: {target.name}",
            )
        except OSError as e:
            if get_platform() != Platform.WINDOWS:
                raise  # On Unix, symlink failure is fatal
            if e.errno not in (errno.EPERM, errno.EACCES) and getattr(e, 'winerror', None) != 1314:
                raise

        # Windows fallback: junction (directories only)
        if source.is_dir() and _create_junction(source, target):
            return LinkResult(
                source=source,
                target=target,
                success=True,
                action=action,
                link_mode="junction",
                message=f"{action.capitalize()} junction: {target.name}",
            )

        # Windows fallback: copy
        if source.is_dir():
            shutil.copytree(str(source), str(target), dirs_exist_ok=True)
        else:
            shutil.copy2(str(source), str(target))
        return LinkResult(
            source=source,
            target=target,
            success=True,
            action=action,
            link_mode="copy",
            message=(
                f"{action.capitalize()} copy: {target.name}. "
                "Symlinks unavailable; changes require re-running installer."
            ),
        )

    except OSError as e:
        return LinkResult(
            source=source,
            target=target,
            success=False,
            action="failed",
            link_mode="none",
            message=f"Failed to create link: {e}",
        )


# ---------------------------------------------------------------------------
# Cross-platform file locking
# ---------------------------------------------------------------------------


from spellbook.core.services import _pid_exists  # noqa: E402


class CrossPlatformLock:
    """Cross-platform file locking with stale lock detection.

    Uses fcntl.flock() on Unix, msvcrt.locking() on Windows.
    Supports context manager protocol.

    Args:
        lock_path: Path to the lock file.
        stale_seconds: Seconds after which a lock is considered stale.
        shared: If True, acquire a shared (read) lock. Only effective on Unix.
        blocking: If True, acquire() blocks until lock is available using
            the OS native blocking lock (fcntl.flock on Unix, msvcrt.LK_LOCK
            on Windows). If False, acquire() returns immediately.
    """

    def __init__(
        self,
        lock_path: Path,
        stale_seconds: int = 3600,
        shared: bool = False,
        blocking: bool = False,
    ):
        self.lock_path = lock_path
        self.stale_seconds = stale_seconds
        self.shared = shared
        self.blocking = blocking
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        """Acquire the lock.

        In blocking mode, waits until the lock becomes available (indefinitely
        on Unix via fcntl.flock, up to ~10 seconds on Windows via msvcrt.LK_LOCK).
        In non-blocking mode, returns immediately.

        Returns:
            True on success, False if lock is held by another live process.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)

        try:
            if sys.platform == "win32":
                import msvcrt

                # Note: msvcrt does not support shared locks.
                # On Windows, shared=True degrades to exclusive lock.
                if self.shared:
                    logger.debug(
                        "Windows: shared lock degrades to exclusive (msvcrt limitation)"
                    )
                if self.blocking:
                    # msvcrt.LK_LOCK retries up to 10 times (~10s), then raises OSError
                    msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)
                else:
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                flag = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
                if not self.blocking:
                    flag |= fcntl.LOCK_NB
                fcntl.flock(self._fd, flag)
        except (BlockingIOError, OSError):
            # Lock held - check if stale
            try:
                os.lseek(self._fd, 0, os.SEEK_SET)
                content = os.read(self._fd, 1024).decode()
                lock_info = json.loads(content)
                pid = lock_info.get("pid")
                timestamp = lock_info.get("timestamp", 0)

                is_stale = False
                if pid and not _pid_exists(pid):
                    is_stale = True
                elif time.time() - timestamp > self.stale_seconds:
                    is_stale = True

                if is_stale:
                    # Try to acquire again (stale lock)
                    try:
                        if sys.platform == "win32":
                            import msvcrt

                            msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl

                            flag = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
                            fcntl.flock(self._fd, flag | fcntl.LOCK_NB)
                    except (BlockingIOError, OSError):
                        os.close(self._fd)
                        self._fd = None
                        return False
                else:
                    os.close(self._fd)
                    self._fd = None
                    return False
            except (json.JSONDecodeError, OSError):
                os.close(self._fd)
                self._fd = None
                return False

        # Write our lock info
        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        lock_data = json.dumps({"pid": os.getpid(), "timestamp": time.time()})
        os.write(self._fd, lock_data.encode())
        return True

    def release(self) -> None:
        """Release the lock and clean up.

        In non-blocking mode, removes the lock file after release.
        In blocking mode, keeps the lock file to avoid race conditions
        with other threads/processes waiting on the same inode.
        """
        if self._fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    os.lseek(self._fd, 0, os.SEEK_SET)
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
            self._fd = None
            if not self.blocking:
                try:
                    self.lock_path.unlink()
                except OSError:
                    pass

    def __enter__(self) -> "CrossPlatformLock":
        if not self.acquire():
            raise LockHeldError(f"Lock held by another process: {self.lock_path}")
        return self

    def __exit__(self, *args) -> None:
        self.release()


# ---------------------------------------------------------------------------
# Service configuration and management (canonical source: spellbook.core.services)
# ---------------------------------------------------------------------------

# Re-export ServiceConfig, ServiceManager, and tts_service_config from
# spellbook.core.services so existing installer.compat consumers keep working.
from spellbook.core.services import ServiceConfig, ServiceManager, tts_service_config  # noqa: E402,F811


def _get_daemon_python_for_config() -> Optional[str]:
    """Get path to daemon venv Python, or None if not available.

    Thin wrapper around spellbook.daemon._paths.get_daemon_python to
    allow mocking in tests without requiring the full spellbook package.
    """
    from spellbook.daemon._paths import get_daemon_python

    return get_daemon_python()


def _get_daemon_path() -> str:
    """Get platform-appropriate PATH for the daemon service."""
    plat = get_platform()
    if plat == Platform.MACOS:
        from spellbook.daemon.service import _get_darwin_daemon_path

        return _get_darwin_daemon_path()
    elif plat == Platform.LINUX:
        from spellbook.daemon.service import _get_linux_daemon_path

        return _get_linux_daemon_path()
    return os.environ.get("PATH", "")


def mcp_service_config(spellbook_dir: Path, port: int, host: str) -> ServiceConfig:
    """Build ServiceConfig for the MCP daemon (backward-compatible).

    Args:
        spellbook_dir: Path to the spellbook installation.
        port: MCP server port (typically 8765).
        host: MCP server host (typically "127.0.0.1").

    Returns:
        ServiceConfig with MCP daemon parameters.
    """
    daemon_path = _get_daemon_path()

    daemon_python_str = _get_daemon_python_for_config()
    if daemon_python_str and Path(daemon_python_str).exists():
        executable = Path(daemon_python_str)
        args = ["-m", "spellbook.mcp"]
    else:
        uv_path = shutil.which("uv") or "uv"
        executable = Path(uv_path)
        args = ["run", "python", "-m", "spellbook.mcp"]

    config_dir = Path(
        os.environ.get("SPELLBOOK_CONFIG_DIR", str(get_config_dir()))
    )
    log_dir = get_log_dir()

    return ServiceConfig(
        launchd_label="com.spellbook.mcp",
        service_name="spellbook-mcp",
        schtasks_name="SpellbookMCP",
        description="Spellbook MCP Server",
        executable=executable,
        args=args,
        working_directory=spellbook_dir,
        environment={
            "PATH": daemon_path,
            "SPELLBOOK_MCP_TRANSPORT": "streamable-http",
            "SPELLBOOK_MCP_HOST": host,
            "SPELLBOOK_MCP_PORT": str(port),
            "SPELLBOOK_DIR": str(spellbook_dir),
        },
        log_stdout=log_dir / "mcp.log",
        log_stderr=log_dir / "mcp.err.log",
        pid_file=config_dir / "spellbook-mcp.pid",
        keep_alive=True,
        health_check_port=port,
        health_check_host=host,
    )


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def get_python_executable() -> str:
    """Get the Python executable path.

    Handles the python3 vs python naming difference on Windows.
    Returns sys.executable which always works.
    """
    return sys.executable


# Re-export path helpers from spellbook.core.paths (canonical source).
# installer.compat consumers (including installer/ modules) can continue
# importing get_data_dir, get_log_dir, get_config_dir from here.
from spellbook.core.paths import get_config_dir, get_data_dir, get_log_dir


