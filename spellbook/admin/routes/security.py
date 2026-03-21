"""Security event log API routes (SQLAlchemy ORM)."""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.routes.list_helpers import build_list_response, validate_sort_order
from spellbook.db import spellbook_db
from spellbook.db.spellbook_models import (
    CanaryToken,
    SecurityEvent,
    SecurityMode,
    TrustRegistry,
)

router = APIRouter(prefix="/security", tags=["security"])

SORT_WHITELIST = {"created_at", "severity", "event_type"}


@router.get("/events")
async def list_security_events(
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    sort_by: Optional[str] = Query(None, pattern=f"^({'|'.join(SORT_WHITELIST)})$"),
    sort_order: Optional[str] = Query(None, pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """List security events with optional filters, pagination, and sorting."""
    # Build filter conditions
    filters = []
    if severity:
        filters.append(SecurityEvent.severity == severity)
    if event_type:
        filters.append(SecurityEvent.event_type == event_type)
    if since:
        filters.append(SecurityEvent.created_at >= since)
    if until:
        filters.append(SecurityEvent.created_at <= until)

    # Count query
    count_stmt = select(func.count()).select_from(SecurityEvent)
    if filters:
        count_stmt = count_stmt.where(*filters)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Data query
    data_stmt = select(SecurityEvent)
    if filters:
        data_stmt = data_stmt.where(*filters)

    # Sorting
    resolved_sort_by = sort_by or "created_at"
    resolved_sort_order = validate_sort_order(sort_order or "desc")
    sort_column = getattr(SecurityEvent, resolved_sort_by)
    if resolved_sort_order == "asc":
        data_stmt = data_stmt.order_by(sort_column.asc())
    else:
        data_stmt = data_stmt.order_by(sort_column.desc())

    # Pagination
    offset = (page - 1) * per_page
    data_stmt = data_stmt.limit(per_page).offset(offset)

    result = await db.execute(data_stmt)
    events = [row.to_dict() for row in result.scalars().all()]

    return build_list_response(events, total, page, per_page)


@router.get("/summary")
async def security_summary(
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Return event counts grouped by severity."""
    stmt = select(SecurityEvent.severity, func.count()).group_by(SecurityEvent.severity)
    result = await db.execute(stmt)
    rows = result.all()
    return {
        "by_severity": {severity: cnt for severity, cnt in rows},
    }


@router.get("/dashboard")
async def security_dashboard(
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Return aggregated security dashboard data."""
    # All queries use the same session but run sequentially
    # (asyncio.gather with sync session calls doesn't help here)

    # 1. Events by severity (last 24h)
    sev_stmt = (
        select(SecurityEvent.severity, func.count())
        .where(SecurityEvent.created_at > func.datetime("now", "-24 hours"))
        .group_by(SecurityEvent.severity)
    )
    sev_result = await db.execute(sev_stmt)
    by_severity = sev_result.all()

    # 2. Top event types (last 24h)
    top_stmt = (
        select(SecurityEvent.event_type, func.count().label("cnt"))
        .where(SecurityEvent.created_at > func.datetime("now", "-24 hours"))
        .group_by(SecurityEvent.event_type)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_result = await db.execute(top_stmt)
    top_types = top_result.all()

    # 3. Active canaries (not triggered)
    canary_stmt = select(func.count()).select_from(CanaryToken).where(
        CanaryToken.triggered_at.is_(None)
    )
    canary_result = await db.execute(canary_stmt)
    active_canaries = canary_result.scalar_one()

    # 4. Trust registry size
    trust_stmt = select(func.count()).select_from(TrustRegistry)
    trust_result = await db.execute(trust_stmt)
    trust_count = trust_result.scalar_one()

    # 5. Security mode
    mode_stmt = select(SecurityMode).where(SecurityMode.id == 1)
    mode_result = await db.execute(mode_stmt)
    mode_row = mode_result.scalars().first()

    return {
        "mode": mode_row.mode if mode_row else "standard",
        "events_24h": {severity: cnt for severity, cnt in by_severity},
        "top_event_types": [
            {"event_type": et, "cnt": cnt} for et, cnt in top_types
        ],
        "active_canaries": active_canaries,
        "trust_registry_size": trust_count,
    }


@router.get("/events/{event_id}")
async def get_security_event(
    event_id: int,
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Get a single security event by ID."""
    stmt = select(SecurityEvent).where(SecurityEvent.id == event_id)
    result = await db.execute(stmt)
    event = result.scalars().first()
    if not event:
        return JSONResponse(
            {"error": {"code": "EVENT_NOT_FOUND", "message": "Security event not found"}},
            status_code=404,
        )
    return event.to_dict()
