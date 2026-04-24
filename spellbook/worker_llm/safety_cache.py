"""Persistent verdict + block cache for ``tool_safety``.

Disk schema (JSON)::

    {
      "verdicts": {<sha256>: {"verdict": "OK|WARN|BLOCK",
                              "reasoning": "...",
                              "expires_at": <float wall-clock>}},
      "blocks":   {<sha256>: <float wall-clock>}
    }

The cache is file-backed because Claude Code fires each hook in a fresh
subprocess — an in-process dict would never see the 30-second bypass
window record. Writes are atomic (temp file + ``os.replace``) so a
concurrent read never observes a partially-written cache.

**Graceful degradation.** A corrupt cache file on disk is not a crash:
we log a single WARNING and start with empty caches. The next successful
write heals the file.

**Size cap.** ``MAX_CACHE_ENTRIES`` (default 500) bounds the on-disk
footprint. Once full, insertion-order eviction (FIFO) drops the oldest
entry. Worst-case collision rate is tiny because verdict keys are
sha256 of the (tool_name, params) pair.

See impl plan Task SC1, design §5.2, §14.4.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from spellbook.core.command_utils import atomic_replace
from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict

logger = logging.getLogger(__name__)

CACHE_PATH: Path = (
    Path.home() / ".local" / "spellbook" / "cache" / "worker_llm_block.json"
)

BYPASS_WINDOW_S: float = 30.0
MAX_CACHE_ENTRIES: int = 500


@dataclass
class _Entry:
    verdict: SafetyVerdict
    expires_at: float  # wall-clock


# Insertion-ordered dicts (CPython 3.7+) give us FIFO eviction for free.
_VERDICT_CACHE: dict[str, _Entry] = {}
_BLOCK_CACHE: dict[str, float] = {}

# Module-level counter so we can emit a single loud warning on the first
# persist failure per process, then fall back to DEBUG for the rest.
# Rationale: cache persistence is best-effort (fire-and-forget) and runs in
# the hot hook subprocess path, so we do not want to spam logs — but silent
# swallow hid unwritable-cache-dir bugs. One WARN makes misconfigurations
# loud without flooding. Pattern mirrors ``events.py::_publish_failures``.
_persist_failures: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_key(tool_name: str, params: dict) -> str:
    """Deterministic SHA-256 key for a (tool_name, params) signature.

    ``sort_keys=True`` so dict reordering does not change the key. Non-
    serializable values fall back to ``str(v)`` via ``default=str`` so
    things like ``Path`` objects in params do not blow up.
    """
    body = tool_name + "|" + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def get_cached_verdict(key: str) -> SafetyVerdict | None:
    """Return a cached verdict if one exists and has not expired."""
    entry = _VERDICT_CACHE.get(key)
    if entry is None:
        return None
    if entry.expires_at < time.time():
        _VERDICT_CACHE.pop(key, None)
        _persist_to_disk()
        return None
    return entry.verdict


def cache_verdict(key: str, verdict: SafetyVerdict) -> None:
    """Store ``verdict`` under ``key`` with a wall-clock expiry.

    Enforces ``MAX_CACHE_ENTRIES`` via insertion-order eviction: when
    the cache is full and the key is new, the oldest entry is dropped.
    """
    ttl = _ttl_seconds()
    # If key already present, rotate it to MRU position by popping first.
    if key in _VERDICT_CACHE:
        _VERDICT_CACHE.pop(key)
    elif len(_VERDICT_CACHE) >= MAX_CACHE_ENTRIES:
        # Evict oldest insertion (FIFO) to make room.
        oldest_key = next(iter(_VERDICT_CACHE))
        _VERDICT_CACHE.pop(oldest_key, None)

    _VERDICT_CACHE[key] = _Entry(
        verdict=verdict, expires_at=time.time() + ttl
    )
    _persist_to_disk()


def record_block(key: str) -> None:
    """Remember that a BLOCK verdict fired for ``key`` at wall-clock now."""
    _BLOCK_CACHE[key] = time.time()
    _persist_to_disk()


def should_bypass(key: str) -> bool:
    """True iff ``key`` has a fresh (<=30s) block; consumes the bypass.

    Consuming means the next call returns False. Rationale: the 30s
    window is meant to let a user re-run the exact same blocked call
    once, not grant a rolling amnesty.
    """
    t = _BLOCK_CACHE.get(key)
    if t is None:
        return False
    within = (time.time() - t) <= BYPASS_WINDOW_S
    _BLOCK_CACHE.pop(key, None)
    _persist_to_disk()
    return within


# ---------------------------------------------------------------------------
# Disk I/O
# ---------------------------------------------------------------------------


def _ttl_seconds() -> float:
    from spellbook.core.config import config_get

    return float(config_get("worker_llm_safety_cache_ttl_s") or 300.0)


def _load_from_disk() -> None:
    """Repopulate the in-memory caches from ``CACHE_PATH``.

    Called once at import time and exposed for tests that reload the
    module. Corrupt JSON, missing keys, or wrong-type payloads produce a
    single WARNING and an empty cache — never an exception.
    """
    _VERDICT_CACHE.clear()
    _BLOCK_CACHE.clear()
    if not CACHE_PATH.exists():
        return
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            "worker_llm safety_cache is corrupt (%s: %s); "
            "starting fresh, next write will heal the file.",
            type(e).__name__,
            e,
        )
        return
    if not isinstance(payload, dict):
        logger.warning(
            "worker_llm safety_cache schema mismatch "
            "(expected object, got %s); starting fresh.",
            type(payload).__name__,
        )
        return

    now = time.time()
    verdicts = payload.get("verdicts") or {}
    if isinstance(verdicts, dict):
        for k, row in verdicts.items():
            if not isinstance(row, dict):
                continue
            try:
                expires_at = float(row["expires_at"])
            except (KeyError, TypeError, ValueError):
                continue
            if expires_at < now:
                continue  # dead on arrival
            verdict = str(row.get("verdict", ""))
            reasoning = str(row.get("reasoning", ""))
            if verdict not in {"OK", "WARN", "BLOCK"}:
                continue
            _VERDICT_CACHE[str(k)] = _Entry(
                verdict=SafetyVerdict(verdict=verdict, reasoning=reasoning),
                expires_at=expires_at,
            )

    blocks = payload.get("blocks") or {}
    if isinstance(blocks, dict):
        for k, ts in blocks.items():
            try:
                _BLOCK_CACHE[str(k)] = float(ts)
            except (TypeError, ValueError):
                continue


def _persist_to_disk() -> None:
    """Atomically write the current caches to ``CACHE_PATH``.

    Fire-and-forget: IO errors are logged but do not propagate — the
    tool_safety path is already in the hot hook subprocess and must
    never raise here.
    """
    payload = {
        "verdicts": {
            k: {
                "verdict": e.verdict.verdict,
                "reasoning": e.verdict.reasoning,
                "expires_at": e.expires_at,
            }
            for k, e in _VERDICT_CACHE.items()
        },
        "blocks": dict(_BLOCK_CACHE),
    }
    global _persist_failures
    try:
        _atomic_write_json(CACHE_PATH, payload)
    except OSError as e:
        # FIRST failure per process -> WARNING (actionable, names the path
        # and exception type). Subsequent failures drop to DEBUG to avoid
        # flooding logs from the hot hook subprocess path.
        if _persist_failures == 0:
            logger.warning(
                "worker_llm safety_cache persist failed (%s writing to %s): "
                "%s. Further failures will be logged at DEBUG.",
                type(e).__name__,
                CACHE_PATH,
                e,
            )
        else:
            logger.debug("safety_cache write failed: %s", e)
        _persist_failures += 1


def _atomic_write_json(path: Path, data: dict) -> None:
    """Atomic write via tempfile + ``os.replace``.

    Pattern mirrors ``hooks/spellbook_hook.py::_atomic_write_json`` so a
    crashing process never leaves a half-written cache visible to a
    concurrent reader.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data).encode("utf-8")
    for _ in range(5):
        tmp = path.with_suffix(f".tmp.{os.getpid()}.{secrets.token_hex(4)}")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(body)
            atomic_replace(str(tmp), str(path))
            return
        except Exception:
            # Clean up the temp file so a failed write does not leave
            # litter in the cache directory.
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
    raise OSError(
        f"safety_cache: could not acquire a fresh tempfile suffix near {path}"
    )


# Populate in-memory caches at import time so hook subprocesses that never
# call `_load_from_disk()` explicitly still see the persisted state.
_load_from_disk()
