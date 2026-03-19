"""Memory browser CRUD routes for admin interface.

Provides listing with FTS5 search, namespace/type/status filtering,
pagination, detail view with citations, update, soft delete,
consolidation trigger, namespace listing, and stats.
"""

import asyncio
import hashlib
import json
import logging
import math
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.db import execute_spellbook_db, query_spellbook_db
from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.core.db import get_db_path
from spellbook.memory.consolidation import consolidate_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memory"])

# Module-level flag for consolidation lock
_consolidation_running = False


def _error_response(code: str, message: str, status: int, details: list | None = None) -> JSONResponse:
    """Return a standardized ErrorResponse."""
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


def _parse_meta(meta_str: str | None) -> dict:
    """Parse meta JSON string, returning empty dict on failure."""
    if not meta_str:
        return {}
    try:
        return json.loads(meta_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def _escape_fts_query(q: str) -> str:
    """Escape user input for FTS5 query. Wrap in double quotes, escape internal quotes."""
    escaped = q.replace('"', '""')
    return f'"{escaped}"'


@router.get("")
async def list_memories(
    q: Optional[str] = Query(None, description="FTS search query"),
    namespace: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    sort: str = Query("created_at", description="Sort column"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """List memories with optional FTS search, filters, and pagination."""
    where_clauses = ["m.status != 'deleted'"]
    params: list = []

    # FTS search
    fts_join = ""
    if q:
        fts_join = "JOIN memories_fts ON memories_fts.rowid = m.rowid"
        where_clauses.append("memories_fts MATCH ?")
        params.append(_escape_fts_query(q))

    # Filters
    if namespace:
        where_clauses.append("m.namespace = ?")
        params.append(namespace)
    if memory_type:
        where_clauses.append("m.memory_type = ?")
        params.append(memory_type)
    if status:
        where_clauses = [c for c in where_clauses if "m.status != 'deleted'" not in c]
        where_clauses.append("m.status = ?")
        params.append(status)
    if branch:
        where_clauses.append("m.branch = ?")
        params.append(branch)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Validate sort column
    allowed_sorts = {"created_at", "importance", "namespace", "memory_type", "accessed_at", "content"}
    if sort not in allowed_sorts:
        sort = "created_at"
    sort_order = "ASC" if order.lower() == "asc" else "DESC"

    # Count query
    count_sql = f"""
        SELECT COUNT(*) as cnt FROM memories m
        {fts_join}
        WHERE {where_sql}
    """
    try:
        count_result = await query_spellbook_db(count_sql, tuple(params))
    except sqlite3.OperationalError as e:
        if "fts" in str(e).lower() or "malformed" in str(e).lower():
            return _error_response("INVALID_FTS_QUERY", str(e), 400)
        raise

    total = count_result[0]["cnt"] if count_result else 0
    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    # Data query with LEFT JOIN for citation_count
    data_sql = f"""
        SELECT m.id, m.content, m.memory_type, m.namespace, m.branch,
               m.importance, m.created_at, m.accessed_at, m.status, m.meta,
               COUNT(mc.id) as citation_count
        FROM memories m
        LEFT JOIN memory_citations mc ON m.id = mc.memory_id
        {fts_join}
        WHERE {where_sql}
        GROUP BY m.id
        ORDER BY m.{sort} {sort_order}
        LIMIT ? OFFSET ?
    """
    data_params = list(params) + [per_page, offset]

    try:
        rows = await query_spellbook_db(data_sql, tuple(data_params))
    except sqlite3.OperationalError as e:
        if "fts" in str(e).lower() or "malformed" in str(e).lower():
            return _error_response("INVALID_FTS_QUERY", str(e), 400)
        raise

    memories = []
    for row in rows:
        mem = dict(row)
        mem["meta"] = _parse_meta(mem.get("meta"))
        memories.append(mem)

    return {
        "memories": memories,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/namespaces")
async def list_namespaces(
    _session: str = Depends(require_admin_auth),
):
    """List distinct memory namespaces."""
    rows = await query_spellbook_db(
        "SELECT DISTINCT namespace FROM memories WHERE status != 'deleted' ORDER BY namespace"
    )
    return {"namespaces": [r["namespace"] for r in rows]}


@router.get("/stats")
async def memory_stats(
    _session: str = Depends(require_admin_auth),
):
    """Get aggregated memory statistics."""
    total_result = await query_spellbook_db("SELECT COUNT(*) as cnt FROM memories")
    total = total_result[0]["cnt"] if total_result else 0

    by_type_rows = await query_spellbook_db(
        "SELECT memory_type, COUNT(*) as cnt FROM memories GROUP BY memory_type"
    )
    by_type = {r["memory_type"] or "unknown": r["cnt"] for r in by_type_rows}

    by_status_rows = await query_spellbook_db(
        "SELECT status, COUNT(*) as cnt FROM memories GROUP BY status"
    )
    by_status = {r["status"]: r["cnt"] for r in by_status_rows}

    by_namespace_rows = await query_spellbook_db(
        "SELECT namespace, COUNT(*) as cnt FROM memories GROUP BY namespace"
    )
    by_namespace = {r["namespace"]: r["cnt"] for r in by_namespace_rows}

    return {
        "total": total,
        "by_type": by_type,
        "by_status": by_status,
        "by_namespace": by_namespace,
    }


@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Get a single memory with full content and citations."""
    rows = await query_spellbook_db(
        """
        SELECT m.id, m.content, m.memory_type, m.namespace, m.branch,
               m.importance, m.created_at, m.accessed_at, m.status, m.meta,
               COUNT(mc.id) as citation_count
        FROM memories m
        LEFT JOIN memory_citations mc ON m.id = mc.memory_id
        WHERE m.id = ?
        GROUP BY m.id
        """,
        (memory_id,),
    )
    if not rows:
        return _error_response("MEMORY_NOT_FOUND", f"Memory '{memory_id}' not found", 404)

    mem = dict(rows[0])
    mem["meta"] = _parse_meta(mem.get("meta"))

    # Fetch citations
    citations = await query_spellbook_db(
        "SELECT id, memory_id, file_path, line_range, content_snippet FROM memory_citations WHERE memory_id = ?",
        (memory_id,),
    )
    mem["citations"] = citations

    return mem


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: dict,
    _session: str = Depends(require_admin_auth),
):
    """Update a memory's content, importance, or metadata."""
    # Verify memory exists
    existing = await query_spellbook_db(
        "SELECT id, content, status FROM memories WHERE id = ?", (memory_id,)
    )
    if not existing:
        return _error_response("MEMORY_NOT_FOUND", f"Memory '{memory_id}' not found", 404)

    # Build SET clauses
    set_clauses = []
    params: list = []

    if "content" in body and body["content"] is not None:
        set_clauses.append("content = ?")
        params.append(body["content"])
        # Update content_hash when content changes
        set_clauses.append("content_hash = ?")
        params.append(hashlib.sha256(body["content"].encode()).hexdigest())

    if "importance" in body and body["importance"] is not None:
        set_clauses.append("importance = ?")
        params.append(body["importance"])

    if "meta" in body and body["meta"] is not None:
        set_clauses.append("meta = ?")
        params.append(json.dumps(body["meta"]))

    if not set_clauses:
        return _error_response("INVALID_REQUEST", "No valid fields to update", 400)

    params.append(memory_id)
    sql = f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ?"
    await execute_spellbook_db(sql, tuple(params))

    # Publish event
    await event_bus.publish(
        Event(
            subsystem=Subsystem.MEMORY,
            event_type="memory.updated",
            data={"memory_id": memory_id, "fields": list(body.keys())},
        )
    )

    return {"status": "ok", "memory_id": memory_id}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Soft-delete a memory by setting status to 'deleted'."""
    rows_affected = await execute_spellbook_db(
        "UPDATE memories SET status = 'deleted', deleted_at = datetime('now') WHERE id = ? AND status != 'deleted'",
        (memory_id,),
    )
    if rows_affected == 0:
        return _error_response("MEMORY_NOT_FOUND", f"Memory '{memory_id}' not found", 404)

    # Publish event
    await event_bus.publish(
        Event(
            subsystem=Subsystem.MEMORY,
            event_type="memory.deleted",
            data={"memory_id": memory_id},
        )
    )

    return {"status": "ok", "memory_id": memory_id}


@router.post("/consolidate")
async def trigger_consolidation(
    body: dict,
    _session: str = Depends(require_admin_auth),
):
    """Trigger memory consolidation for a namespace. Returns 409 if already running."""
    global _consolidation_running

    if _consolidation_running:
        return _error_response(
            "CONSOLIDATION_IN_PROGRESS",
            "A consolidation is already in progress",
            409,
        )

    namespace = body.get("namespace", "")
    max_events = body.get("max_events", 50)

    _consolidation_running = True
    try:
        db_path = str(get_db_path())
        result = await asyncio.to_thread(
            consolidate_batch, db_path, namespace, event_limit=max_events
        )
    finally:
        _consolidation_running = False

    # Publish event
    await event_bus.publish(
        Event(
            subsystem=Subsystem.MEMORY,
            event_type="memory.consolidated",
            data={
                "namespace": namespace,
                "memories_created": result.get("memories_created", 0),
                "events_consolidated": result.get("events_consolidated", 0),
            },
        )
    )

    return {
        "memories_created": result.get("memories_created", 0),
        "events_consolidated": result.get("events_consolidated", 0),
    }
