"""HTTP custom routes for the MCP server.

Registers REST endpoints via @mcp.custom_route() for use by hook scripts
and monitoring tools that need HTTP access without full MCP protocol.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse

from spellbook.mcp import state as _state
from spellbook.mcp.server import mcp
from spellbook.core.db import get_db_path
from spellbook.memory.tools import (
    do_log_event,
    _get_memory_dir,
)
from spellbook.memory.filestore import recall_memories as _filestore_recall
from spellbook.memory.store import log_raw_event, mark_events_consolidated
from spellbook.memory.consolidation import should_consolidate, consolidate_batch
from spellbook.core.path_utils import get_spellbook_config_dir


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


@mcp.custom_route("/api/memory/event", methods=["POST"])
async def api_memory_event(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to log raw observation events.

    Accepts JSON body: {
        "session_id": "...",
        "project": "...",
        "tool_name": "...",
        "subject": "...",
        "summary": "...",
        "tags": "...",
        "event_type": "tool_use",
        "branch": "..."
    }
    Returns JSON: {"status": "logged", "event_id": N}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    required = ["session_id", "project", "tool_name", "subject", "summary"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return JSONResponse(
            {"error": f"missing required fields: {missing}"}, status_code=400
        )

    # Input length validation (truncate, not reject -- fail-open)
    summary = str(body["summary"])[:1000]
    tool_name = str(body["tool_name"])[:100]
    subject = str(body["subject"])[:500]
    tags = str(body.get("tags", ""))[:500]
    branch = str(body.get("branch", ""))[:200]

    db_path = str(get_db_path())
    result = do_log_event(
        db_path=db_path,
        session_id=body["session_id"],
        project=body["project"],
        tool_name=tool_name,
        subject=subject,
        summary=summary,
        tags=tags,
        event_type=body.get("event_type", "tool_use"),
        branch=branch,
    )
    return JSONResponse(result)


@mcp.custom_route("/api/memory/unconsolidated", methods=["POST"])
async def api_memory_unconsolidated(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to enqueue a self-nominated memory
    candidate as a raw unconsolidated event.

    Accepts JSON body: {
        "project": "...",         (required, project-encoded namespace)
        "type": "feedback|project|user|reference",  (required)
        "content": "...",         (required, 1-3 sentence summary)
        "tags": "...",            (optional, comma-separated)
        "citations": "...",       (optional, path:line comma-separated)
        "branch": "...",          (optional)
        "source": "...",          (optional, e.g. "stop_hook", "user_prompt_submit")
        "session_id": "..."       (optional)
    }

    Returns JSON: {"status": "logged", "event_id": N}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    required = ["project", "type", "content"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return JSONResponse(
            {"error": f"missing required fields: {missing}"}, status_code=400
        )

    project = str(body["project"])[:500]
    mtype = str(body["type"])[:50]
    content = str(body["content"])[:5000]
    tags = str(body.get("tags", ""))[:500]
    citations = str(body.get("citations", ""))[:1000]
    branch = str(body.get("branch", ""))[:200]
    source = str(body.get("source", "auto_store"))[:100]
    session_id = str(body.get("session_id", ""))[:200]

    # Combine tags with self-nomination marker and type for downstream filters
    combined_tags = ",".join(
        t for t in ["self-nominated", f"type:{mtype}", tags] if t
    )[:500]

    db_path = str(get_db_path())
    event_id = log_raw_event(
        db_path=db_path,
        session_id=session_id,
        project=project,
        event_type="memory_candidate",
        tool_name=source,
        subject=citations,
        summary=content,
        tags=combined_tags,
        branch=branch,
    )
    return JSONResponse({"status": "logged", "event_id": event_id})


@mcp.custom_route("/api/memory/bridge-content", methods=["POST"])
async def api_memory_bridge_content(request: Request) -> JSONResponse:
    """REST endpoint for bridge hook to submit auto-memory content.

    Stores two events: a brief-summary event (for consolidation) and a
    full-content event (for audit/retrieval, marked consolidated immediately).
    Triggers consolidation if the event threshold is met.

    Accepts JSON body: {
        "session_id": "...",
        "project": "...",
        "file_path": "...",      (optional)
        "filename": "...",       (optional)
        "content": "...",
        "is_primary": true|false, (optional)
        "branch": "..."          (optional)
    }

    Returns JSON: {"status": "captured", "event_id": N, "consolidated": bool}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    required = ["session_id", "project", "content"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return JSONResponse(
            {"error": f"missing required fields: {missing}"}, status_code=400
        )

    session_id = str(body["session_id"])
    project = str(body["project"])
    file_path = str(body.get("file_path", ""))
    filename = str(body.get("filename", ""))
    content = str(body["content"])
    is_primary = bool(body.get("is_primary", False))
    branch = str(body.get("branch", ""))[:200]

    db_path = str(get_db_path())

    # Count lines and extract section headers for brief summary
    lines = content.split("\n")
    line_count = len(lines)
    sections = [
        line.lstrip("#").strip()
        for line in lines
        if line.startswith("#") and line.lstrip("#").strip()
    ]
    sections_str = ", ".join(sections[:5])
    if len(sections) > 5:
        sections_str += f" (+{len(sections) - 5} more)"
    brief = f"{filename} updated: {line_count} lines"
    if sections_str:
        brief += f", sections: {sections_str}"

    # 1. Brief-summary event (flows through normal consolidation)
    result = do_log_event(
        db_path=db_path,
        session_id=session_id,
        project=project,
        tool_name="auto_memory_bridge",
        subject=file_path,
        summary=brief[:1000],
        tags=f"auto-memory,bridge,{filename.lower().replace('.md', '')}",
        event_type="auto_memory_bridge",
        branch=branch,
    )
    event_id = result["event_id"]

    # 2. Full-content event (audit/retrieval, skip consolidation)
    content_event_id = log_raw_event(
        db_path=db_path,
        session_id=session_id,
        project=project,
        event_type="auto_memory_content",
        tool_name="auto_memory_bridge",
        subject=file_path,
        summary=content[:10000],
        tags=f"auto-memory,content,{filename.lower().replace('.md', '')}",
        branch=branch,
    )
    # Mark immediately so consolidation pipeline ignores it
    mark_events_consolidated(db_path, [content_event_id], "bridge-immediate")

    # 3. Check consolidation threshold
    consolidated = False
    if should_consolidate(db_path):
        import asyncio

        asyncio.ensure_future(asyncio.to_thread(consolidate_batch, db_path, project))
        consolidated = True

    return JSONResponse({
        "status": "captured",
        "event_id": event_id,
        "consolidated": consolidated,
    })


def _derive_namespace_from_cwd(cwd: str) -> str:
    """Project-encode a cwd path into a memory namespace.

    Thin wrapper over the canonical implementation in
    ``spellbook.memory.utils.derive_namespace_from_cwd`` — kept for the
    existing import path used by callers.
    """
    from spellbook.memory.utils import derive_namespace_from_cwd

    return derive_namespace_from_cwd(cwd)


def _memory_result_to_dict(result, memory_dir: str) -> dict:
    """Serialize a filestore MemoryResult into the REST response shape.

    Shape:
        {
          "path": str,           # absolute memory file path
          "score": float,
          "match_context": str | None,
          "frontmatter": {
              "type": str,
              "confidence": str | None,
              "created": str (ISO date),
              "last_verified": str | None (ISO date),
          },
          "body": str,
        }
    """
    mem = result.memory
    fm = mem.frontmatter
    return {
        "path": mem.path,
        "score": result.score,
        "match_context": result.match_context,
        "frontmatter": {
            "type": fm.type,
            "confidence": fm.confidence,
            "created": fm.created.isoformat() if fm.created else None,
            "last_verified": fm.last_verified.isoformat() if fm.last_verified else None,
        },
        "body": mem.content,
    }


@mcp.custom_route("/api/memory/recall", methods=["POST"])
async def api_memory_recall(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to query memories.

    Accepts JSON body:
        {
          "query": str,        # optional when file_path is provided
          "file_path": str,    # optional, filter by citation file
          "namespace": str,    # optional; derived from cwd when absent
          "cwd": str,          # optional; used to derive namespace
          "branch": str,       # optional; passed to scoring
          "limit": int,        # default 5
          "tags": list[str],   # optional
        }

    Returns:
        {"memories": [MemoryResult-shape dicts], "count": N}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    namespace = body.get("namespace") or ""
    if not namespace:
        # _derive_namespace_from_cwd shells out to `git rev-parse`; offload the
        # subprocess call so we do not block the event loop.
        namespace = await asyncio.to_thread(
            _derive_namespace_from_cwd,
            body.get("cwd", "") or body.get("repo_path", ""),
        )
    if not namespace:
        return JSONResponse({"memories": [], "count": 0})

    branch = body.get("branch") or None
    query = body.get("query", "") or ""
    file_path = body.get("file_path") or None
    limit = int(body.get("limit", 5) or 5)
    tags = body.get("tags") or None

    memory_dir = _get_memory_dir(namespace, "project")
    try:
        results = await asyncio.to_thread(
            _filestore_recall,
            query=query,
            memory_dir=memory_dir,
            scope=None,
            tags=tags,
            file_path=file_path,
            limit=limit,
            branch=branch,
        )
    except Exception:
        return JSONResponse({"memories": [], "count": 0})

    memories = [_memory_result_to_dict(r, memory_dir) for r in results]
    return JSONResponse({"memories": memories, "count": len(memories)})


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
          "task_name": str,  # required; e.g. "transcript_harvest"
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
    # Today we register ``transcript_harvest``; other tasks enqueue with
    # ``callback=None`` and rely on ``client.call``'s event emission for
    # observability.
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

    Lazy-imports the task module so the MCP server doesn't pull in every
    task handler at registration time.
    """
    if task_name == "transcript_harvest":
        from spellbook.worker_llm.tasks.transcript_harvest import (
            async_consumer_callback as _cb,
        )
        return _cb
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

        record_hook_event(
            hook_name=hook_name,
            event_name=event_name,
            duration_ms=duration_ms,
            exit_code=exit_code,
            tool_name=tool_name,
            error=error,
            notes=notes,
        )
    except Exception:
        # Silent: record_hook_event is best-effort. Route must still ack.
        pass

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
    subprocess-facing endpoint (``/api/hook-log``, ``/api/memory/event``,
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
            from spellbook.worker_llm.observability import record_call

            record_call(
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
            # Silent: ``record_call`` is best-effort. Route must still ack.
            pass

    return JSONResponse({"ok": True})
