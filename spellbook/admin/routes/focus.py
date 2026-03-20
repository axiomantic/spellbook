"""Zeigarnik focus-tracking API routes.

Provides views into stint stacks (active focus context) and
correction events for the admin dashboard.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.db import query_spellbook_db
from spellbook.admin.routes.list_helpers import build_list_response, validate_sort_order
from spellbook.db import spellbook_db
from spellbook.db.helpers import apply_pagination, apply_sorting
from spellbook.db.spellbook_models import StintCorrectionEvent, StintStack

router = APIRouter(prefix="/focus", tags=["focus"])

CORRECTIONS_SORT_WHITELIST = {"created_at", "project_path", "correction_type"}


def _parse_json(text: str) -> list:
    """Parse a JSON text column into a list, returning [] on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _stack_to_dict(stack: StintStack) -> dict:
    """Convert a StintStack ORM object to a response dict with depth."""
    d = stack.to_dict()
    parsed = d.get("stack") or []
    return {
        "project_path": d["project_path"],
        "session_id": d["session_id"],
        "stack": parsed,
        "depth": len(parsed),
        "updated_at": d["updated_at"],
    }


@router.get("/stacks")
async def focus_stacks(
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """All active stint stacks, ordered by most recently updated."""
    query = select(StintStack).order_by(desc(StintStack.updated_at))
    result = await db.execute(query)
    stacks = list(result.scalars().all())

    items = [_stack_to_dict(s) for s in stacks]
    return {"items": items}


@router.get("/corrections")
async def focus_corrections(
    project: Optional[str] = Query(None, description="Filter by project_path"),
    correction_type: Optional[str] = Query(
        None, description="Filter by correction_type: llm_wrong, mcp_wrong"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Items per page"),
    sort: str = Query("created_at", description="Sort column"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Correction events with optional filtering, sorting, and pagination."""
    # Build base query with filters
    query = select(StintCorrectionEvent)

    if project:
        query = query.where(StintCorrectionEvent.project_path == project)

    if correction_type:
        query = query.where(StintCorrectionEvent.correction_type == correction_type)

    # Count total matching rows
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Apply sorting
    sort_order = validate_sort_order(order)
    query = apply_sorting(
        query,
        StintCorrectionEvent,
        sort,
        sort_order,
        allowed_columns=CORRECTIONS_SORT_WHITELIST,
        default_column="created_at",
    )

    # Apply pagination
    query = apply_pagination(query, page, per_page)

    result = await db.execute(query)
    corrections = list(result.scalars().all())

    items = [c.to_dict() for c in corrections]
    return build_list_response(items=items, total=total, page=page, per_page=per_page)


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
