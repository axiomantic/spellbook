"""Zeigarnik focus-tracking API routes.

Provides views into stint stacks (active focus context) and
correction events for the admin dashboard.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query

from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.db import query_spellbook_db

router = APIRouter(prefix="/focus", tags=["focus"])

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


def _parse_json(text: str) -> list:
    """Parse a JSON text column into a list, returning [] on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, TypeError):
        return []


@router.get("/stacks")
async def focus_stacks(
    _session: str = Depends(require_admin_auth),
):
    """All active stint stacks, ordered by most recently updated."""
    rows = await query_spellbook_db(
        """
        SELECT project_path, session_id, stack_json, updated_at
        FROM stint_stack
        ORDER BY updated_at DESC
        """,
        (),
    )

    stacks = []
    for row in rows:
        parsed = _parse_json(row.get("stack_json", "[]"))
        stacks.append(
            {
                "project_path": row.get("project_path"),
                "session_id": row.get("session_id"),
                "stack": parsed,
                "depth": len(parsed),
                "updated_at": row.get("updated_at"),
            }
        )

    return {"stacks": stacks}


@router.get("/corrections")
async def focus_corrections(
    period: str = Query("7d", description="Time period: 24h, 7d, 30d, all"),
    project: Optional[str] = Query(None, description="Filter by project_path"),
    correction_type: Optional[str] = Query(
        None, description="Filter by correction_type: llm_wrong, mcp_wrong"
    ),
    _session: str = Depends(require_admin_auth),
):
    """Correction events with optional filtering."""
    period_clause, period_params = _period_clause(period)

    conditions = ["1=1"]
    params: list = []

    if period_clause:
        conditions.append(period_clause.lstrip("AND "))
        params.extend(period_params)

    if project:
        conditions.append("project_path = ?")
        params.append(project)

    if correction_type:
        conditions.append("correction_type = ?")
        params.append(correction_type)

    where = " AND ".join(conditions)

    rows = await query_spellbook_db(
        f"""
        SELECT *
        FROM stint_correction_events
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT 200
        """,
        tuple(params),
    )

    corrections = []
    for row in rows:
        parsed_row = dict(row)
        parsed_row["old_stack_json"] = _parse_json(
            parsed_row.get("old_stack_json", "[]")
        )
        parsed_row["new_stack_json"] = _parse_json(
            parsed_row.get("new_stack_json", "[]")
        )
        corrections.append(parsed_row)

    return {"corrections": corrections, "total": len(corrections)}


@router.get("/summary")
async def focus_summary(
    _session: str = Depends(require_admin_auth),
):
    """Aggregate focus stats for the dashboard."""

    async def get_stacks():
        return await query_spellbook_db(
            "SELECT stack_json FROM stint_stack",
            (),
        )

    async def get_total_corrections_24h():
        return await query_spellbook_db(
            """
            SELECT COUNT(*) as count
            FROM stint_correction_events
            WHERE created_at >= datetime('now', '-24 hours')
            """,
            (),
        )

    async def get_llm_wrong_24h():
        return await query_spellbook_db(
            """
            SELECT COUNT(*) as count
            FROM stint_correction_events
            WHERE created_at >= datetime('now', '-24 hours')
              AND correction_type = 'llm_wrong'
            """,
            (),
        )

    async def get_mcp_wrong_24h():
        return await query_spellbook_db(
            """
            SELECT COUNT(*) as count
            FROM stint_correction_events
            WHERE created_at >= datetime('now', '-24 hours')
              AND correction_type = 'mcp_wrong'
            """,
            (),
        )

    stacks_rows, total_rows, llm_rows, mcp_rows = await asyncio.gather(
        get_stacks(),
        get_total_corrections_24h(),
        get_llm_wrong_24h(),
        get_mcp_wrong_24h(),
    )

    # Count active projects (non-empty stacks)
    active_projects = 0
    max_depth = 0
    for row in stacks_rows:
        parsed = _parse_json(row.get("stack_json", "[]"))
        if len(parsed) > 0:
            active_projects += 1
        if len(parsed) > max_depth:
            max_depth = len(parsed)

    return {
        "active_projects": active_projects,
        "total_corrections_24h": total_rows[0]["count"] if total_rows else 0,
        "llm_wrong_24h": llm_rows[0]["count"] if llm_rows else 0,
        "mcp_wrong_24h": mcp_rows[0]["count"] if mcp_rows else 0,
        "max_depth": max_depth,
    }
