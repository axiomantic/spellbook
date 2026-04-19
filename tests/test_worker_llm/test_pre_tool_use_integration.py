"""Integration tests for the PreToolUse hook's worker-LLM tool_safety gate.

The PreToolUse handler (``hooks.spellbook_hook._handle_pre_tool_use``) gates
a safety-sniff call to the worker LLM on ``feature_tool_safety``. Behavior
contract:

- Feature off: byte-identical to the pre-worker-LLM path (no outputs added,
  no sys.exit).
- OK verdict: allow the tool; no output injection, no exit.
- WARN verdict: append a ``<worker-llm-tool-safety verdict="WARN">`` block
  to the hook outputs so the orchestrator surfaces the concern but still
  runs the tool.
- BLOCK verdict: emit a ``<worker-llm-tool-safety verdict="BLOCK">`` block
  on stderr and ``sys.exit(2)`` — Claude Code's blocking convention.
- Any worker error: FAIL OPEN (no injection, no exit, stderr notice).
- Cache-first: cached verdict is consulted BEFORE the worker call.
- 30s bypass: after a BLOCK, the next matching call within 30s bypasses the
  safety sniff entirely (no worker call, no exit).

See impl plan Task D2; design §5.2.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_enabled(monkeypatch):
    """Force memory.auto_recall True so the sibling path does not short-circuit."""

    def fake_config_value(key, default=None):
        if key in ("memory.auto_recall", "memory.auto_store"):
            return True
        return default

    monkeypatch.setattr(spellbook_hook, "_get_config_value", fake_config_value)


@pytest.fixture
def isolated_safety_cache(tmp_path, monkeypatch):
    """Scope the safety cache file to tmp_path so runs don't bleed state."""
    from spellbook.worker_llm import safety_cache as sc

    cache_path = tmp_path / "worker_llm_block.json"
    monkeypatch.setattr(sc, "CACHE_PATH", cache_path)
    sc._VERDICT_CACHE.clear()
    sc._BLOCK_CACHE.clear()
    yield sc
    sc._VERDICT_CACHE.clear()
    sc._BLOCK_CACHE.clear()


@pytest.fixture
def stub_memory_recall(monkeypatch):
    """Stub out _memory_recall_for_tool so it doesn't try HTTP."""
    monkeypatch.setattr(
        spellbook_hook, "_memory_recall_for_tool", lambda *a, **kw: None
    )


# ---------------------------------------------------------------------------
# Feature off (default / backwards-compat invariant)
# ---------------------------------------------------------------------------


class TestFeatureOff:
    def test_feature_off_is_byte_identical(
        self,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
        worker_llm_transport,
    ):
        # No worker_llm_config fixture -> feature_tool_safety returns False.
        seen = worker_llm_transport([])  # empty script; fail loudly if called

        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {
                "tool_input": {"command": "ls"},
                "cwd": "/repo/proj",
            },
        )

        assert out == []  # no warn block
        assert seen == []  # no HTTP calls


# ---------------------------------------------------------------------------
# OK / WARN / BLOCK verdict rendering
# ---------------------------------------------------------------------------


class TestVerdictRendering:
    def test_ok_verdict_allows_silently(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
    ):
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 200,
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            '{"verdict":"OK",'
                                            '"reasoning":"benign"}'
                                        )
                                    }
                                }
                            ]
                        },
                        "delay_s": 0.0,
                        "raise_on_send": None,
                    },
                )()
            ]
        )

        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {"tool_input": {"command": "ls"}, "cwd": "/repo/proj"},
        )
        assert all("worker-llm-tool-safety" not in o for o in out)

    def test_warn_verdict_appends_warning_block(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
    ):
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 200,
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            '{"verdict":"WARN",'
                                            '"reasoning":"touches /etc"}'
                                        )
                                    }
                                }
                            ]
                        },
                        "delay_s": 0.0,
                        "raise_on_send": None,
                    },
                )()
            ]
        )

        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {"tool_input": {"command": "cat /etc/passwd"}, "cwd": "/repo/proj"},
        )
        assert len(out) >= 1
        blob = "\n".join(out)
        assert '<worker-llm-tool-safety verdict="WARN">' in blob
        assert "touches /etc" in blob

    def test_block_verdict_exits_two(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
        capsys,
    ):
        # Use a command that does NOT trip the existing pre-worker _gate_bash
        # security filter (which already exits 2 on ``rm -rf /`` etc.). Our
        # BLOCK path is what we want to exercise here, not the pre-existing
        # static gate.
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 200,
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": (
                                            '{"verdict":"BLOCK",'
                                            '"reasoning":"suspicious curl | sh"}'
                                        )
                                    }
                                }
                            ]
                        },
                        "delay_s": 0.0,
                        "raise_on_send": None,
                    },
                )()
            ]
        )

        with pytest.raises(SystemExit) as ei:
            spellbook_hook._handle_pre_tool_use(
                "Bash",
                {
                    "tool_input": {"command": "echo piped"},
                    "cwd": "/repo/proj",
                },
            )
        assert ei.value.code == 2
        err = capsys.readouterr().err
        assert '<worker-llm-tool-safety verdict="BLOCK">' in err
        assert "suspicious curl | sh" in err


# ---------------------------------------------------------------------------
# Fail-open paths
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_connect_error_fails_open(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
        capsys,
    ):
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 0,
                        "body": "",
                        "delay_s": 0.0,
                        "raise_on_send": httpx.ConnectError("refused"),
                    },
                )()
            ]
        )

        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {"tool_input": {"command": "ls"}, "cwd": "/repo/proj"},
        )
        # Fail-open: no injection, no exit.
        assert all("worker-llm-tool-safety" not in o for o in out)

    def test_timeout_fails_open(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
    ):
        worker_llm_transport(
            [
                type(
                    "S",
                    (),
                    {
                        "status": 0,
                        "body": "",
                        "delay_s": 0.0,
                        "raise_on_send": httpx.ConnectTimeout("slow"),
                    },
                )()
            ]
        )
        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {"tool_input": {"command": "ls"}, "cwd": "/repo/proj"},
        )
        assert all("worker-llm-tool-safety" not in o for o in out)


# ---------------------------------------------------------------------------
# Cache-first
# ---------------------------------------------------------------------------


class TestCacheFirst:
    def test_cache_hit_skips_worker_call(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
    ):
        """Pre-populate cache with a WARN; transport is empty so a second call
        would raise ``script exhausted`` if we hit it. Verifies the cache is
        consulted BEFORE the worker.
        """
        from spellbook.worker_llm import safety_cache
        from spellbook.worker_llm.tasks.tool_safety import SafetyVerdict

        params = {"command": "ls"}
        key = safety_cache.make_key("Bash", params)
        safety_cache.cache_verdict(
            key, SafetyVerdict(verdict="WARN", reasoning="cached-warn-msg")
        )

        seen = worker_llm_transport([])  # no HTTP allowed
        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {"tool_input": params, "cwd": "/repo/proj"},
        )
        blob = "\n".join(out)
        assert '<worker-llm-tool-safety verdict="WARN">' in blob
        assert "cached-warn-msg" in blob
        assert seen == []  # no worker HTTP call


# ---------------------------------------------------------------------------
# 30-second bypass window
# ---------------------------------------------------------------------------


class TestBypassWindow:
    def test_recent_block_bypasses_worker(
        self,
        worker_llm_transport,
        worker_llm_config,
        config_enabled,
        stub_memory_recall,
        isolated_safety_cache,
    ):
        """After a recorded BLOCK, the next matching call bypasses the worker
        entirely (no HTTP, no sys.exit). The command here must NOT trip the
        pre-existing ``_gate_bash`` static filter — we are exercising the
        worker-LLM bypass path, not the fail-closed gate.
        """
        from spellbook.worker_llm import safety_cache

        params = {"command": "ls /tmp/x"}
        key = safety_cache.make_key("Bash", params)
        safety_cache.record_block(key)

        seen = worker_llm_transport([])  # no HTTP allowed
        out = spellbook_hook._handle_pre_tool_use(
            "Bash",
            {"tool_input": params, "cwd": "/repo/proj"},
        )
        # No BLOCK on the bypass path.
        assert all("worker-llm-tool-safety" not in o for o in out)
        assert seen == []
