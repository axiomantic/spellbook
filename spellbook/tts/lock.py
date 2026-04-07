"""Cross-process provisioning lock for TTS service installation.

Prevents concurrent provisioning from the installer wizard and MCP
config_set handler racing each other. Uses flock (Unix) / msvcrt (Windows).
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

from spellbook.core.paths import get_data_dir

DEFAULT_LOCK_FILE = get_data_dir() / "tts-provision.lock"


class ProvisioningLocked(Exception):
    """Another process is already provisioning TTS."""


def is_provisioning_locked(lock_file: Path = None) -> bool:
    """Check whether the provisioning lock is currently held.

    Attempts a non-blocking lock acquisition. If the lock cannot be
    acquired, another process is provisioning TTS.

    Args:
        lock_file: Path to the lock file. Defaults to DEFAULT_LOCK_FILE.

    Returns:
        True if provisioning is in progress (lock held), False otherwise.
    """
    if lock_file is None:
        lock_file = DEFAULT_LOCK_FILE

    if not lock_file.exists():
        return False

    fd = None
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                # Lock acquired: not held by another process
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                return False
            except OSError:
                return True
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired: not held by another process
                fcntl.flock(fd, fcntl.LOCK_UN)
                return False
            except OSError:
                return True
    except OSError:
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


@contextmanager
def provisioning_lock(lock_file: Path = None):
    """Acquire cross-process provisioning lock.

    Uses PID file + flock (Unix) or msvcrt.locking (Windows).
    Non-blocking: raises ProvisioningLocked immediately if held.

    Args:
        lock_file: Path to the lock file. Defaults to DEFAULT_LOCK_FILE.

    Yields:
        None on success.

    Raises:
        ProvisioningLocked: If lock cannot be acquired.
    """
    if lock_file is None:
        lock_file = DEFAULT_LOCK_FILE

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    try:
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ProvisioningLocked(
                    "TTS provisioning already in progress"
                )
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ProvisioningLocked(
                    "TTS provisioning already in progress"
                )

        # Write PID for debugging
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, str(os.getpid()).encode())

        yield
    finally:
        if sys.platform == "win32":
            import msvcrt

            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
