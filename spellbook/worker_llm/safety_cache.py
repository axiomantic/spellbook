"""Verdict cache for ``tool_safety``.

Minimal in-memory stub. Task SC1 replaces the storage with a persistent
JSON cache at ``~/.local/spellbook/worker_llm/safety_cache.json`` with TTL
expiry, size-capped LRU eviction, and atomic writes.

Public API (stable across stub and full implementation):
- ``make_key(tool_name, params) -> str``
- ``get_cached_verdict(key) -> SafetyVerdict | None``
- ``cache_verdict(key, verdict) -> None``
- ``record_block(key) -> None``
- ``should_bypass(key) -> bool``
"""

from __future__ import annotations

import hashlib
import json
import time

from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict

_VERDICT_CACHE: dict[str, tuple[SafetyVerdict, float]] = {}
_BLOCK_CACHE: dict[str, float] = {}
BYPASS_WINDOW_S = 30.0


def make_key(tool_name: str, params: dict) -> str:
    """Deterministic SHA-256 key for a tool-call signature."""
    body = tool_name + "|" + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def get_cached_verdict(key: str) -> SafetyVerdict | None:
    """Return a cached verdict if one exists and has not expired."""
    entry = _VERDICT_CACHE.get(key)
    if entry is None:
        return None
    verdict, expires_at = entry
    if expires_at < time.time():
        _VERDICT_CACHE.pop(key, None)
        return None
    return verdict


def cache_verdict(key: str, verdict: SafetyVerdict) -> None:
    """Store a verdict under ``key`` with the configured TTL."""
    from spellbook.core.config import config_get

    ttl = float(config_get("worker_llm_safety_cache_ttl_s") or 300.0)
    _VERDICT_CACHE[key] = (verdict, time.time() + ttl)


def record_block(key: str) -> None:
    """Remember that a BLOCK verdict fired for ``key`` at wall-clock now."""
    _BLOCK_CACHE[key] = time.time()


def should_bypass(key: str) -> bool:
    """True iff ``key`` has a fresh (<=30s) block that we will now consume."""
    t = _BLOCK_CACHE.get(key)
    if t is None:
        return False
    if time.time() - t <= BYPASS_WINDOW_S:
        _BLOCK_CACHE.pop(key, None)
        return True
    _BLOCK_CACHE.pop(key, None)
    return False
