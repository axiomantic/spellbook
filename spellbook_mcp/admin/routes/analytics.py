"""Tool call analytics API routes.

Provides aggregated views of security_events data: tool frequency,
error rates, timeline, and summary statistics.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.db import query_spellbook_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

PERIOD_MAP = {
    "24h": "-24 hours",
    "7d": "-7 days",
    "30d": "-30 days",
}


def _period_clause(period: str) -> tuple[str, tuple]:
    """Return (WHERE clause fragment, params) for period filtering.

    Returns empty clause for 'all' period.
    """
    sqlite_offset = PERIOD_MAP.get(period)
    if sqlite_offset is None:
        return "", ()
    return "AND created_at >= datetime('now', ?)", (sqlite_offset,)


@router.get("/tool-frequency")
async def tool_frequency(
    period: str = Query("7d", description="Time period: 24h, 7d, 30d, all"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    _session: str = Depends(require_admin_auth),
):
    """Tool call counts grouped by tool_name, sorted descending."""
    period_clause, period_params = _period_clause(period)

    conditions = ["tool_name IS NOT NULL", "1=1"]
    params: list = []

    if period_clause:
        conditions.append(period_clause.lstrip("AND "))
        params.extend(period_params)

    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)

    where = " AND ".join(conditions)

    rows = await query_spellbook_db(
        f"""
        SELECT tool_name, COUNT(*) as count,
               SUM(CASE WHEN severity IN ('error', 'critical') THEN 1 ELSE 0 END) as errors
        FROM security_events
        WHERE {where}
        GROUP BY tool_name
        ORDER BY count DESC
        """,
        tuple(params),
    )

    return {"tools": rows}


@router.get("/error-rates")
async def error_rates(
    period: str = Query("7d"),
    _session: str = Depends(require_admin_auth),
):
    """Error rates by tool, ordered by error count descending."""
    period_clause, period_params = _period_clause(period)

    conditions = ["tool_name IS NOT NULL", "1=1"]
    params: list = []

    if period_clause:
        conditions.append(period_clause.lstrip("AND "))
        params.extend(period_params)

    where = " AND ".join(conditions)

    rows = await query_spellbook_db(
        f"""
        SELECT tool_name,
               COUNT(*) as total,
               SUM(CASE WHEN severity IN ('error', 'critical') THEN 1 ELSE 0 END) as errors,
               ROUND(
                   100.0 * SUM(CASE WHEN severity IN ('error', 'critical') THEN 1 ELSE 0 END) / COUNT(*),
                   2
               ) as error_rate
        FROM security_events
        WHERE {where}
        GROUP BY tool_name
        HAVING errors > 0
        ORDER BY errors DESC
        """,
        tuple(params),
    )

    return {"tools": rows}


@router.get("/timeline")
async def timeline(
    period: str = Query("7d"),
    _session: str = Depends(require_admin_auth),
):
    """Time-series event counts bucketed by hour (24h) or day (7d/30d/all)."""
    period_clause, period_params = _period_clause(period)

    # Use hour buckets for 24h, day buckets otherwise
    bucket_format = "%Y-%m-%d %H:00" if period == "24h" else "%Y-%m-%d"

    conditions = ["1=1"]
    params: list = []

    if period_clause:
        conditions.append(period_clause.lstrip("AND "))
        params.extend(period_params)

    where = " AND ".join(conditions)

    rows = await query_spellbook_db(
        f"""
        SELECT strftime('{bucket_format}', created_at) as bucket,
               COUNT(*) as count,
               SUM(CASE WHEN severity IN ('error', 'critical') THEN 1 ELSE 0 END) as errors
        FROM security_events
        WHERE {where}
        GROUP BY bucket
        ORDER BY bucket
        """,
        tuple(params),
    )

    return {"timeline": rows}


@router.get("/summary")
async def analytics_summary(
    period: str = Query("7d"),
    _session: str = Depends(require_admin_auth),
):
    """Aggregate statistics: total events, unique tools, error rate, events today."""
    period_clause, period_params = _period_clause(period)

    conditions = ["1=1"]
    params: list = []

    if period_clause:
        conditions.append(period_clause.lstrip("AND "))
        params.extend(period_params)

    where = " AND ".join(conditions)

    rows = await query_spellbook_db(
        f"""
        SELECT
            COUNT(*) as total_events,
            COUNT(DISTINCT tool_name) as unique_tools,
            ROUND(
                100.0 * SUM(CASE WHEN severity IN ('error', 'critical') THEN 1 ELSE 0 END) / MAX(COUNT(*), 1),
                2
            ) as error_rate,
            SUM(CASE WHEN created_at >= datetime('now', '-24 hours') THEN 1 ELSE 0 END) as events_today
        FROM security_events
        WHERE {where}
        """,
        tuple(params),
    )

    if rows:
        result = rows[0]
    else:
        result = {
            "total_events": 0,
            "unique_tools": 0,
            "error_rate": 0,
            "events_today": 0,
        }

    return result
