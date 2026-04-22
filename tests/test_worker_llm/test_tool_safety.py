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
def _reset_safety_cache(tmp_path, monkeypatch):
    """Every tool_safety call reads/writes the module-global verdict and
    block caches, and cache_verdict/record_block persist those caches to
    ``safety_cache.CACHE_PATH``. Without monkeypatching ``CACHE_PATH`` to
    a tmp path, these tests would write to the user's real
    ``~/.local/spellbook/cache/worker_llm_block.json`` and pollute user
    state. Pattern mirrors ``test_safety_cache.py::_isolate_cache``.
    """
    from spellbook.worker_llm import safety_cache

    monkeypatch.setattr(safety_cache, "CACHE_PATH", tmp_path / "safety.json")
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

    # The shared client has a generous constructor timeout; per-call
    # overrides are passed to ``post``. Capture the ``timeout`` kwarg on
    # each post call to assert the tool_safety override is forwarded.
    #
    # Intentional monkeypatch on a callable: ``bigfoot.spy.object`` on an
    # async class method (httpx.AsyncClient.post) is not cleanly
    # supported — the spy wraps the bound method lookup path but the
    # interaction is not recorded on the verifier's timeline under the
    # source_id the spy expects. Until bigfoot exposes a first-class
    # "record-only" interceptor for async class methods, this test
    # keeps the narrow post-level monkeypatch. The conftest HTTP
    # mocking is fully on bigfoot.http; this is the one remaining
    # call-site patch in the worker_llm suite.
    seen_timeouts: list = []
    orig_post = httpx.AsyncClient.post

    async def capture(self, *args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        return await orig_post(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", capture)

    from spellbook.worker_llm.tasks.tool_safety import tool_safety

    tool_safety("Bash", {"command": "ls"}, "")
    assert seen_timeouts == [worker_llm_config["worker_llm_tool_safety_timeout_s"]]


def test_recent_context_trimmed_to_last_window(
    worker_llm_transport, worker_llm_config
):
    seen = worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok('{"verdict":"OK","reasoning":""}'))]
    )

    from spellbook.worker_llm.tasks import tool_safety as ts_mod
    from spellbook.worker_llm.tasks.tool_safety import tool_safety

    window = ts_mod._RECENT_CONTEXT_BYTES
    huge = "AB" * (window * 2)  # ~4x the cap
    expected_tail = huge[-window:]

    tool_safety("Bash", {"command": "ls"}, huge)

    body = json.loads(seen[0].content.decode())
    user_msg = json.loads(body["messages"][1]["content"])
    assert user_msg["recent_context"] == expected_tail
    assert len(user_msg["recent_context"]) == window


def test_oversized_param_strings_are_head_tail_trimmed(
    worker_llm_transport, worker_llm_config
):
    seen = worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok('{"verdict":"OK","reasoning":""}'))]
    )

    from spellbook.worker_llm.tasks import tool_safety as ts_mod
    from spellbook.worker_llm.tasks.tool_safety import tool_safety

    cap = ts_mod._PARAM_VALUE_CAP
    head_tail = ts_mod._PARAM_VALUE_HEAD_TAIL
    huge_content = ("H" * head_tail) + ("M" * (cap * 5)) + ("T" * head_tail)

    tool_safety(
        "Write",
        {"file_path": "/tmp/x.py", "content": huge_content},
        "",
    )

    body = json.loads(seen[0].content.decode())
    user_msg = json.loads(body["messages"][1]["content"])
    content = user_msg["tool_params"]["content"]
    # Short values are untouched.
    assert user_msg["tool_params"]["file_path"] == "/tmp/x.py"
    # Long value keeps head + tail and declares the elision.
    assert content.startswith("H" * head_tail)
    assert content.endswith("T" * head_tail)
    assert "chars elided" in content
    # Non-string params pass through unchanged.
    assert ts_mod._trim_param_value(True) is True
    assert ts_mod._trim_param_value(42) == 42


def test_trim_does_not_affect_cache_key(worker_llm_transport, worker_llm_config):
    """Trimming is display-only: caching still keys off the real tool_params."""
    from spellbook.worker_llm import safety_cache
    from spellbook.worker_llm.tasks import tool_safety as ts_mod

    cap = ts_mod._PARAM_VALUE_CAP
    big = "X" * (cap * 3)
    params_real = {"file_path": "/tmp/x.py", "content": big}

    key_real = safety_cache.make_key("Write", params_real)
    key_trimmed = safety_cache.make_key(
        "Write", ts_mod._trim_params_for_prompt(params_real)
    )
    assert key_real != key_trimmed, (
        "If trimming changed the cache key, two distinct large writes "
        "would alias to the same cached verdict."
    )


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


# ---------------------------------------------------------------------------
# Observability: prompt-load failure emits a fail_open event
# ---------------------------------------------------------------------------


def test_prompt_load_error_emits_fail_open_event(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    """A prompt-loader failure short-circuits BEFORE ``client.call`` runs, so
    the ``call_failed`` event from ``client.call``'s finally-block never
    fires. The branch must emit its own ``publish_call(status='fail_open')``
    so this failure mode is visible to the admin UI. The event_type routes
    to ``call_fail_open`` per Step 4 of the observability impl plan."""
    worker_llm_transport([])  # any HTTP call would raise — should not be reached

    from spellbook.worker_llm import prompts
    from spellbook.worker_llm.tasks import tool_safety as tool_safety_mod
    from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict, tool_safety

    def boom(_task):
        raise FileNotFoundError("packaging bug: tool_safety.md missing")

    monkeypatch.setattr(prompts, "load", boom)

    captured: list = []

    def fake_publish_call(
        task,
        model,
        latency_ms,
        status,
        prompt_len,
        response_len,
        error=None,
        override_loaded=False,
    ):
        captured.append(
            {
                "task": task,
                "model": model,
                "latency_ms": latency_ms,
                "status": status,
                "prompt_len": prompt_len,
                "response_len": response_len,
                "error": error,
                "override_loaded": override_loaded,
            }
        )

    monkeypatch.setattr(tool_safety_mod, "publish_call", fake_publish_call)

    v = tool_safety("Bash", {"command": "ls"}, "")
    # Still fails open — user action is not blocked.
    assert v == SafetyVerdict(verdict="OK", reasoning="error; fail-open")
    # But the fail-open is observable via publish_call(status='fail_open'),
    # which routes to event_type='call_fail_open' (see events.py:publish_call).
    assert captured == [
        {
            "task": "tool_safety",
            "model": "",
            "latency_ms": 0,
            "status": "fail_open",
            "prompt_len": 0,
            "response_len": 0,
            "error": "prompt_load_error: packaging bug: tool_safety.md missing",
            "override_loaded": False,
        }
    ]
