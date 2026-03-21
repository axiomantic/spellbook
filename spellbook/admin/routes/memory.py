"""Memory browser CRUD routes for admin interface.

Provides listing with FTS5 search, namespace/type/status filtering,
pagination, detail view with citations, update, soft delete,
consolidation trigger, namespace listing, and stats.

Uses SQLAlchemy ORM for all database access. FTS5 queries use the
text() escape hatch within ORM sessions (FTS5 virtual tables cannot
be mapped to ORM models).
"""

import asyncio
import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.admin.routes.list_helpers import build_list_response
from spellbook.core.db import get_db_path
from spellbook.db import spellbook_db
from spellbook.db.helpers import apply_pagination, apply_sorting
from spellbook.db.spellbook_models import Memory, MemoryCitation
from spellbook.memory.consolidation import consolidate_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memory"])

# Module-level flag for consolidation lock
_consolidation_running = False

# Sort whitelist for list endpoint
_SORT_WHITELIST = {"created_at", "importance", "namespace", "memory_type", "accessed_at", "content"}


def _error_response(code: str, message: str, status: int, details: list | None = None) -> JSONResponse:
    """Return a standardized ErrorResponse."""
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


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
    db: AsyncSession = Depends(spellbook_db),
    _session: str = Depends(require_admin_auth),
):
    """List memories with optional FTS search, filters, and pagination."""
    # When FTS search is active, we must use raw SQL with text() because
    # FTS5 virtual tables cannot be mapped to SQLAlchemy ORM models.
    if q:
        return await _list_memories_fts(
            db, q, namespace, memory_type, status, branch,
            sort, order, page, per_page,
        )

    # ORM query path (no FTS)
    query = select(Memory)

    # Default: exclude deleted
    if status:
        query = query.where(Memory.status == status)
    else:
        query = query.where(Memory.status != "deleted")

    if namespace:
        query = query.where(Memory.namespace == namespace)
    if memory_type:
        query = query.where(Memory.memory_type == memory_type)
    if branch:
        query = query.where(Memory.branch == branch)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_q)
    total = count_result.scalar_one()

    # Sort and paginate
    query = apply_sorting(query, Memory, sort, order, _SORT_WHITELIST)
    query = apply_pagination(query, page, per_page)

    result = await db.execute(query)
    memories = list(result.scalars().all())

    # Build items with citation_count
    items = []
    for mem in memories:
        d = mem.to_dict()
        # Get citation count for this memory
        cite_q = select(func.count(MemoryCitation.id)).where(
            MemoryCitation.memory_id == mem.id
        )
        cite_result = await db.execute(cite_q)
        d["citation_count"] = cite_result.scalar_one()
        items.append(d)

    return build_list_response(items, total, page, per_page)


async def _list_memories_fts(
    db: AsyncSession,
    q: str,
    namespace: Optional[str],
    memory_type: Optional[str],
    status: Optional[str],
    branch: Optional[str],
    sort: str,
    order: str,
    page: int,
    per_page: int,
):
    """List memories with FTS5 search using text() escape hatch."""
    fts_escaped = _escape_fts_query(q)

    where_clauses = ["m.status != 'deleted'"]
    params: dict = {"fts_query": fts_escaped}

    if status:
        where_clauses = [c for c in where_clauses if "m.status != 'deleted'" not in c]
        where_clauses.append("m.status = :status")
        params["status"] = status
    if namespace:
        where_clauses.append("m.namespace = :namespace")
        params["namespace"] = namespace
    if memory_type:
        where_clauses.append("m.memory_type = :memory_type")
        params["memory_type"] = memory_type
    if branch:
        where_clauses.append("m.branch = :branch")
        params["branch"] = branch

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Validate sort column
    if sort not in _SORT_WHITELIST:
        sort = "created_at"
    sort_order = "ASC" if order.lower() == "asc" else "DESC"

    # Count query
    count_sql = text(f"""
        SELECT COUNT(*) as cnt FROM memories m
        JOIN memories_fts ON memories_fts.rowid = m.rowid
        WHERE {where_sql}
        AND memories_fts MATCH :fts_query
    """)

    try:
        count_result = await db.execute(count_sql, params)
        total = count_result.scalar_one()
    except Exception as e:
        if "fts" in str(e).lower() or "malformed" in str(e).lower():
            return _error_response("INVALID_FTS_QUERY", str(e), 400)
        raise

    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    # Data query
    data_sql = text(f"""
        SELECT m.id, m.content, m.memory_type, m.namespace, m.branch,
               m.importance, m.created_at, m.accessed_at, m.status, m.meta,
               m.deleted_at, m.content_hash,
               COUNT(mc.id) as citation_count
        FROM memories m
        LEFT JOIN memory_citations mc ON m.id = mc.memory_id
        JOIN memories_fts ON memories_fts.rowid = m.rowid
        WHERE {where_sql}
        AND memories_fts MATCH :fts_query
        GROUP BY m.id
        ORDER BY m.{sort} {sort_order}
        LIMIT :limit OFFSET :offset
    """)
    data_params = {**params, "limit": per_page, "offset": offset}

    try:
        result = await db.execute(data_sql, data_params)
        rows = result.mappings().all()
    except Exception as e:
        if "fts" in str(e).lower() or "malformed" in str(e).lower():
            return _error_response("INVALID_FTS_QUERY", str(e), 400)
        raise

    items = []
    for row in rows:
        d = dict(row)
        # Parse meta JSON
        meta_str = d.get("meta")
        if meta_str:
            try:
                d["meta"] = json.loads(meta_str)
            except (json.JSONDecodeError, TypeError):
                d["meta"] = {}
        else:
            d["meta"] = {}
        items.append(d)

    return build_list_response(items, total, page, per_page)


@router.get("/namespaces")
async def list_namespaces(
    db: AsyncSession = Depends(spellbook_db),
    _session: str = Depends(require_admin_auth),
):
    """List distinct memory namespaces."""
    query = (
        select(Memory)
        .where(Memory.status != "deleted")
        .order_by(Memory.namespace)
    )
    result = await db.execute(query)
    memories = result.scalars().all()
    # Deduplicate namespaces preserving order
    seen = set()
    namespaces = []
    for m in memories:
        if m.namespace not in seen:
            seen.add(m.namespace)
            namespaces.append(m.namespace)
    return {"namespaces": namespaces}


@router.get("/stats")
async def memory_stats(
    db: AsyncSession = Depends(spellbook_db),
    _session: str = Depends(require_admin_auth),
):
    """Get aggregated memory statistics."""
    # Total count
    total_result = await db.execute(select(func.count(Memory.id)))
    total = total_result.scalar_one()

    # By type
    by_type_result = await db.execute(
        select(Memory.memory_type, func.count(Memory.id))
        .group_by(Memory.memory_type)
    )
    by_type = {(mt or "unknown"): cnt for mt, cnt in by_type_result.all()}

    # By status
    by_status_result = await db.execute(
        select(Memory.status, func.count(Memory.id))
        .group_by(Memory.status)
    )
    by_status = {s: cnt for s, cnt in by_status_result.all()}

    # By namespace
    by_ns_result = await db.execute(
        select(Memory.namespace, func.count(Memory.id))
        .group_by(Memory.namespace)
    )
    by_namespace = {ns: cnt for ns, cnt in by_ns_result.all()}

    return {
        "total": total,
        "by_type": by_type,
        "by_status": by_status,
        "by_namespace": by_namespace,
    }


@router.get("/{memory_id}")
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(spellbook_db),
    _session: str = Depends(require_admin_auth),
):
    """Get a single memory with full content and citations."""
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    mem = result.scalar_one_or_none()
    if mem is None:
        return _error_response("MEMORY_NOT_FOUND", f"Memory '{memory_id}' not found", 404)

    d = mem.to_dict()

    # Get citation count
    cite_count_result = await db.execute(
        select(func.count(MemoryCitation.id)).where(
            MemoryCitation.memory_id == memory_id
        )
    )
    d["citation_count"] = cite_count_result.scalar_one()

    # Fetch citations
    citations_result = await db.execute(
        select(MemoryCitation).where(MemoryCitation.memory_id == memory_id)
    )
    citations = citations_result.scalars().all()
    d["citations"] = [c.to_dict() for c in citations]

    return d


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: dict,
    db: AsyncSession = Depends(spellbook_db),
    _session: str = Depends(require_admin_auth),
):
    """Update a memory's content, importance, or metadata."""
    # Verify memory exists
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    mem = result.scalar_one_or_none()
    if mem is None:
        return _error_response("MEMORY_NOT_FOUND", f"Memory '{memory_id}' not found", 404)

    updated = False

    if "content" in body and body["content"] is not None:
        mem.content = body["content"]
        mem.content_hash = hashlib.sha256(body["content"].encode()).hexdigest()
        updated = True

    if "importance" in body and body["importance"] is not None:
        mem.importance = body["importance"]
        updated = True

    if "meta" in body and body["meta"] is not None:
        mem.meta = json.dumps(body["meta"])
        updated = True

    if not updated:
        return _error_response("INVALID_REQUEST", "No valid fields to update", 400)

    await db.flush()

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
    db: AsyncSession = Depends(spellbook_db),
    _session: str = Depends(require_admin_auth),
):
    """Soft-delete a memory by setting status to 'deleted'."""
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    mem = result.scalar_one_or_none()
    if mem is None or mem.status == "deleted":
        return _error_response("MEMORY_NOT_FOUND", f"Memory '{memory_id}' not found", 404)

    mem.status = "deleted"
    mem.deleted_at = datetime.now(timezone.utc).isoformat()
    await db.flush()

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
