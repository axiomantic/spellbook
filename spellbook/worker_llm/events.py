"""Hybrid in-process/subprocess event publisher for worker-LLM calls.

``spellbook.admin.events.publish_sync`` only succeeds when a daemon event loop
is running in the same process. Hook subprocesses, MCP stdio workers, and CLI
invocations have no loop, so their events are silently dropped unless we route
them over HTTP to the daemon.

This module detects its own runtime via the ``event_bus._in_daemon`` marker:

- Daemon (loop present)  -> ``publish_sync`` directly.
- Subprocess (no loop)   -> POST ``{subsystem, event_type, data}`` to the
                            daemon's ``/api/events/publish`` endpoint.

The daemon endpoint re-invokes ``event_bus.publish`` from inside its running
loop, where it works correctly. See design doc §2.5 for the full rationale.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

from spellbook.admin.events import Event, Subsystem, event_bus, publish_sync
from spellbook.worker_llm.auth import _load_bearer_token
from spellbook.worker_llm.observability import record_call

logger = logging.getLogger(__name__)


def _spawn_background(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run ``fn`` without blocking a running event loop.

    If a loop is running in the current thread, offload ``fn`` to the default
    executor via ``loop.run_in_executor`` and DO NOT await the returned future
    (fire-and-forget). If no loop is running, call ``fn`` directly on the
    current thread -- subprocess callers, CLI, and sync test paths go through
    this branch.

    Exceptions raised by ``fn`` are swallowed both when the loop is running
    (via the wrapper closure below) and when it is not (try/except around the
    direct call). Observability writes must never surface through the caller:
    the worker-LLM call and the hook dispatcher already committed their
    user-visible side effects by the time we reach this helper.

    ``record_call`` (worker_llm events) and ``record_hook_event`` (hook
    events) must never run inline on the daemon event loop: SQLite writer-lock
    contention under load would block the loop for the duration of the write.
    This helper is the shared off-ramp that keeps those sync DB writes off
    the async path.
    """
    def _safe_call() -> None:
        try:
            fn(*args, **kwargs)
        except Exception:
            # Best-effort: swallow every exception. ``fn`` is expected to
            # also have its own first-loud-then-debug log policy (see
            # ``record_call`` / ``record_hook_event``); we just guarantee
            # nothing escapes ``_spawn_background``.
            logger.debug(
                "_spawn_background: suppressed exception from %s",
                getattr(fn, "__name__", repr(fn)),
                exc_info=True,
            )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop on this thread: run synchronously. This keeps
        # subprocess callers, the CLI, and non-async tests on the original
        # fast path where the write completes before the call returns.
        _safe_call()
        return

    # Fire-and-forget: we DO NOT store the Future. The default executor
    # holds its own reference to the submitted work via its internal queue,
    # so the callable will run regardless. Any exception is swallowed inside
    # ``_safe_call`` so there is no "exception never retrieved" warning.
    loop.run_in_executor(None, _safe_call)

# Module-level counter so we can emit a single loud warning on the first
# subprocess publish failure per process, then fall back to DEBUG for the
# rest. Rationale: subprocess event publish is best-effort (fire-and-forget),
# so we do not want to spam logs, but silent failures have historically
# masked route-mismatch bugs. One warning is enough to make the
# misconfiguration loud.
_publish_failures: int = 0


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
    Attaches the bearer token (when available) so this path clears
    ``BearerAuthMiddleware`` — the ``/api/events/publish`` route lives at the
    MCP root, not under the cookie-auth ``/admin`` mount.

    Fire-and-forget: all exceptions are swallowed. The FIRST failure in a
    given process is logged at WARNING (so route-mismatch / auth bugs are
    loud); subsequent failures drop to DEBUG to avoid log flooding.
    """
    import json as _json
    import urllib.request

    global _publish_failures

    host = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
    port = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
    url = f"http://{host}:{port}{path}"
    headers = {"Content-Type": "application/json"}
    token = _load_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(
            url,
            data=_json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout):
            pass
    except Exception as exc:
        # Never propagate: event publishing is best-effort.
        if _publish_failures == 0:
            logger.warning(
                "worker_llm event publish failed (subprocess fallback): "
                "%s posting to %s: %s. Further failures will be logged at DEBUG.",
                type(exc).__name__,
                url,
                exc,
            )
        else:
            logger.debug(
                "worker_llm event publish failed (subprocess fallback) "
                "to %s",
                url,
                exc_info=True,
            )
        _publish_failures += 1


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
    """Emit a ``call_ok``, ``call_failed``, or ``call_fail_open`` event for a worker-LLM invocation.

    Always safe to call from any context (daemon, hook subprocess, CLI).
    Event routing is decided per-call by inspecting the daemon marker.
    """
    if status == "fail_open":
        event_type = "call_fail_open"
    elif error:
        event_type = "call_failed"
    else:
        event_type = "call_ok"
    _publish(
        Subsystem.WORKER_LLM,
        event_type,
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
    # Fire-and-forget persistent log — daemon path only. Subprocess callers
    # re-enter via ``/api/events/publish`` which has its own ``record_call``
    # invocation; gating on ``_in_daemon_process`` here prevents a
    # double-insert. ``record_call`` already swallows exceptions internally,
    # but ``_spawn_background`` adds a second safety net so a future refactor
    # that removes that guard still cannot propagate an exception out of
    # ``publish_call`` — the LLM call must never be blocked by observability.
    #
    # ``record_call`` is a synchronous SQLite write; calling it inline from a
    # coroutine would block the daemon event loop for the duration of the
    # write. ``_spawn_background`` offloads to ``loop.run_in_executor`` when
    # a loop is running and falls back to a direct sync call otherwise.
    if _in_daemon_process():
        _spawn_background(
            record_call,
            task=task,
            model=model,
            latency_ms=latency_ms,
            status=status,
            prompt_len=prompt_len,
            response_len=response_len,
            error=error,
            override_loaded=override_loaded,
        )


def publish_override_loaded(task: str, path: str) -> None:
    """Emit an ``override_loaded`` event when a user override prompt is used."""
    _publish(
        Subsystem.WORKER_LLM,
        "override_loaded",
        {"task": task, "path": path},
    )


def publish_hook_integration(
    task: str,
    mode: str,
    candidate_count: int,
    duration_ms: int,
    status: str,
    error: str | None = None,
) -> None:
    """Emit a ``hook_integration`` event summarizing a hook-side worker run.

    Unlike ``publish_call`` (one event per HTTP call), this event summarizes
    the hook's overall outcome — including mode (``replace``/``merge``/``skip``),
    the number of candidates produced (post-dedup), and the total duration
    including merge / cache / POST work. Emitting ONE summary event per hook
    invocation keeps the admin EventMonitorPage free of per-call noise while
    preserving the coarse-grained "did the feature fire and with what result"
    signal operators actually want.

    Args:
        task: ``"transcript_harvest"`` | ``"tool_safety"`` | ...
        mode: Mode string for transcript_harvest; ``""`` for flag-toggle tasks.
        candidate_count: Number of artifacts produced (candidates posted /
            verdict count / rerank items). ``-1`` when not applicable.
        duration_ms: Wall-clock duration of the full hook integration step.
        status: ``"ok"`` | ``"worker_error"`` | ``"partial"`` | ``"bypass"``.
        error: Exception type name if ``status != "ok"``; else None.
    """
    _publish(
        Subsystem.WORKER_LLM,
        "hook_integration",
        {
            "task": task,
            "mode": mode,
            "candidate_count": candidate_count,
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
        },
    )


def publish_fail_open(task: str, reason: str, error: str) -> None:
    """Emit a ``fail_open`` event when a task bails before calling the worker.

    The in-client fail-open paths (timeout, connect error, bad response) all
    get their ``call_failed`` event via ``client.call``'s ``finally`` block.
    But fail-open branches that short-circuit BEFORE reaching the client —
    notably ``tool_safety``'s prompt-loader catch — never hit that finally.
    Without this helper those fail-opens are invisible to the admin UI.

    Args:
        task: Observability tag (e.g. ``"tool_safety"``).
        reason: Short machine-readable reason (e.g. ``"prompt_load_error"``).
        error: Human-readable error string (``str(exc)``).
    """
    _publish(
        Subsystem.WORKER_LLM,
        "fail_open",
        {"task": task, "reason": reason, "error": error},
    )
