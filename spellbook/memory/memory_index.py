"""Sidecar index for fast memory lookup by hash and efficient listing.

The index lives at ``<memory_dir>/.memory-index.json`` and mirrors minimal
metadata (content_hash, type, kind, created, mtime_ns) for every memory
markdown file in the directory. It is authoritative for two hot paths:

- Dedup lookup by content hash in ``filestore.store_memory``
  (replaces O(N) directory walk + frontmatter parse).
- Listing memories for the admin UI (``/api/memories``), avoiding per-request
  frontmatter parsing of every file.

The index is a cache: callers must invoke :func:`rebuild_if_stale` to
self-heal after external modifications. When the cached index cannot be
trusted (missing file, corrupt JSON), callers should be prepared to fall
back to the canonical on-disk representation.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from spellbook.memory.frontmatter import parse_frontmatter
from spellbook.memory.models import MemoryFrontmatter
from spellbook.memory.utils import iter_memory_files

logger = logging.getLogger(__name__)

INDEX_FILENAME = ".memory-index.json"
INDEX_VERSION = 1

# In-memory cache of last rebuild-check wall-clock time per memory_dir.
# Keeps ``rebuild_if_stale`` cheap when called from hot paths.
_REBUILD_CHECK_CACHE: dict[str, float] = {}
_REBUILD_CHECK_INTERVAL_SEC = 60.0


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------


def _index_path(memory_dir: str) -> Path:
    return Path(memory_dir) / INDEX_FILENAME


def load_index(memory_dir: str | os.PathLike) -> dict:
    """Load the index file, or return an empty schema on miss/corruption."""
    path = _index_path(str(memory_dir))
    if not path.exists():
        return {"version": INDEX_VERSION, "entries": {}}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("memory-index unreadable at %s: %s; returning empty", path, e)
        return {"version": INDEX_VERSION, "entries": {}}
    if not isinstance(data, dict) or "entries" not in data:
        return {"version": INDEX_VERSION, "entries": {}}
    return data


def save_index(memory_dir: str | os.PathLike, index: dict) -> None:
    """Atomically write the index JSON (tempfile + fsync + replace)."""
    dir_path = Path(memory_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    target = _index_path(str(memory_dir))

    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), prefix=".tmp_memidx_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(index, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Entry manipulation
# ---------------------------------------------------------------------------


def _entry_payload(
    frontmatter: MemoryFrontmatter,
    content_hash: str,
    mtime_ns: int,
) -> dict[str, Any]:
    created = frontmatter.created
    created_str = (
        created.isoformat() if isinstance(created, date) else str(created)
    )
    return {
        "content_hash": content_hash,
        "type": frontmatter.type,
        "kind": frontmatter.kind,
        "created": created_str,
        "mtime_ns": mtime_ns,
    }


def record_store(
    memory_dir: str | os.PathLike,
    rel_path: str,
    frontmatter: MemoryFrontmatter,
    content_hash: str,
    mtime_ns: int,
) -> None:
    """Upsert an entry for a newly stored or updated memory."""
    index = load_index(memory_dir)
    index.setdefault("version", INDEX_VERSION)
    index.setdefault("entries", {})
    index["entries"][rel_path] = _entry_payload(frontmatter, content_hash, mtime_ns)
    save_index(memory_dir, index)


def record_delete(memory_dir: str | os.PathLike, rel_path: str) -> None:
    """Drop an entry for a forgotten/archived memory.

    Always persists the index (even on miss) so the sidecar file exists.
    """
    index = load_index(memory_dir)
    index.setdefault("version", INDEX_VERSION)
    index.setdefault("entries", {})
    index["entries"].pop(rel_path, None)
    save_index(memory_dir, index)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def find_by_hash(
    memory_dir: str | os.PathLike, content_hash: str
) -> list[str]:
    """Return rel_paths of all memories with the given content_hash."""
    index = load_index(memory_dir)
    matches: list[str] = []
    for rel_path, entry in index.get("entries", {}).items():
        if entry.get("content_hash") == content_hash:
            matches.append(rel_path)
    return matches


def list_entries(memory_dir: str | os.PathLike) -> list[dict[str, Any]]:
    """Return all index entries sorted by ``created`` desc, ties by rel_path.

    Each returned dict includes ``rel_path`` plus all stored fields.
    """
    index = load_index(memory_dir)
    entries = index.get("entries", {})
    listed: list[dict[str, Any]] = []
    for rel_path, entry in entries.items():
        item = {"rel_path": rel_path, **entry}
        listed.append(item)

    def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
        # Sort by created desc (lexicographic on ISO date string works), then
        # rel_path asc for stable ordering on ties. We invert the created key
        # by using a tuple (negated via a sentinel) -- easier to just sort
        # twice: by rel_path asc first (stable), then by created desc.
        return (item.get("created") or "", item.get("rel_path", ""))

    listed.sort(key=lambda it: it.get("rel_path", ""))
    listed.sort(key=lambda it: it.get("created") or "", reverse=True)
    return listed


# ---------------------------------------------------------------------------
# Rebuild / self-heal
# ---------------------------------------------------------------------------


def _scan_disk_entries(memory_dir: str) -> dict[str, dict[str, Any]]:
    """Walk ``memory_dir`` and build an index dict from disk."""
    from spellbook.memory.utils import content_hash as _ch

    entries: dict[str, dict[str, Any]] = {}
    root = Path(memory_dir)
    if not root.is_dir():
        return entries
    for abs_path in iter_memory_files(str(root)):
        try:
            fm, body = parse_frontmatter(abs_path)
        except (ValueError, OSError):
            continue
        rel = os.path.relpath(abs_path, str(root))
        rel_norm = rel.replace(os.sep, "/")
        try:
            mtime_ns = os.stat(abs_path).st_mtime_ns
        except OSError:
            continue
        c_hash = fm.content_hash or _ch(body)
        entries[rel_norm] = _entry_payload(fm, c_hash, mtime_ns)
    return entries


def _disk_state_signature(memory_dir: str) -> set[tuple[str, int]]:
    """Return (rel_path, mtime_ns) pairs for all .md files on disk.

    Cheap enough to run on every rebuild check; no frontmatter parsing.
    """
    sig: set[tuple[str, int]] = set()
    root = Path(memory_dir)
    if not root.is_dir():
        return sig
    for abs_path in iter_memory_files(str(root)):
        rel = os.path.relpath(abs_path, str(root)).replace(os.sep, "/")
        try:
            mtime_ns = os.stat(abs_path).st_mtime_ns
        except OSError:
            continue
        sig.add((rel, mtime_ns))
    return sig


def _index_signature(index: dict) -> set[tuple[str, int]]:
    return {
        (rel, int(entry.get("mtime_ns") or 0))
        for rel, entry in index.get("entries", {}).items()
    }


def rebuild_if_stale(
    memory_dir: str | os.PathLike,
    *,
    force: bool = False,
    now: float | None = None,
) -> bool:
    """Detect index/disk divergence; full-rebuild on mismatch.

    Uses an in-memory 60s throttle so hot paths can call this freely.
    Pass ``force=True`` to bypass the throttle (tests, explicit admin ops).

    Returns True if a rebuild was performed, False otherwise.
    """
    import time

    key = os.path.realpath(str(memory_dir))
    if not force:
        now_val = now if now is not None else time.monotonic()
        last = _REBUILD_CHECK_CACHE.get(key)
        if last is not None and (now_val - last) < _REBUILD_CHECK_INTERVAL_SEC:
            return False
        _REBUILD_CHECK_CACHE[key] = now_val

    index = load_index(memory_dir)
    disk_sig = _disk_state_signature(str(memory_dir))
    idx_sig = _index_signature(index)

    if disk_sig == idx_sig:
        return False

    fresh_entries = _scan_disk_entries(str(memory_dir))
    save_index(memory_dir, {"version": INDEX_VERSION, "entries": fresh_entries})
    return True
