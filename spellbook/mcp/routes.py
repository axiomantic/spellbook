"""HTTP custom routes for the MCP server.

Registers REST endpoints via @mcp.custom_route() for use by hook scripts
and monitoring tools that need HTTP access without full MCP protocol.
"""

import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse

from spellbook.mcp import state as _state
from spellbook.mcp.server import mcp
from spellbook.notifications import tts as tts_module
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


@mcp.custom_route("/api/speak", methods=["POST"])
async def api_speak(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to trigger TTS.

    Accepts JSON body: {"text": "...", "voice": "...", "volume": 0.3}
    Returns JSON: {"ok": true, "elapsed": 1.23, "wav_path": "..."} on success,
    optionally with "warning" if volume was clamped or playback failed.
    Returns {"error": "..."} on failure.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    text = body.get("text", "")
    if not text:
        return JSONResponse({"error": "no text provided"}, status_code=400)

    if len(text) > 5000:
        return JSONResponse({"error": "text exceeds 5000 character limit"}, status_code=400)

    voice = body.get("voice")
    volume = body.get("volume")
    session_id = body.get("session_id")

    result = await tts_module.speak(text, voice=voice, volume=volume, session_id=session_id)
    status_code = 200 if result.get("ok") else 500
    return JSONResponse(result, status_code=status_code)


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


def _poll_inbox_sync(messaging_base: Path, session_id: str) -> list[dict]:
    """Synchronous inbox polling -- runs in thread pool via asyncio.to_thread()."""
    messages: list[dict] = []
    for alias_dir in sorted(messaging_base.iterdir()):
        if not alias_dir.is_dir():
            continue

        # Only drain inboxes with a matching .session_id marker
        marker = alias_dir / ".session_id"
        if not marker.exists():
            continue
        try:
            marker_session_id = marker.read_text().strip()
        except OSError:
            continue
        if marker_session_id != session_id:
            continue

        inbox = alias_dir / "inbox"
        if not inbox.exists():
            continue

        for msg_file in sorted(inbox.glob("*.json")):
            try:
                data = json.loads(msg_file.read_text())
                messages.append({
                    "message_type": data.get("message_type", "direct"),
                    "sender": data.get("sender", "unknown"),
                    "payload": data.get("payload", {}),
                    "correlation_id": data.get("correlation_id"),
                    "filename": msg_file.name,
                })
                # Delete after processing
                msg_file.unlink()
            except Exception:
                # Log broken message files before deleting
                logger.warning("Malformed inbox message %s, deleting", msg_file)
                try:
                    msg_file.unlink()
                except OSError:
                    pass
    return messages


@mcp.custom_route("/api/messaging/poll", methods=["POST"])
async def api_messaging_poll(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to poll messaging inbox via the daemon.

    Accepts JSON body: {"session_id": "string"}
    Returns JSON: {"messages": [...]} where each message has fields:
        message_type, sender, payload, correlation_id, filename

    Iterates all alias directories under ~/.local/spellbook/messaging/,
    draining only those whose .session_id marker matches the request.
    This replicates the behavior formerly in hooks/spellbook_hook.py
    _messaging_check(), eliminating the need for hook processes to have
    write access to the config directory.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    session_id = body.get("session_id", "")
    if not session_id:
        return JSONResponse(
            {"error": "missing required field: session_id"},
            status_code=400,
        )

    messaging_base = get_spellbook_config_dir() / "messaging"
    if not messaging_base.exists():
        return JSONResponse({"messages": []})

    messages = await asyncio.to_thread(
        _poll_inbox_sync, messaging_base, session_id
    )
    return JSONResponse({"messages": messages})
