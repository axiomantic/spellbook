"""Access tracking and audit trail for the file-based memory system.

Manages two sidecar files in the memory directory:
- .access-log.json: Per-memory access counts and last_accessed timestamps
- .audit-log.jsonl: Append-only audit trail of all memory operations
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from spellbook.core.compat import CrossPlatformLock


def record_access(memory_path: str, memory_dir: str) -> None:
    """Record an access to a memory file.

    Increments the access count and updates last_accessed in .access-log.json.
    Holds an exclusive lock for the entire read-modify-write cycle to prevent
    TOCTOU races.

    Args:
        memory_path: Relative path of the memory within memory_dir (e.g. "project/test.md").
        memory_dir: Root memory directory containing .access-log.json.
    """
    log_path = os.path.join(memory_dir, ".access-log.json")

    # Hold exclusive lock for the entire read-modify-write cycle
    _atomic_update_access_log(log_path, memory_path)


def get_importance(memory_path: str, memory_dir: str) -> float:
    """Compute importance score from access count.

    Returns min(1.0 + 0.1 * access_count, 10.0). Defaults to 1.0 if not accessed.

    Args:
        memory_path: Relative path of the memory within memory_dir.
        memory_dir: Root memory directory containing .access-log.json.
    """
    log_path = os.path.join(memory_dir, ".access-log.json")
    data = _read_access_log(log_path)
    return importance_from_log(data, memory_path)


def importance_from_log(data: dict, memory_path: str) -> float:
    """Compute importance score from a pre-loaded access-log dict.

    Use this when iterating many paths against the same log to avoid
    re-reading the file on every call.
    """
    if memory_path not in data:
        return 1.0
    count = data[memory_path]["count"]
    return min(1.0 + 0.1 * count, 10.0)


def load_access_log(memory_dir: str) -> dict:
    """Read the access-log dict for a memory directory (empty if missing)."""
    log_path = os.path.join(memory_dir, ".access-log.json")
    return _read_access_log(log_path)


def batch_record_access(memory_paths: list[str], memory_dir: str) -> None:
    """Record accesses for multiple memories in a single read-modify-write cycle.

    Equivalent to calling :func:`record_access` for each path but performs
    exactly one ``_write_access_log`` invocation regardless of how many
    paths are supplied. Skips the write entirely when the input list is empty.
    """
    if not memory_paths:
        return

    log_path = os.path.join(memory_dir, ".access-log.json")
    dir_path = os.path.dirname(log_path) or "."
    os.makedirs(dir_path, exist_ok=True)

    lock_path = Path(log_path + ".lock")
    with CrossPlatformLock(lock_path, shared=False, blocking=True):
        if os.path.exists(log_path):
            with open(log_path, "rb") as f:
                content = f.read()
        else:
            content = b""

        data = json.loads(content.decode("utf-8")) if content else {}

        now = datetime.now(timezone.utc).isoformat()
        for memory_path in memory_paths:
            entry = data.get(memory_path)
            if entry is None:
                entry = {"count": 0, "last_accessed": ""}
                data[memory_path] = entry
            entry["count"] += 1
            entry["last_accessed"] = now

        _write_access_log(log_path, data)


def record_audit(
    action: str,
    memory_path: str,
    details: dict,
    memory_dir: str,
) -> None:
    """Append an entry to the audit trail.

    Args:
        action: The action performed (create, update, delete, archive, verify, recall).
        memory_path: Path of the affected memory file.
        details: Additional context about the action.
        memory_dir: Root memory directory containing .audit-log.jsonl.
    """
    log_path = os.path.join(memory_dir, ".audit-log.jsonl")
    entry = {
        "action": action,
        "memory_path": memory_path,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    line = json.dumps(entry, separators=(",", ":")) + "\n"

    lock_path = Path(log_path + ".lock")
    with CrossPlatformLock(lock_path, shared=False, blocking=True):
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)


def _atomic_update_access_log(log_path: str, memory_path: str) -> None:
    """Atomically read-modify-write the access log under exclusive lock.

    Holds the lock for the entire cycle to prevent TOCTOU races between
    concurrent read and write operations.
    """
    dir_path = os.path.dirname(log_path) or "."
    os.makedirs(dir_path, exist_ok=True)

    lock_path = Path(log_path + ".lock")
    with CrossPlatformLock(lock_path, shared=False, blocking=True):
        # Read current data under lock
        if os.path.exists(log_path):
            with open(log_path, "rb") as f:
                content = f.read()
        else:
            content = b""

        if content:
            data = json.loads(content.decode("utf-8"))
        else:
            data = {}

        # Modify
        if memory_path not in data:
            data[memory_path] = {"count": 0, "last_accessed": ""}
        data[memory_path]["count"] += 1
        data[memory_path]["last_accessed"] = datetime.now(timezone.utc).isoformat()

        # Write atomically via temp file, then rename (still under lock)
        _write_access_log(log_path, data)


def _read_access_log(log_path: str) -> dict:
    """Read the access log file. Returns empty dict if not found."""
    if not os.path.exists(log_path):
        return {}
    lock_path = Path(log_path + ".lock")
    with CrossPlatformLock(lock_path, shared=True, blocking=True):
        with open(log_path, "r") as f:
            return json.load(f)


def _write_access_log(log_path: str, data: dict) -> None:
    """Atomically write the access log file."""
    dir_path = os.path.dirname(log_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".tmp_access_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, log_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
