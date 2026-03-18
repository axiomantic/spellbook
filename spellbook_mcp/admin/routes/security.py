"""Security event log API routes."""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.db import query_spellbook_db

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/events")
async def list_security_events(
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """List security events with optional filters and pagination."""
    conditions = ["1=1"]
    params: list = []

    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if since:
        conditions.append("created_at >= ?")
        params.append(since)
    if until:
        conditions.append("created_at <= ?")
        params.append(until)

    where = " AND ".join(conditions)

    count_result = await query_spellbook_db(
        f"SELECT COUNT(*) as cnt FROM security_events WHERE {where}",
        tuple(params),
    )
    total = count_result[0]["cnt"] if count_result else 0
    offset = (page - 1) * per_page

    events = await query_spellbook_db(
        f"SELECT * FROM security_events WHERE {where} "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
        tuple(params) + (per_page, offset),
    )

    return {
        "events": events,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/summary")
async def security_summary(
    _session: str = Depends(require_admin_auth),
):
    """Return event counts grouped by severity."""
    rows = await query_spellbook_db(
        "SELECT severity, COUNT(*) as cnt FROM security_events GROUP BY severity"
    )
    return {
        "by_severity": {row["severity"]: row["cnt"] for row in rows},
    }


@router.get("/dashboard")
async def security_dashboard(
    _session: str = Depends(require_admin_auth),
):
    """Return aggregated security dashboard data."""
    by_severity, top_types, canaries, trust, mode_rows = await asyncio.gather(
        query_spellbook_db(
            "SELECT severity, COUNT(*) as cnt FROM security_events "
            "WHERE created_at > datetime('now', '-24 hours') GROUP BY severity"
        ),
        query_spellbook_db(
            "SELECT event_type, COUNT(*) as cnt FROM security_events "
            "WHERE created_at > datetime('now', '-24 hours') GROUP BY event_type "
            "ORDER BY cnt DESC LIMIT 10"
        ),
        query_spellbook_db(
            "SELECT COUNT(*) as cnt FROM canary_tokens WHERE triggered_at IS NULL"
        ),
        query_spellbook_db("SELECT COUNT(*) as cnt FROM trust_registry"),
        query_spellbook_db("SELECT mode FROM security_mode WHERE id = 1"),
    )

    return {
        "mode": mode_rows[0]["mode"] if mode_rows else "standard",
        "events_24h": {r["severity"]: r["cnt"] for r in by_severity},
        "top_event_types": top_types,
        "active_canaries": canaries[0]["cnt"] if canaries else 0,
        "trust_registry_size": trust[0]["cnt"] if trust else 0,
    }


@router.get("/events/{event_id}")
async def get_security_event(
    event_id: int,
    _session: str = Depends(require_admin_auth),
):
    """Get a single security event by ID."""
    rows = await query_spellbook_db(
        "SELECT * FROM security_events WHERE id = ?", (event_id,)
    )
    if not rows:
        return JSONResponse(
            {"error": {"code": "EVENT_NOT_FOUND", "message": "Security event not found"}},
            status_code=404,
        )
    return rows[0]
