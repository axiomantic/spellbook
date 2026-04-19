"""Hybrid in-process/subprocess event publisher for worker-LLM calls.

``spellbook.admin.events.publish_sync`` only succeeds when a daemon event loop
is running in the same process. Hook subprocesses, MCP stdio workers, and CLI
invocations have no loop, so their events are silently dropped unless we route
them over HTTP to the daemon.

This module detects its own runtime via the ``event_bus._in_daemon`` marker:

- Daemon (loop present)  -> ``publish_sync`` directly.
- Subprocess (no loop)   -> POST ``{subsystem, event_type, data}`` to the
                            daemon's ``/api/events/publish`` endpoint.

The daemon endpoint re-invokes ``publish_sync`` from inside its running loop,
where it works correctly. See design doc §2.5 for the full rationale.
"""

from __future__ import annotations

import logging
import os

from spellbook.admin.events import Event, Subsystem, event_bus, publish_sync

logger = logging.getLogger(__name__)


def _in_daemon_process() -> bool:
    """True iff this process is the spellbook daemon (has a running loop).

    The FastAPI lifespan handler for ``create_admin_app`` sets
    ``event_bus._in_daemon = True`` at startup. Any other caller leaves it
    False and treats itself as a subprocess.
    """
    return bool(getattr(event_bus, "_in_daemon", False))


def _fallback_http_post(path: str, payload: dict, timeout: float = 1.0) -> None:
    """Minimal urllib POST used when ``hooks.spellbook_hook`` is unavailable.

    Default port is ``"8765"`` — matches ``hooks/spellbook_hook.py:34``
    ``MCP_PORT`` and every other ``SPELLBOOK_MCP_PORT`` default in the repo.
    Fire-and-forget: all exceptions are swallowed and logged at DEBUG.
    """
    import json as _json
    import urllib.request

    host = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
    port = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
    url = f"http://{host}:{port}{path}"
    try:
        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout):
            pass
    except Exception:
        # Never propagate: event publishing is best-effort.
        logger.debug(
            "worker_llm event publish failed (subprocess fallback)",
            exc_info=True,
        )


def _publish_via_daemon(subsystem: str, event_type: str, data: dict) -> None:
    """POST to the daemon's event-publish endpoint. Fire-and-forget.

    Prefers ``hooks.spellbook_hook._http_post`` when available (it owns
    MCP_HOST/MCP_PORT discovery and shares retry semantics with the rest of
    the hook path). Falls back to urllib otherwise.
    """
    try:
        from hooks.spellbook_hook import _http_post  # noqa: WPS433
    except Exception:
        _http_post = _fallback_http_post

    _http_post(
        "/api/events/publish",
        {"subsystem": subsystem, "event_type": event_type, "data": data},
        timeout=1.0,
    )


def _publish(subsystem: Subsystem, event_type: str, data: dict) -> None:
    """In-process publish when daemon; HTTP publish when subprocess."""
    if _in_daemon_process():
        publish_sync(Event(subsystem=subsystem, event_type=event_type, data=data))
        return
    _publish_via_daemon(subsystem.value, event_type, data)


def publish_call(
    task: str,
    model: str,
    latency_ms: int,
    status: str,
    prompt_len: int,
    response_len: int,
    error: str | None = None,
    override_loaded: bool = False,
) -> None:
    """Emit a ``call_ok`` or ``call_failed`` event for a worker-LLM invocation.

    Always safe to call from any context (daemon, hook subprocess, CLI).
    Event routing is decided per-call by inspecting the daemon marker.
    """
    _publish(
        Subsystem.WORKER_LLM,
        "call_failed" if error else "call_ok",
        {
            "task": task,
            "model": model,
            "latency_ms": latency_ms,
            "status": status,
            "prompt_len": prompt_len,
            "response_len": response_len,
            "error": error,
            "override_loaded": override_loaded,
        },
    )


def publish_override_loaded(task: str, path: str) -> None:
    """Emit an ``override_loaded`` event when a user override prompt is used."""
    _publish(
        Subsystem.WORKER_LLM,
        "override_loaded",
        {"task": task, "path": path},
    )
