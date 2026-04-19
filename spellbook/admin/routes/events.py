"""Recent events API route for the Event Monitor page.

Returns historical security_events so the page has data on load
instead of waiting for live WebSocket events.

Also exposes ``POST /api/events/publish`` so hook subprocesses, MCP stdio
workers, and CLI invocations — none of which have a running event loop — can
delegate event publishing to the daemon. See spellbook/worker_llm/events.py
for the client side.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.db import query_spellbook_db
from spellbook.admin.events import Event, Subsystem, publish_sync

router = APIRouter(prefix="/events", tags=["events"])


class EventPublishBody(BaseModel):
    subsystem: str
    event_type: str
    data: dict


@router.post("/publish")
async def publish_event_from_subprocess(body: EventPublishBody) -> dict:
    """Accept a fire-and-forget event from a hook subprocess or MCP worker.

    Rationale: ``publish_sync`` only functions inside the daemon's event loop.
    Subprocess callers cannot use it directly; this endpoint lets them delegate
    publishing to the daemon. Returns 400 on unknown subsystem to prevent
    typos from silently losing events.
    """
    try:
        subsystem = Subsystem(body.subsystem)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"unknown subsystem: {e}"
        )
    publish_sync(
        Event(
            subsystem=subsystem,
            event_type=body.event_type,
            data=body.data,
        )
    )
    return {"ok": True}


@router.get("/recent")
async def recent_events(
    limit: int = Query(50, ge=1, le=200),
    since_hours: float = Query(24, ge=0.1, le=720),
    _session: str = Depends(require_admin_auth),
):
    """Return recent security events for the Event Monitor page.

    Maps database rows to the WSEvent shape expected by the frontend:
    {type, subsystem, event, data, timestamp}.
    """
    rows = await query_spellbook_db(
        "SELECT id, event_type, severity, source, detail, session_id, "
        "tool_name, action_taken, created_at "
        "FROM security_events "
        "WHERE created_at >= datetime('now', '-' || ? || ' hours') "
        "ORDER BY created_at DESC LIMIT ?",
        (since_hours, limit),
    )

    events = []
    for row in rows:
        events.append({
            "type": "event",
            "subsystem": "security",
            "event": row.get("event_type", "unknown"),
            "data": {
                "id": row.get("id"),
                "severity": row.get("severity"),
                "source": row.get("source"),
                "detail": row.get("detail"),
                "session_id": row.get("session_id"),
                "tool_name": row.get("tool_name"),
                "action_taken": row.get("action_taken"),
            },
            "timestamp": row.get("created_at", ""),
        })

    return {"events": events, "total": len(events)}
