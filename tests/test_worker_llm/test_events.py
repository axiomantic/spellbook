"""Tests for ``spellbook.worker_llm.events`` hybrid publisher."""

import sys
from unittest.mock import patch

from spellbook.admin.events import Subsystem, event_bus
from spellbook.worker_llm import events as wl_events


def test_in_daemon_uses_publish_sync(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    with patch("spellbook.worker_llm.events.publish_sync") as pm:
        wl_events.publish_call(
            task="t",
            model="m",
            latency_ms=1,
            status="ok",
            prompt_len=1,
            response_len=1,
        )
    assert pm.call_count == 1
    evt = pm.call_args.args[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "call_ok"
    assert evt.data == {
        "task": "t",
        "model": "m",
        "latency_ms": 1,
        "status": "ok",
        "prompt_len": 1,
        "response_len": 1,
        "error": None,
        "override_loaded": False,
    }


def test_in_daemon_publishes_override_loaded(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    with patch("spellbook.worker_llm.events.publish_sync") as pm:
        wl_events.publish_override_loaded(task="tool_safety", path="/tmp/x.md")
    assert pm.call_count == 1
    evt = pm.call_args.args[0]
    assert evt.subsystem == Subsystem.WORKER_LLM
    assert evt.event_type == "override_loaded"
    assert evt.data == {"task": "tool_safety", "path": "/tmp/x.md"}


def test_error_emits_call_failed_event(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", True)
    with patch("spellbook.worker_llm.events.publish_sync") as pm:
        wl_events.publish_call(
            task="t",
            model="m",
            latency_ms=42,
            status="WorkerLLMTimeout",
            prompt_len=100,
            response_len=0,
            error="boom",
            override_loaded=True,
        )
    evt = pm.call_args.args[0]
    assert evt.event_type == "call_failed"
    assert evt.data == {
        "task": "t",
        "model": "m",
        "latency_ms": 42,
        "status": "WorkerLLMTimeout",
        "prompt_len": 100,
        "response_len": 0,
        "error": "boom",
        "override_loaded": True,
    }


def test_subprocess_posts_to_daemon(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", False)
    calls: list = []

    def fake_post(path, payload, timeout=1.0):
        calls.append((path, payload, timeout))

    monkeypatch.setattr(wl_events, "_fallback_http_post", fake_post)
    # Force the lazy import of hooks.spellbook_hook to fail so the fallback
    # helper is the one invoked.
    monkeypatch.setitem(sys.modules, "hooks.spellbook_hook", None)
    wl_events.publish_call(
        task="t",
        model="m",
        latency_ms=1,
        status="err",
        prompt_len=1,
        response_len=0,
        error="boom",
    )
    assert len(calls) == 1
    path, payload, timeout = calls[0]
    assert path == "/api/events/publish"
    assert timeout == 1.0
    assert payload == {
        "subsystem": "worker_llm",
        "event_type": "call_failed",
        "data": {
            "task": "t",
            "model": "m",
            "latency_ms": 1,
            "status": "err",
            "prompt_len": 1,
            "response_len": 0,
            "error": "boom",
            "override_loaded": False,
        },
    }


def test_subprocess_override_loaded_posts_to_daemon(monkeypatch):
    monkeypatch.setattr(event_bus, "_in_daemon", False)
    calls: list = []

    monkeypatch.setattr(
        wl_events,
        "_fallback_http_post",
        lambda path, payload, timeout=1.0: calls.append((path, payload, timeout)),
    )
    monkeypatch.setitem(sys.modules, "hooks.spellbook_hook", None)
    wl_events.publish_override_loaded(task="transcript_harvest", path="/u/x.md")
    assert calls == [
        (
            "/api/events/publish",
            {
                "subsystem": "worker_llm",
                "event_type": "override_loaded",
                "data": {"task": "transcript_harvest", "path": "/u/x.md"},
            },
            1.0,
        )
    ]


def test_fallback_http_post_defaults_to_port_8765(monkeypatch):
    # Clear any env var leakage, then simulate urllib to capture URL.
    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)
    monkeypatch.delenv("SPELLBOOK_MCP_HOST", raising=False)

    captured: list = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=1.0):
        captured.append((req.full_url, timeout))
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    wl_events._fallback_http_post("/api/events/publish", {"x": 1}, timeout=1.0)
    assert captured == [("http://127.0.0.1:8765/api/events/publish", 1.0)]


def test_fallback_http_post_respects_env_overrides(monkeypatch):
    monkeypatch.setenv("SPELLBOOK_MCP_HOST", "example.local")
    monkeypatch.setenv("SPELLBOOK_MCP_PORT", "12345")

    captured: list = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=1.0):
        captured.append(req.full_url)
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    wl_events._fallback_http_post("/p", {"x": 1}, timeout=1.0)
    assert captured == ["http://example.local:12345/p"]


def test_fallback_http_post_swallows_all_exceptions(monkeypatch):
    monkeypatch.delenv("SPELLBOOK_MCP_PORT", raising=False)

    def raising_urlopen(*a, **kw):
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr("urllib.request.urlopen", raising_urlopen)
    # Must not raise.
    wl_events._fallback_http_post("/p", {"x": 1}, timeout=1.0)
