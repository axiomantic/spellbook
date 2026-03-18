"""Recent events API route for the Event Monitor page.

Returns historical security_events so the page has data on load
instead of waiting for live WebSocket events.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.db import query_spellbook_db

router = APIRouter(prefix="/events", tags=["events"])


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
