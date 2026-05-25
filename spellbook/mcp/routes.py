"""HTTP custom routes for the MCP server.

Registers REST endpoints via @mcp.custom_route() for use by hook scripts
and monitoring tools that need HTTP access without full MCP protocol.
"""

import asyncio
import logging
import time
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Project imports must follow logger setup so they pick up the configured logger.
from spellbook.core.path_utils import get_spellbook_config_dir  # noqa: E402
from spellbook.mcp import state as _state  # noqa: E402
from spellbook.mcp.server import mcp  # noqa: E402


def _get_version() -> str:
    """Read version from .version file."""
    import os
    from pathlib import Path

    try:
        version_path = Path(__file__).parent.parent.parent / ".version"
        if version_path.exists():
            return version_path.read_text(encoding="utf-8").strip()

        spellbook_dir = os.environ.get("SPELLBOOK_DIR")
        if spellbook_dir:
            version_path = Path(spellbook_dir) / ".version"
            if version_path.exists():
                return version_path.read_text(encoding="utf-8").strip()

        return "unknown"
    except OSError:
        return "unknown"


@mcp.custom_route("/health", methods=["GET"])
async def api_health(request: Request) -> JSONResponse:
    """Lightweight health check endpoint for the installer and monitoring.

    Returns JSON: {"status": "ok", "version": "...", "uptime_seconds": ...}
    """
    return JSONResponse({
        "status": "ok",
        "version": _get_version(),
        "uptime_seconds": round(time.time() - _state.server_start_time, 1),
    })


# ---------------------------------------------------------------------------
# Hook log rotation (moved from hooks/spellbook_hook.py)
# ---------------------------------------------------------------------------

_HOOK_LOG_MAX_BYTES = 1_000_000  # 1 MB
_HOOK_LOG_BACKUP_COUNT = 3
_hook_log_lock = asyncio.Lock()


def _rotate_hook_log(log_file: Path) -> None:
    """Rotate hook log file if it exceeds _HOOK_LOG_MAX_BYTES.

    Keeps up to _HOOK_LOG_BACKUP_COUNT backups: hook-errors.log.1, .2, .3.
    Must be called while holding _hook_log_lock.
    """
    try:
        if not log_file.exists() or log_file.stat().st_size < _HOOK_LOG_MAX_BYTES:
            return
        for i in range(_HOOK_LOG_BACKUP_COUNT, 0, -1):
            if i == _HOOK_LOG_BACKUP_COUNT:
                src = log_file.with_suffix(f".log.{i}")
                if src.exists():
                    src.unlink()
            else:
                src = log_file.with_suffix(f".log.{i}")
                dst = log_file.with_suffix(f".log.{i + 1}")
                if src.exists():
                    src.replace(dst)
        log_file.replace(log_file.with_suffix(".log.1"))
    except OSError:
        pass  # Best-effort rotation


@mcp.custom_route("/api/hook-log", methods=["POST"])
async def api_hook_log(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to log errors via the daemon.

    Accepts JSON body: {"timestamp": "ISO string", "event": "string", "traceback": "string"}
    Returns JSON: {"ok": true} on success.

    The daemon writes to ~/.local/spellbook/logs/hook-errors.log with
    rotation, eliminating the need for hook processes to have write access
    to the config directory.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    timestamp = body.get("timestamp", "")
    event = body.get("event", "")
    tb = body.get("traceback", "")

    if not event:
        return JSONResponse({"error": "missing required field: event"}, status_code=400)

    log_dir = get_spellbook_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "hook-errors.log"

    def _write_log(path: Path, text: str) -> None:
        _rotate_hook_log(path)
        with open(path, "a") as f:
            f.write(text)

    entry = f"\n{'=' * 60}\n{timestamp}\n{event}\n{tb}"
    async with _hook_log_lock:
        await asyncio.to_thread(_write_log, log_file, entry)

    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Worker-LLM async enqueue (subprocess fallback for spellbook.worker_llm.queue)
# ---------------------------------------------------------------------------


@mcp.custom_route("/api/worker-llm/enqueue", methods=["POST"])
async def api_worker_llm_enqueue(request: Request) -> JSONResponse:
    """Accept a fire-and-forget worker-LLM task from a hook subprocess.

    The async queue lives in-daemon only (see
    ``spellbook.worker_llm.queue``). Hook subprocesses have no running
    event loop, so they POST here and the daemon enqueues on their behalf.

    Route co-lives with ``/api/events/publish`` at the MCP root so
    ``BearerAuthMiddleware`` authenticates it without going through the
    admin cookie mount.

    Accepts JSON body:
        {
          "task_name": str,  # required; e.g. "tool_safety"
          "prompt": str,     # required; user_prompt for the worker call
          "context": dict    # optional; opaque context forwarded to the
                             # consumer callback via WorkerTask.context
        }

    Returns:
        - 202 ``{"ok": true, "dropped": false}`` when queued.
        - 202 ``{"ok": true, "dropped": true}`` when queued with drop-oldest.
        - 503 when ``worker_llm_queue_enabled`` is False or the queue is
          not running in this process.
        - 400 on missing/invalid fields.

    The 202 status signals "accepted, not yet processed" which matches the
    fire-and-forget contract: callers must not wait for the underlying
    worker call to finish.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    task_name = body.get("task_name")
    prompt = body.get("prompt")
    if not isinstance(task_name, str) or not task_name:
        return JSONResponse(
            {"error": "missing or invalid 'task_name'"}, status_code=400
        )
    if not isinstance(prompt, str):
        return JSONResponse(
            {"error": "missing or invalid 'prompt'"}, status_code=400
        )
    raw_context = body.get("context")
    if raw_context is not None and not isinstance(raw_context, dict):
        return JSONResponse(
            {"error": "field 'context' must be an object"}, status_code=400
        )
    context = raw_context or {}

    from spellbook.core.config import config_get as _config_get
    from spellbook.worker_llm import queue as _queue

    if not _config_get("worker_llm_queue_enabled"):
        return JSONResponse(
            {"error": "worker_llm_queue_enabled is False"}, status_code=503
        )
    if not _queue.is_available():
        return JSONResponse(
            {"error": "worker_llm queue is not running"}, status_code=503
        )

    # Dispatch to a task-aware consumer callback when one is registered.
    # No task currently registers a consumer-side callback; tasks enqueue
    # with ``callback=None`` and rely on ``client.call``'s event emission
    # for observability.
    callback = _resolve_task_callback(task_name)

    try:
        queued = await _queue.enqueue(
            task_name, prompt, callback=callback, context=context
        )
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)

    # 202 Accepted: queued, not yet processed. ``dropped`` reflects the
    # drop-oldest eviction; callers may log it.
    return JSONResponse(
        {"ok": True, "dropped": not queued}, status_code=202
    )


def _resolve_task_callback(task_name: str):
    """Return the consumer-side callback for ``task_name`` or ``None``.

    No task currently registers a consumer-side callback, so this always
    returns ``None``. The indirection is retained so a future task that
    needs a custom consumer can lazy-import its handler here without
    pulling every task module in at registration time.
    """
    return None


# ---------------------------------------------------------------------------
# Worker-LLM event publish (subprocess fallback for spellbook.worker_llm.events)
# ---------------------------------------------------------------------------


@mcp.custom_route("/api/hooks/record", methods=["POST"])
async def api_hooks_record(request: Request) -> JSONResponse:
    """Persist a hook dispatcher invocation into ``hook_events``.

    Subprocess hook scripts (``hooks/spellbook_hook.py`` etc.) have no
    running event loop, so they POST here and the daemon writes the row
    on their behalf. Co-lives with ``/api/events/publish`` at the MCP
    root so ``BearerAuthMiddleware`` authenticates it.

    Accepts JSON body:
        {
          "hook_name": str,     # required; <=128 chars
          "event_name": str,    # required; <=128 chars
          "tool_name": str,     # optional; <=128 chars
          "duration_ms": int,   # required; >=0
          "exit_code": int,     # required
          "error": str,         # optional; <=1000 chars
          "notes": str          # optional; <=4000 chars
        }

    Returns:
        - 202 ``{"ok": true}`` when accepted.
        - 400 on missing/invalid fields.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    hook_name = body.get("hook_name")
    event_name = body.get("event_name")
    duration_ms = body.get("duration_ms")
    exit_code = body.get("exit_code")
    tool_name = body.get("tool_name")
    error = body.get("error")
    notes = body.get("notes")

    if not isinstance(hook_name, str) or not hook_name or len(hook_name) > 128:
        return JSONResponse(
            {"error": "missing or invalid 'hook_name' (1..128 chars)"},
            status_code=400,
        )
    if not isinstance(event_name, str) or not event_name or len(event_name) > 128:
        return JSONResponse(
            {"error": "missing or invalid 'event_name' (1..128 chars)"},
            status_code=400,
        )
    if tool_name is not None:
        if not isinstance(tool_name, str) or len(tool_name) > 128:
            return JSONResponse(
                {"error": "invalid 'tool_name' (<=128 chars or null)"},
                status_code=400,
            )
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms < 0:
        return JSONResponse(
            {"error": "missing or invalid 'duration_ms' (non-negative int)"},
            status_code=400,
        )
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return JSONResponse(
            {"error": "missing or invalid 'exit_code' (int)"},
            status_code=400,
        )
    if error is not None:
        if not isinstance(error, str) or len(error) > 1000:
            return JSONResponse(
                {"error": "invalid 'error' (<=1000 chars or null)"},
                status_code=400,
            )
    if notes is not None:
        if not isinstance(notes, str) or len(notes) > 4000:
            return JSONResponse(
                {"error": "invalid 'notes' (<=4000 chars or null)"},
                status_code=400,
            )

    try:
        from spellbook.hooks.observability import record_hook_event
        from spellbook.worker_llm.events import _spawn_background

        # ``record_hook_event`` runs a synchronous SQLite INSERT; calling
        # it directly from this async handler would hold the daemon event
        # loop for the duration of the write. Offload via
        # ``_spawn_background``: fire-and-forget in the default executor
        # when a loop is running, direct sync call otherwise. The outer
        # try/except stays as a belt-and-braces guard; the helper itself
        # also swallows internal exceptions.
        _spawn_background(
            record_hook_event,
            hook_name=hook_name,
            event_name=event_name,
            duration_ms=duration_ms,
            exit_code=exit_code,
            tool_name=tool_name,
            error=error,
            notes=notes,
        )
    except Exception:
        # Best-effort: record_hook_event is fire-and-forget and the ack
        # must go out regardless. Log at DEBUG so operators investigating
        # missing hook-events have a trail; never surface to the caller.
        logger.debug(
            "api_hook_log: failed to spawn record_hook_event",
            exc_info=True,
        )

    return JSONResponse({"ok": True}, status_code=202)


@mcp.custom_route("/api/events/publish", methods=["POST"])
async def api_events_publish(request: Request) -> JSONResponse:
    """Accept a fire-and-forget event from a hook subprocess or MCP worker.

    ``spellbook.admin.events.publish_sync`` only functions inside the daemon's
    running event loop. Subprocess callers (hook scripts, CLI, MCP stdio
    workers) cannot use it directly, so they delegate publishing to the daemon
    by POSTing to this endpoint. We are already inside the daemon's event loop
    here, so we can ``await event_bus.publish(...)`` directly.

    This route lives at the MCP server root (not under ``/admin``) so it is
    covered by ``BearerAuthMiddleware`` -- the same auth surface as every other
    subprocess-facing endpoint (``/api/hook-log``, ``/api/hooks/record``,
    etc.).

    Accepts JSON body:
        {"subsystem": "worker_llm", "event_type": "call_ok", "data": {...}}

    Returns:
        {"ok": true} on success, 400 on unknown subsystem or missing fields.
    """
    from spellbook.admin.events import Event, Subsystem, event_bus

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    required = ["subsystem", "event_type", "data"]
    missing = [f for f in required if f not in body]
    if missing:
        return JSONResponse(
            {"error": f"missing required fields: {missing}"}, status_code=400
        )

    data = body["data"]
    if not isinstance(data, dict):
        return JSONResponse(
            {"error": "field 'data' must be an object"}, status_code=400
        )

    try:
        subsystem = Subsystem(body["subsystem"])
    except ValueError as e:
        return JSONResponse(
            {"error": f"unknown subsystem: {e}"}, status_code=400
        )

    event_type = str(body["event_type"])
    await event_bus.publish(
        Event(
            subsystem=subsystem,
            event_type=event_type,
            data=data,
        )
    )

    # Persist subprocess-originated worker-LLM call events into the
    # observability table. The daemon path writes via ``publish_call``
    # (design §4.1); this branch covers hooks and other subprocesses that
    # POST here because they have no event loop to call ``publish_sync``
    # directly.
    if subsystem is Subsystem.WORKER_LLM and event_type in (
        "call_ok",
        "call_failed",
        "call_fail_open",
    ):
        # Input validation: ``BearerAuthMiddleware`` authenticates the
        # caller but does NOT vet the payload, so this validation is
        # necessary before the fields reach the indexed
        # ``worker_llm_calls`` columns. Length caps keep the two indexed
        # string columns bounded; the ``status`` enum check prevents
        # typos from producing orphan values that would distort
        # aggregates (``success_rate``, ``error_breakdown``).
        task_val = str(data.get("task", ""))
        model_val = str(data.get("model", ""))
        status_val = str(data.get("status", ""))
        if len(task_val) > 128 or len(model_val) > 128:
            return JSONResponse(
                {"error": "task/model too long (max 128 chars)"},
                status_code=400,
            )
        if status_val not in {"success", "error", "timeout", "fail_open", "dropped"}:
            return JSONResponse(
                {"error": f"invalid status: {status_val!r}"},
                status_code=400,
            )
        try:
            from spellbook.worker_llm.events import _spawn_background
            from spellbook.worker_llm import observability as _wl_obs

            # ``record_call`` is a synchronous SQLite INSERT; calling it
            # directly from this async handler would hold the daemon event
            # loop for the duration of the write. Offload via
            # ``_spawn_background`` — fire-and-forget in the default
            # executor when a loop is running; sync call when not.
            #
            # We resolve ``record_call`` off the module attribute (rather
            # than binding via ``from ... import record_call``) so that
            # tests monkeypatching ``observability.record_call`` still see
            # their spy invoked through the background path. The helper
            # itself swallows any exception the spy / real function
            # raises.
            _spawn_background(
                _wl_obs.record_call,
                task=task_val,
                model=model_val,
                latency_ms=int(data.get("latency_ms", 0) or 0),
                status=status_val,
                prompt_len=int(data.get("prompt_len", 0) or 0),
                response_len=int(data.get("response_len", 0) or 0),
                error=data.get("error"),
                override_loaded=bool(data.get("override_loaded", False)),
            )
        except Exception:
            # Best-effort: ``record_call`` is fire-and-forget and the ack
            # must go out regardless. Log at DEBUG so operators can
            # correlate missing worker-LLM rows; never surface to caller.
            logger.debug(
                "api_events_publish: failed to spawn record_call",
                exc_info=True,
            )

    return JSONResponse({"ok": True})
