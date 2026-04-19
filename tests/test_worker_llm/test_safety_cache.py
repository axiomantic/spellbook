"""Tests for persistent JSON safety cache.

Covers: make_key stability, TTL expiry (time-travel via monkeypatch —
freezegun is not a dev dep, see impl plan I4), record_block + bypass
consumption, persistence across importlib.reload, size cap + insertion-
order eviction, atomic writes (no partial file on crash), graceful
degradation on corrupt cache file.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from spellbook.worker_llm import safety_cache
from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Redirect the module-global cache file to a temp path for every test
    and reset the in-memory mirrors."""
    path = tmp_path / "c.json"
    monkeypatch.setattr(safety_cache, "CACHE_PATH", path)
    safety_cache._VERDICT_CACHE.clear()
    safety_cache._BLOCK_CACHE.clear()
    yield path
    safety_cache._VERDICT_CACHE.clear()
    safety_cache._BLOCK_CACHE.clear()


# ---------------------------------------------------------------------------
# make_key
# ---------------------------------------------------------------------------


def test_make_key_is_deterministic():
    k1 = safety_cache.make_key("Bash", {"command": "ls", "cwd": "/tmp"})
    k2 = safety_cache.make_key("Bash", {"cwd": "/tmp", "command": "ls"})
    assert k1 == k2  # stable across insertion order (sort_keys=True)


def test_make_key_differs_on_tool_name():
    assert safety_cache.make_key("Bash", {}) != safety_cache.make_key("Edit", {})


def test_make_key_differs_on_params():
    assert (
        safety_cache.make_key("Bash", {"command": "ls"})
        != safety_cache.make_key("Bash", {"command": "pwd"})
    )


# ---------------------------------------------------------------------------
# Roundtrip + TTL expiry
# ---------------------------------------------------------------------------


def test_verdict_roundtrip(_isolate_cache, monkeypatch):
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 300.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )
    k = safety_cache.make_key("Bash", {"command": "ls"})
    safety_cache.cache_verdict(k, SafetyVerdict(verdict="OK", reasoning="r"))

    got = safety_cache.get_cached_verdict(k)
    assert got == SafetyVerdict(verdict="OK", reasoning="r")


def test_verdict_expiry(_isolate_cache, monkeypatch):
    """Time-travel past the TTL; the cached entry must be evicted."""
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 1.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )
    start_t = 1_700_000_000.0
    monkeypatch.setattr("time.time", lambda: start_t)

    k = safety_cache.make_key("Bash", {})
    safety_cache.cache_verdict(k, SafetyVerdict(verdict="OK", reasoning=""))

    # Before TTL elapses: still hot.
    monkeypatch.setattr("time.time", lambda: start_t + 0.5)
    assert safety_cache.get_cached_verdict(k) is not None

    # After TTL elapses: evicted.
    monkeypatch.setattr("time.time", lambda: start_t + 2.0)
    assert safety_cache.get_cached_verdict(k) is None


def test_get_cached_verdict_missing_returns_none(_isolate_cache):
    assert safety_cache.get_cached_verdict("no-such-key") is None


# ---------------------------------------------------------------------------
# Block + bypass
# ---------------------------------------------------------------------------


def test_bypass_within_30s(_isolate_cache, monkeypatch):
    start_t = 1_700_000_000.0
    monkeypatch.setattr("time.time", lambda: start_t)
    k = safety_cache.make_key("Bash", {})
    safety_cache.record_block(k)

    # Within window: True, then consumed -> False.
    assert safety_cache.should_bypass(k) is True
    assert safety_cache.should_bypass(k) is False


def test_bypass_expires_after_window(_isolate_cache, monkeypatch):
    start_t = 1_700_000_000.0
    monkeypatch.setattr("time.time", lambda: start_t)
    k = safety_cache.make_key("Bash", {})
    safety_cache.record_block(k)

    # Jump past the 30s window — expired (and removed).
    monkeypatch.setattr("time.time", lambda: start_t + 31.0)
    assert safety_cache.should_bypass(k) is False


def test_should_bypass_on_empty_cache_returns_false(_isolate_cache):
    assert safety_cache.should_bypass("unknown-key") is False


# ---------------------------------------------------------------------------
# Persistence: file-backed across reload
# ---------------------------------------------------------------------------


def test_block_persists_across_module_reload(_isolate_cache, monkeypatch):
    """record_block must be durable: a second process (simulated by reload)
    sees the block and can honor the 30s bypass window."""
    start_t = 1_700_000_000.0
    monkeypatch.setattr("time.time", lambda: start_t)
    k = safety_cache.make_key("Bash", {"x": 1})
    safety_cache.record_block(k)
    assert _isolate_cache.exists()

    # Preserve the CACHE_PATH override across the reload.
    saved_path = safety_cache.CACHE_PATH
    reloaded = importlib.reload(safety_cache)
    reloaded.CACHE_PATH = saved_path
    reloaded._load_from_disk()

    # Still within bypass window after reload.
    monkeypatch.setattr("time.time", lambda: start_t + 5.0)
    assert reloaded.should_bypass(k) is True


def test_verdict_persists_across_module_reload(_isolate_cache, monkeypatch):
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 300.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )
    start_t = 1_700_000_000.0
    monkeypatch.setattr("time.time", lambda: start_t)

    k = safety_cache.make_key("Bash", {"c": "ls"})
    safety_cache.cache_verdict(
        k, SafetyVerdict(verdict="WARN", reasoning="touches env")
    )

    saved_path = safety_cache.CACHE_PATH
    reloaded = importlib.reload(safety_cache)
    reloaded.CACHE_PATH = saved_path
    reloaded._load_from_disk()

    assert reloaded.get_cached_verdict(k) == SafetyVerdict(
        verdict="WARN", reasoning="touches env"
    )


# ---------------------------------------------------------------------------
# Size cap + eviction
# ---------------------------------------------------------------------------


def test_size_cap_evicts_oldest_insert(_isolate_cache, monkeypatch):
    """Once the verdict cache is full, the oldest insertion is evicted."""
    monkeypatch.setattr(safety_cache, "MAX_CACHE_ENTRIES", 3)
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 300.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )
    start_t = 1_700_000_000.0
    monkeypatch.setattr("time.time", lambda: start_t)

    keys = [safety_cache.make_key("Bash", {"i": i}) for i in range(4)]
    for k in keys:
        safety_cache.cache_verdict(k, SafetyVerdict(verdict="OK", reasoning=""))

    # 4th insert evicts the 1st.
    assert safety_cache.get_cached_verdict(keys[0]) is None
    for k in keys[1:]:
        assert safety_cache.get_cached_verdict(k) is not None


# ---------------------------------------------------------------------------
# Atomic write + corruption recovery
# ---------------------------------------------------------------------------


def test_atomic_write_leaves_no_tempfile(_isolate_cache, monkeypatch):
    """Successful write: only the target file survives, no orphan *.tmp."""
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 300.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )
    k = safety_cache.make_key("Bash", {})
    safety_cache.cache_verdict(k, SafetyVerdict(verdict="OK", reasoning=""))

    parent = _isolate_cache.parent
    entries = sorted(p.name for p in parent.iterdir())
    assert entries == [_isolate_cache.name]


def test_corrupt_cache_file_starts_fresh(tmp_path, monkeypatch, caplog):
    """A garbage cache file must not crash import; log a warning and start
    from an empty in-memory cache."""
    import logging

    path = tmp_path / "c.json"
    path.write_text("{not valid json")
    monkeypatch.setattr(safety_cache, "CACHE_PATH", path)

    with caplog.at_level(logging.WARNING, logger="spellbook.worker_llm.safety_cache"):
        safety_cache._load_from_disk()

    assert safety_cache._VERDICT_CACHE == {}
    assert safety_cache._BLOCK_CACHE == {}
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name == "spellbook.worker_llm.safety_cache"
    ]
    assert len(warnings) == 1
    assert "corrupt" in warnings[0].getMessage().lower()


def test_cache_file_with_missing_keys_tolerated(tmp_path, monkeypatch):
    """A partial cache file (missing 'verdicts' or 'blocks') must not crash;
    the missing section starts empty."""
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"verdicts": {}}))  # 'blocks' omitted
    monkeypatch.setattr(safety_cache, "CACHE_PATH", path)

    safety_cache._load_from_disk()
    assert safety_cache._VERDICT_CACHE == {}
    assert safety_cache._BLOCK_CACHE == {}


def test_on_disk_schema_shape(_isolate_cache, monkeypatch):
    """Disk schema: {"verdicts": {key: {verdict, reasoning, expires_at}},
    "blocks": {key: ts}}. Fixed so external tooling can read it."""
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 300.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)

    k = safety_cache.make_key("Bash", {})
    safety_cache.cache_verdict(k, SafetyVerdict(verdict="OK", reasoning="r"))
    safety_cache.record_block(k)

    on_disk = json.loads(_isolate_cache.read_text())
    assert set(on_disk.keys()) == {"verdicts", "blocks"}
    assert k in on_disk["verdicts"]
    assert set(on_disk["verdicts"][k].keys()) == {
        "verdict",
        "reasoning",
        "expires_at",
    }
    assert on_disk["verdicts"][k]["verdict"] == "OK"
    assert on_disk["verdicts"][k]["reasoning"] == "r"
    assert on_disk["verdicts"][k]["expires_at"] == 1_700_000_300.0
    assert on_disk["blocks"][k] == 1_700_000_000.0


def test_expired_entries_not_reloaded(tmp_path, monkeypatch):
    """A cache file with already-expired verdicts must not repopulate
    _VERDICT_CACHE — they are dead on arrival."""
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps(
            {
                "verdicts": {
                    "live": {
                        "verdict": "OK",
                        "reasoning": "",
                        "expires_at": 1_700_000_100.0,
                    },
                    "dead": {
                        "verdict": "OK",
                        "reasoning": "",
                        "expires_at": 1_000_000_000.0,
                    },
                },
                "blocks": {},
            }
        )
    )
    monkeypatch.setattr(safety_cache, "CACHE_PATH", path)
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)

    safety_cache._load_from_disk()
    assert "live" in safety_cache._VERDICT_CACHE
    assert "dead" not in safety_cache._VERDICT_CACHE


def test_cache_path_parent_created_on_write(tmp_path, monkeypatch):
    """First write creates the parent directory if it does not exist."""
    nested = tmp_path / "a" / "b" / "safety.json"
    monkeypatch.setattr(safety_cache, "CACHE_PATH", nested)
    monkeypatch.setattr(
        "spellbook.core.config.config_get",
        lambda k: 300.0 if k == "worker_llm_safety_cache_ttl_s" else None,
    )

    k = safety_cache.make_key("Bash", {})
    safety_cache.cache_verdict(k, SafetyVerdict(verdict="OK", reasoning=""))
    assert nested.exists()
