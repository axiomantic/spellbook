"""PID file management for the spellbook daemon.

Provides read/write/remove operations for the daemon PID file,
plus a convenience check for whether the daemon process is running.
"""

from __future__ import annotations

from pathlib import Path

from spellbook.core.compat import _pid_exists
from spellbook.daemon._paths import get_pid_file


def read_pid() -> int | None:
    """Read PID from pid file, return None if not exists or invalid.

    If the PID file exists but the process is no longer running, the stale
    PID file is cleaned up and ``None`` is returned.
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if _pid_exists(pid):
            return pid
        pid_file.unlink(missing_ok=True)
        return None
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return None


def write_pid(pid: int) -> None:
    """Write PID to pid file."""
    get_pid_file().write_text(str(pid), encoding="utf-8")


def remove_pid() -> None:
    """Remove the PID file if it exists."""
    get_pid_file().unlink(missing_ok=True)


def is_daemon_running() -> bool:
    """Check whether the daemon process is currently running.

    Returns ``True`` if a PID file exists and the process is alive.
    """
    return read_pid() is not None
