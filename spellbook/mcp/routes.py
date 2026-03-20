"""HTTP custom routes for the MCP server.

Registers REST endpoints via @mcp.custom_route() for use by hook scripts
and monitoring tools that need HTTP access without full MCP protocol.
"""

import time

from starlette.requests import Request
from starlette.responses import JSONResponse

from spellbook.mcp import state as _state
from spellbook.mcp.server import mcp
from spellbook.notifications import tts as tts_module
from spellbook.core.db import get_db_path
from spellbook.memory.tools import (
    do_log_event,
    do_memory_recall,
)
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


@mcp.custom_route("/api/memory/recall", methods=["POST"])
async def api_memory_recall(request: Request) -> JSONResponse:
    """REST endpoint for hook scripts to query memories by file path.

    Accepts JSON body: {"file_path": "...", "namespace": "...", "branch": "...", "limit": 5}
    or {"query": "...", "namespace": "...", "branch": "...", "limit": 10}
    Returns JSON: {"memories": [...], "count": N}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    namespace = body.get("namespace", "")
    if not namespace:
        return JSONResponse({"memories": [], "count": 0})

    branch = body.get("branch", "")
    repo_path = body.get("repo_path", "")

    db_path = str(get_db_path())
    result = do_memory_recall(
        db_path=db_path,
        query=body.get("query", ""),
        namespace=namespace,
        limit=body.get("limit", 5),
        file_path=body.get("file_path"),
        branch=branch,
        repo_path=repo_path,
    )
    return JSONResponse(result)
