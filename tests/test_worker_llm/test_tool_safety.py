"""Tests for ``spellbook.worker_llm.tasks.tool_safety``.

Covers: happy-path OK/WARN/BLOCK parsing, uppercase normalization,
fail-open on timeout, fail-open on connection error, fail-open on
malformed response, fail-open on invalid verdict string, short-timeout
forwarding, recent-context truncation, and SC1 cache read-through /
write-through behavior (no caching of fail-open results so a transient
worker outage does not poison the cache).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest


def _ok(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture(autouse=True)
def _reset_safety_cache():
    """Every tool_safety call reads/writes the module-global verdict and
    block caches; reset them between tests so each case is isolated."""
    from spellbook.worker_llm import safety_cache

    safety_cache._VERDICT_CACHE.clear()
    safety_cache._BLOCK_CACHE.clear()
    yield
    safety_cache._VERDICT_CACHE.clear()
    safety_cache._BLOCK_CACHE.clear()


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------


def test_parses_ok_verdict(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('{"verdict":"OK","reasoning":"safe call"}'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {"command": "ls"}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="safe call")


def test_parses_warn_verdict(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('{"verdict":"WARN","reasoning":"touches env"}'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {"command": "cat .env"}, "")
    assert v == SafetyVerdict(verdict="WARN", reasoning="touches env")


def test_parses_block_verdict(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('{"verdict":"BLOCK","reasoning":"rm -rf"}'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {"command": "rm -rf /"}, "")
    assert v == SafetyVerdict(verdict="BLOCK", reasoning="rm -rf")


def test_lowercase_verdict_normalized_to_upper(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('{"verdict":"ok","reasoning":"fine"}'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    assert tool_safety("Bash", {}, "") == SafetyVerdict(
        verdict="OK", reasoning="fine"
    )


def test_code_fence_wrapping_is_tolerated(
    worker_llm_transport, worker_llm_config
):
    fenced = '```json\n{"verdict":"OK","reasoning":"r"}\n```'
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(fenced))])

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    assert tool_safety("Bash", {}, "") == SafetyVerdict(
        verdict="OK", reasoning="r"
    )


# ---------------------------------------------------------------------------
# Fail-open: timeout, connect error, malformed response, invalid verdict
# ---------------------------------------------------------------------------


def test_timeout_fails_open(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.TimeoutException("slow"))]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {"command": "ls"}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")


def test_connect_error_fails_open(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.ConnectError("refused"))]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")


def test_non_json_response_fails_open(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok("not json at all"))]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")


def test_invalid_verdict_string_fails_open(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('{"verdict":"SAFE","reasoning":"nope"}'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    # "SAFE" is not in {OK, WARN, BLOCK}; fail open rather than raise so the
    # PreToolUse hook never accidentally blocks a user because a drifty model
    # spat out an unknown token.
    v = tool_safety("Bash", {}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")


def test_json_array_top_level_fails_open(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok("[1,2,3]"))]
    )

    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    v = tool_safety("Bash", {}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")


# ---------------------------------------------------------------------------
# Budget: short-timeout forwarding, recent-context truncation
# ---------------------------------------------------------------------------


def test_uses_short_tool_safety_timeout(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok('{"verdict":"OK","reasoning":""}'))]
    )

    seen_timeouts: list = []
    # Wrap httpx.AsyncClient to record the timeout each call uses.
    orig_init = httpx.AsyncClient.__init__

    def capture(self, *args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        return orig_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", capture)

    from spellbook.worker_llm.tasks.tool_safety import tool_safety

    tool_safety("Bash", {"command": "ls"}, "")
    assert seen_timeouts == [worker_llm_config["worker_llm_tool_safety_timeout_s"]]


def test_recent_context_trimmed_to_last_4kb(
    worker_llm_transport, worker_llm_config
):
    seen = worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok('{"verdict":"OK","reasoning":""}'))]
    )

    # 10 KB of context; only last 4 KB should be sent.
    huge = "AB" * 5000  # 10 000 chars
    expected_tail = huge[-4000:]

    from spellbook.worker_llm.tasks.tool_safety import tool_safety

    tool_safety("Bash", {"command": "ls"}, huge)

    body = json.loads(seen[0].content.decode())
    user_msg = json.loads(body["messages"][1]["content"])
    assert user_msg["recent_context"] == expected_tail
    assert len(user_msg["recent_context"]) == 4000


# ---------------------------------------------------------------------------
# SC1 cache integration: read-through + write-through; no-cache-on-fail-open
# ---------------------------------------------------------------------------


def test_cache_hit_short_circuits_without_http(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    """A cached verdict MUST return directly without touching httpx."""
    seen = worker_llm_transport([])  # empty script — any call would raise

    from spellbook.worker_llm import safety_cache
    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    cached = SafetyVerdict(verdict="WARN", reasoning="cached")

    def fake_get(key: str) -> SafetyVerdict | None:
        return cached

    monkeypatch.setattr(safety_cache, "get_cached_verdict", fake_get)

    v = tool_safety("Bash", {"command": "ls"}, "")
    assert v == cached
    assert seen == []


def test_cache_miss_writes_through_on_success(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('{"verdict":"BLOCK","reasoning":"destructive"}'),
            )
        ]
    )

    from spellbook.worker_llm import safety_cache
    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    monkeypatch.setattr(safety_cache, "get_cached_verdict", lambda k: None)
    writes: list = []
    monkeypatch.setattr(
        safety_cache,
        "cache_verdict",
        lambda k, v: writes.append((k, v)),
    )

    v = tool_safety("Bash", {"command": "rm"}, "")
    assert v == SafetyVerdict(verdict="BLOCK", reasoning="destructive")
    assert len(writes) == 1
    k, stored = writes[0]
    assert stored == v
    # Key must be the SC1-computed key for the same inputs.
    assert k == safety_cache.make_key("Bash", {"command": "rm"})


def test_fail_open_result_is_not_cached(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    """Transient worker errors MUST NOT poison the cache with a fail-open OK."""
    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.TimeoutException("slow"))]
    )

    from spellbook.worker_llm import safety_cache
    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    monkeypatch.setattr(safety_cache, "get_cached_verdict", lambda k: None)
    writes: list = []
    monkeypatch.setattr(
        safety_cache,
        "cache_verdict",
        lambda k, v: writes.append((k, v)),
    )

    v = tool_safety("Bash", {"command": "ls"}, "")
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")
    assert writes == []  # nothing cached — transient error
