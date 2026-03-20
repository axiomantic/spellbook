"""Tool call analytics API routes.

Provides aggregated views of security_events data: tool frequency,
error rates, timeline, and summary statistics.

Uses SQLAlchemy ORM queries against the SecurityEvent model.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select

from spellbook.admin.auth import require_admin_auth
from spellbook.db import get_spellbook_session
from spellbook.db.spellbook_models import SecurityEvent

router = APIRouter(prefix="/analytics", tags=["analytics"])

PERIOD_MAP = {
    "24h": "-24 hours",
    "7d": "-7 days",
    "30d": "-30 days",
}


def _error_count_expr():
    """SQLAlchemy expression for counting error/critical severity events."""
    return func.sum(
        case(
            (SecurityEvent.severity.in_(["error", "critical"]), 1),
            else_=0,
        )
    )


def _apply_period_filter(stmt, period: str):
    """Add period-based date filtering to a SELECT statement.

    Returns the statement unchanged for 'all' period.
    """
    sqlite_offset = PERIOD_MAP.get(period)
    if sqlite_offset is not None:
        stmt = stmt.where(
            SecurityEvent.created_at >= func.datetime("now", sqlite_offset)
        )
    return stmt


@router.get("/tool-frequency")
async def tool_frequency(
    period: str = Query("7d", description="Time period: 24h, 7d, 30d, all"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    _session: str = Depends(require_admin_auth),
):
    """Tool call counts grouped by tool_name, sorted descending."""
    async with get_spellbook_session() as session:
        errors_expr = _error_count_expr()
        stmt = (
            select(
                SecurityEvent.tool_name,
                func.count().label("count"),
                errors_expr.label("errors"),
            )
            .where(SecurityEvent.tool_name.isnot(None))
        )

        stmt = _apply_period_filter(stmt, period)

        if event_type:
            stmt = stmt.where(SecurityEvent.event_type == event_type)

        stmt = stmt.group_by(SecurityEvent.tool_name).order_by(
            func.count().desc()
        )

        result = await session.execute(stmt)
        rows = [
            {"tool_name": row.tool_name, "count": row.count, "errors": row.errors}
            for row in result
        ]

    return {"tools": rows}


@router.get("/error-rates")
async def error_rates(
    period: str = Query("7d"),
    _session: str = Depends(require_admin_auth),
):
    """Error rates by tool, ordered by error count descending."""
    async with get_spellbook_session() as session:
        errors_expr = _error_count_expr()

        stmt = (
            select(
                SecurityEvent.tool_name,
                func.count().label("total"),
                errors_expr.label("errors"),
                func.round(
                    100.0 * errors_expr / func.count(), 2
                ).label("error_rate"),
            )
            .where(SecurityEvent.tool_name.isnot(None))
        )

        stmt = _apply_period_filter(stmt, period)

        stmt = (
            stmt.group_by(SecurityEvent.tool_name)
            .having(errors_expr > 0)
            .order_by(errors_expr.desc())
        )

        result = await session.execute(stmt)
        rows = [
            {
                "tool_name": row.tool_name,
                "total": row.total,
                "errors": row.errors,
                "error_rate": row.error_rate,
            }
            for row in result
        ]

    return {"tools": rows}


@router.get("/timeline")
async def timeline(
    period: str = Query("7d"),
    _session: str = Depends(require_admin_auth),
):
    """Time-series event counts bucketed by hour (24h) or day (7d/30d/all)."""
    bucket_format = "%Y-%m-%d %H:00" if period == "24h" else "%Y-%m-%d"

    async with get_spellbook_session() as session:
        bucket_col = func.strftime(bucket_format, SecurityEvent.created_at).label(
            "bucket"
        )

        stmt = select(
            bucket_col,
            func.count().label("count"),
            _error_count_expr().label("errors"),
        )

        stmt = _apply_period_filter(stmt, period)

        stmt = stmt.group_by(bucket_col).order_by(bucket_col)

        result = await session.execute(stmt)
        rows = [
            {"bucket": row.bucket, "count": row.count, "errors": row.errors}
            for row in result
        ]

    return {"timeline": rows}


@router.get("/summary")
async def analytics_summary(
    period: str = Query("7d"),
    _session: str = Depends(require_admin_auth),
):
    """Aggregate statistics: total events, unique tools, error rate, events today."""
    async with get_spellbook_session() as session:
        errors_expr = _error_count_expr()
        stmt = select(
            func.count().label("total_events"),
            func.count(func.distinct(SecurityEvent.tool_name)).label("unique_tools"),
            func.round(
                100.0 * errors_expr / func.max(func.count(), 1),
                2,
            ).label("error_rate"),
            func.sum(
                case(
                    (
                        SecurityEvent.created_at
                        >= func.datetime("now", "-24 hours"),
                        1,
                    ),
                    else_=0,
                )
            ).label("events_today"),
        )

        stmt = _apply_period_filter(stmt, period)

        result = await session.execute(stmt)
        row = result.one_or_none()

        if row and row.total_events:
            return {
                "total_events": row.total_events,
                "unique_tools": row.unique_tools,
                "error_rate": row.error_rate,
                "events_today": row.events_today,
            }

    return {
        "total_events": 0,
        "unique_tools": 0,
        "error_rate": 0,
        "events_today": 0,
    }
