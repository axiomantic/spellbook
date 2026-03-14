"""Session (soul) list and detail API routes."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.db import query_spellbook_db

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _parse_json_field(value: Optional[str]):
    """Parse a JSON string field, returning None if null or invalid."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _enrich_session(row: dict) -> dict:
    """Parse JSON fields in a soul row for API response."""
    result = dict(row)
    for field in ("todos", "recent_files"):
        if field in result:
            result[field] = _parse_json_field(result.get(field))
    return result


@router.get("")
async def list_sessions(
    project: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """List sessions (souls) with optional project filter and pagination."""
    conditions = ["1=1"]
    params: list = []

    if project:
        conditions.append("project_path = ?")
        params.append(project)

    where = " AND ".join(conditions)

    count_result = await query_spellbook_db(
        f"SELECT COUNT(*) as cnt FROM souls WHERE {where}",
        tuple(params),
    )
    total = count_result[0]["cnt"] if count_result else 0
    offset = (page - 1) * per_page

    rows = await query_spellbook_db(
        f"SELECT * FROM souls WHERE {where} ORDER BY bound_at DESC LIMIT ? OFFSET ?",
        tuple(params) + (per_page, offset),
    )

    return {
        "sessions": [_enrich_session(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Get a single session (soul) by ID."""
    rows = await query_spellbook_db(
        "SELECT * FROM souls WHERE id = ?", (session_id,)
    )
    if not rows:
        return JSONResponse(
            {"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found"}},
            status_code=404,
        )
    return _enrich_session(rows[0])
