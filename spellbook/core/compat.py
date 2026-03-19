"""Cross-platform compatibility layer for spellbook (runtime subset).

This module contains the runtime-relevant subset of installer/compat.py:
file locking, config directory resolution, and platform detection.

Installer-only code (link creation, service management, shell integration)
remains in installer/compat.py.

No external dependencies beyond the Python standard library.
"""

import json
import logging
import os
import platform
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


class Platform(Enum):
    """Supported operating systems."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"


class UnsupportedPlatformError(Exception):
    """Raised when running on an unsupported OS."""

    pass


class LockHeldError(Exception):
    """Raised when a lock cannot be acquired because another process holds it."""

    pass


def get_platform() -> Platform:
    """Return the current OS as a Platform enum.

    Returns:
        Platform enum value for the current OS.

    Raises:
        UnsupportedPlatformError: If the OS is not macOS, Linux, or Windows.
    """
    system = platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    elif system == "linux":
        return Platform.LINUX
    elif system == "windows":
        return Platform.WINDOWS
    raise UnsupportedPlatformError(f"Unsupported OS: {system}")


# ---------------------------------------------------------------------------
# Cross-platform file locking
# ---------------------------------------------------------------------------


def _pid_exists(pid: int) -> bool:
    """Check if a process with given PID exists.

    Uses os.kill(pid, 0) on Unix, OpenProcess on Windows.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except (OSError, AttributeError):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            # Process exists but we lack permission to signal it
            return True
        except OSError:
            return False


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
# Utility functions
# ---------------------------------------------------------------------------


def get_config_dir(app_name: str = "spellbook") -> Path:
    """Get OS-appropriate config directory.

    macOS:   ~/.config/{app_name}
    Linux:   ~/.config/{app_name}
    Windows: %APPDATA%/{app_name}

    Args:
        app_name: Application name for the config subdirectory.

    Returns:
        Path to the config directory.
    """
    if get_platform() == Platform.WINDOWS:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    return Path.home() / ".config" / app_name
