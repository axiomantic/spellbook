"""Memory storage module: CRUD operations for the memory system.

All functions accept db_path as first argument to support testing with tmp_path.
Uses SQLAlchemy ORM sessions via spellbook.db.engines.get_sync_session.
FTS5 virtual table operations use text() queries within sessions.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from spellbook.db.engines import get_sync_session
from spellbook.db.spellbook_models import (
    Memory,
    MemoryAuditLog,
    MemoryBranch,
    MemoryCitation,
    MemoryLink,
    RawEvent,
)
from spellbook.memory.secrets import scan_for_secrets


def _content_hash(content: str) -> str:
    """SHA-256 of normalized content (lowercased, whitespace-collapsed)."""
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_citation_in_session(
    session: Session,
    memory_id: str,
    file_path: str,
    line_range: Optional[str] = None,
    snippet: Optional[str] = None,
) -> None:
    """Insert a citation within an existing session. Does NOT flush or commit.

    Uses INSERT OR IGNORE via text() to handle the UNIQUE constraint on
    (memory_id, file_path, line_range) without raising on duplicates.
    """
    session.execute(
        text(
            "INSERT OR IGNORE INTO memory_citations "
            "(memory_id, file_path, line_range, content_snippet) "
            "VALUES (:memory_id, :file_path, :line_range, :snippet)"
        ),
        {
            "memory_id": memory_id,
            "file_path": file_path,
            "line_range": line_range,
            "snippet": snippet,
        },
    )


def insert_memory(
    db_path: str,
    content: str,
    memory_type: str,
    namespace: str,
    tags: List[str],
    citations: List[Dict[str, Any]],
    importance: float = 1.0,
    extra_meta: Optional[Dict[str, Any]] = None,
    branch: str = "",
    scope: str = "project",
) -> str:
    """Insert a memory, deduplicating by content_hash. Returns memory ID.

    If a memory with the same content_hash already exists, returns its ID
    without inserting a duplicate.

    Scans content for secrets and flags findings in meta (never blocks).
    """
    c_hash = _content_hash(content)

    with get_sync_session(db_path) as session:
        # Dedup check
        existing = session.execute(
            select(Memory.id).where(
                Memory.content_hash == c_hash,
                Memory.namespace == namespace,
                Memory.scope == scope,
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        mem_id = str(uuid.uuid4())
        now = _now_iso()

        # Secret detection (flag, never block)
        meta: Dict[str, Any] = {"tags": tags}
        secret_findings = scan_for_secrets(content)
        if secret_findings:
            meta["secret_findings"] = secret_findings

        if extra_meta:
            meta.update(extra_meta)

        memory = Memory(
            id=mem_id,
            content=content,
            memory_type=memory_type,
            namespace=namespace,
            branch=branch,
            scope=scope,
            importance=importance,
            created_at=now,
            status="active",
            content_hash=c_hash,
            meta=json.dumps(meta),
        )
        session.add(memory)
        session.flush()

        # Get rowid for FTS5 (rowid is assigned by SQLite, need to query it)
        rowid = session.execute(
            text("SELECT rowid FROM memories WHERE id = :mem_id"),
            {"mem_id": mem_id},
        ).scalar_one()

        # Insert into FTS5 (standalone table -- must be kept in sync manually)
        citation_paths = " ".join(c.get("file_path", "") for c in citations)
        session.execute(
            text(
                "INSERT INTO memories_fts (rowid, content, tags, citations) "
                "VALUES (:rowid, :content, :tags, :citations)"
            ),
            {
                "rowid": rowid,
                "content": content,
                "tags": " ".join(tags),
                "citations": citation_paths,
            },
        )

        # Insert citations
        for cit in citations:
            _insert_citation_in_session(
                session, mem_id,
                cit["file_path"],
                cit.get("line_range"),
                cit.get("snippet"),
            )

        # Populate junction table with origin association
        if branch:
            branch_assoc = MemoryBranch(
                memory_id=mem_id,
                branch_name=branch,
                association_type="origin",
                created_at=now,
            )
            session.merge(branch_assoc)

    # Audit log after successful commit (separate transaction)
    log_audit(db_path, "create", mem_id, {"memory_type": memory_type})
    return mem_id


def get_memory(db_path: str, memory_id: str) -> Optional[Dict[str, Any]]:
    """Get a single memory by ID, including its citations. Returns None if not found."""
    with get_sync_session(db_path) as session:
        memory = session.get(Memory, memory_id)
        if memory is None:
            return None

        mem = {
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "namespace": memory.namespace,
            "branch": memory.branch,
            "importance": memory.importance,
            "created_at": memory.created_at,
            "accessed_at": memory.accessed_at,
            "status": memory.status,
            "deleted_at": memory.deleted_at,
            "content_hash": memory.content_hash,
            "meta": memory.meta,
        }

        # Fetch citations
        cit_rows = session.execute(
            select(
                MemoryCitation.file_path,
                MemoryCitation.line_range,
                MemoryCitation.content_snippet,
            ).where(MemoryCitation.memory_id == memory_id)
        ).all()
        mem["citations"] = [
            {"file_path": r[0], "line_range": r[1], "snippet": r[2]}
            for r in cit_rows
        ]
        return mem


def soft_delete_memory(db_path: str, memory_id: str) -> None:
    """Soft-delete a memory (set status='deleted', deleted_at=now).
    Also removes from FTS5 index."""
    now = _now_iso()

    with get_sync_session(db_path) as session:
        # Get rowid for FTS5 cleanup
        rowid = session.execute(
            text("SELECT rowid FROM memories WHERE id = :mem_id"),
            {"mem_id": memory_id},
        ).scalar_one_or_none()

        if rowid is not None:
            session.execute(
                text("DELETE FROM memories_fts WHERE rowid = :rowid"),
                {"rowid": rowid},
            )

        memory = session.get(Memory, memory_id)
        if memory is not None:
            memory.status = "deleted"
            memory.deleted_at = now

    log_audit(db_path, "delete", memory_id, {"soft": True})


def insert_citation(
    db_path: str,
    memory_id: str,
    file_path: str,
    line_range: Optional[str] = None,
    snippet: Optional[str] = None,
) -> None:
    """Insert a citation for a memory. Ignores duplicates.

    Note: Uses its own session and commits on completion.
    When called from insert_memory, the internal _insert_citation_in_session
    helper is used instead to share the parent transaction.
    """
    with get_sync_session(db_path) as session:
        _insert_citation_in_session(session, memory_id, file_path, line_range, snippet)


def insert_link(
    db_path: str,
    memory_a: str,
    memory_b: str,
    link_type: str,
    weight: float = 1.0,
) -> None:
    """Insert or update a link between two memories."""
    now = _now_iso()
    # Normalize order for consistency
    a, b = (memory_a, memory_b) if memory_a < memory_b else (memory_b, memory_a)

    with get_sync_session(db_path) as session:
        # Use text() for ON CONFLICT upsert since ORM merge doesn't support
        # the DO UPDATE SET pattern needed here
        session.execute(
            text(
                "INSERT INTO memory_links (memory_a, memory_b, link_type, weight, last_seen) "
                "VALUES (:a, :b, :link_type, :weight, :now) "
                "ON CONFLICT(memory_a, memory_b, link_type) DO UPDATE SET "
                "weight = excluded.weight, last_seen = excluded.last_seen"
            ),
            {"a": a, "b": b, "link_type": link_type, "weight": weight, "now": now},
        )


def log_raw_event(
    db_path: str,
    session_id: str,
    project: str,
    event_type: str,
    tool_name: str,
    subject: str,
    summary: str,
    tags: str,
    branch: str = "",
) -> int:
    """Log a raw observation event. Returns the event ID."""
    now = _now_iso()

    with get_sync_session(db_path) as session:
        event = RawEvent(
            session_id=session_id,
            timestamp=now,
            project=project,
            event_type=event_type,
            tool_name=tool_name,
            subject=subject,
            summary=summary,
            tags=tags,
            branch=branch,
            consolidated=0,
        )
        session.add(event)
        session.flush()
        return event.id


def get_unconsolidated_events(
    db_path: str,
    limit: int = 50,
    namespace: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get unconsolidated raw events, optionally filtered by namespace (project)."""
    with get_sync_session(db_path) as session:
        stmt = select(RawEvent).where(RawEvent.consolidated == 0)
        if namespace:
            stmt = stmt.where(RawEvent.project == namespace)
        stmt = stmt.order_by(RawEvent.id.asc()).limit(limit)

        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id, "session_id": r.session_id, "timestamp": r.timestamp,
                "project": r.project, "event_type": r.event_type,
                "tool_name": r.tool_name, "subject": r.subject,
                "summary": r.summary, "tags": r.tags, "branch": r.branch,
            }
            for r in rows
        ]


def get_recently_consolidated_events(
    db_path: str,
    limit: int = 50,
    namespace: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get events consolidated within the last 24 hours.

    Used by memory_get_unconsolidated with include_consolidated=True
    to allow client re-synthesis of recently consolidated events.
    """
    with get_sync_session(db_path) as session:
        # Use text() for SQLite datetime function
        stmt = text(
            "SELECT id, session_id, timestamp, project, event_type, tool_name, "
            "subject, summary, tags, branch FROM raw_events "
            "WHERE consolidated = 1 AND timestamp > datetime('now', '-24 hours') "
            + ("AND project = :namespace " if namespace else "")
            + "ORDER BY id ASC LIMIT :limit"
        )
        params: Dict[str, Any] = {"limit": limit}
        if namespace:
            params["namespace"] = namespace

        rows = session.execute(stmt, params).all()
        return [
            {
                "id": r[0], "session_id": r[1], "timestamp": r[2],
                "project": r[3], "event_type": r[4], "tool_name": r[5],
                "subject": r[6], "summary": r[7], "tags": r[8], "branch": r[9],
            }
            for r in rows
        ]


def mark_events_consolidated(
    db_path: str, event_ids: List[int], batch_id: str,
    namespace: Optional[str] = None,
) -> int:
    """Mark raw events as consolidated with a batch ID.

    Args:
        db_path: Database path.
        event_ids: Event IDs to mark.
        batch_id: Consolidation batch identifier.
        namespace: If provided, only mark events belonging to this project.
            Prevents marking events from other namespaces.

    Returns:
        Number of events actually marked.
    """
    if not event_ids:
        return 0

    with get_sync_session(db_path) as session:
        # Build parameterized IN clause for dynamic event_ids list
        placeholders = ", ".join(f":id_{i}" for i in range(len(event_ids)))
        query = (
            f"UPDATE raw_events SET consolidated = 1, batch_id = :batch_id "
            f"WHERE id IN ({placeholders})"
        )
        params: Dict[str, Any] = {"batch_id": batch_id}
        for i, eid in enumerate(event_ids):
            params[f"id_{i}"] = eid

        if namespace:
            query += " AND project = :namespace"
            params["namespace"] = namespace

        result = session.execute(text(query), params)
        return result.rowcount


def _apply_branch_scoring(
    db_path: str,
    results: List[Dict[str, Any]],
    branch: str,
    repo_path: str,
    limit: int,
) -> List[Dict[str, Any]]:
    """Apply ancestry-aware branch weighting to recall results.

    Phase 2 of two-phase scoring: multiplies _score by branch relationship
    multiplier, re-sorts, strips internal score, and truncates to limit.
    Also lazily populates the junction table for ancestor relationships.
    """
    from spellbook.core.branch_ancestry import (
        BRANCH_MULTIPLIERS,
        BranchRelationship,
        get_branch_relationship,
    )

    for mem in results:
        mem_branch = mem.get("branch", "")
        relationship = get_branch_relationship(repo_path, branch, mem_branch)
        multiplier = BRANCH_MULTIPLIERS.get(relationship, 1.0)
        mem["_score"] = mem.get("_score", 1.0) * multiplier
        mem["branch_relationship"] = relationship.value

        # Lazy junction table population for ancestor relationships
        if relationship == BranchRelationship.ANCESTOR and branch:
            insert_branch_association(db_path, mem["id"], branch, "ancestor")

    results.sort(key=lambda m: m.get("_score", 0), reverse=True)
    for r in results:
        r.pop("_score", None)
    return results[:limit]


def recall_by_file_path(
    db_path: str,
    file_path: str,
    namespace: str,
    limit: int = 5,
    branch: str = "",
    repo_path: str = "",
    scope: str = "project",
) -> List[Dict[str, Any]]:
    """Recall memories by cited file path (inverted index lookup).

    Uses unified relevance score: importance * temporal_decay * status_penalty.
    When branch and repo_path are provided, applies two-phase scoring:
    1. SQL phase: over-fetch candidates with base score (no branch multiplier)
    2. Python phase: apply ancestry-aware branch multiplier, re-sort, truncate
    """
    fetch_limit = limit * 2 if branch else limit

    with get_sync_session(db_path) as session:
        # Build scope filter for SQL
        if scope == "project":
            scope_filter = "AND m.namespace = :namespace AND m.scope = 'project'"
        elif scope == "global":
            scope_filter = "AND m.scope = 'global'"
        elif scope == "all":
            scope_filter = "AND (m.namespace = :namespace OR m.scope = 'global')"
        else:
            scope_filter = "AND m.namespace = :namespace"

        # Use text() for SQLite-specific functions (julianday, exp)
        rows = session.execute(
            text(
                "SELECT m.id, m.content, m.memory_type, m.importance, m.status, m.meta, "
                "m.created_at, m.accessed_at, m.branch, m.scope, "
                "m.importance * "
                "  exp(-0.0077 * (julianday('now') - julianday(m.created_at))) * "
                "  CASE m.status WHEN 'active' THEN 1.0 ELSE 0.3 END AS _score "
                "FROM memories m "
                "JOIN memory_citations mc ON m.id = mc.memory_id "
                f"WHERE mc.file_path = :file_path {scope_filter} "
                "AND m.status != 'deleted' "
                "ORDER BY _score DESC "
                "LIMIT :limit"
            ),
            {"file_path": file_path, "namespace": namespace, "limit": fetch_limit},
        ).all()

        results = [
            {
                "id": r[0], "content": r[1], "memory_type": r[2],
                "importance": r[3], "status": r[4], "meta": r[5],
                "created_at": r[6], "accessed_at": r[7], "branch": r[8],
                "scope": r[9], "_score": r[10],
            }
            for r in rows
        ]

    if not branch or not repo_path:
        for r in results:
            r.pop("_score", None)
        return results[:limit]

    # Phase 2: Apply ancestry-aware branch weighting
    return _apply_branch_scoring(db_path, results, branch, repo_path, limit)


def recall_by_query(
    db_path: str,
    query: str,
    namespace: str,
    limit: int = 10,
    branch: str = "",
    repo_path: str = "",
    scope: str = "project",
) -> List[Dict[str, Any]]:
    """Recall memories by FTS5 query. Empty query returns recent+important.

    Uses unified relevance score: (-bm25) * importance * temporal_decay * status_penalty.
    When branch and repo_path are provided, applies two-phase scoring:
    1. SQL phase: over-fetch candidates
    2. Python phase: apply branch multiplier, re-sort, truncate

    Escapes user input by wrapping in double-quotes to prevent FTS5 operator injection.
    """
    fetch_limit = limit * 2 if branch else limit

    with get_sync_session(db_path) as session:
        if not query.strip():
            from sqlalchemy import or_

            stmt = select(
                Memory.id, Memory.content, Memory.memory_type,
                Memory.importance, Memory.status, Memory.meta,
                Memory.created_at, Memory.accessed_at, Memory.branch,
                Memory.scope,
            )
            if scope == "project":
                stmt = stmt.where(
                    Memory.namespace == namespace,
                    Memory.scope == "project",
                    Memory.status == "active",
                )
            elif scope == "global":
                stmt = stmt.where(
                    Memory.scope == "global",
                    Memory.status == "active",
                )
            elif scope == "all":
                stmt = stmt.where(
                    or_(
                        Memory.namespace == namespace,
                        Memory.scope == "global",
                    ),
                    Memory.status == "active",
                )
            else:
                stmt = stmt.where(
                    Memory.namespace == namespace,
                    Memory.status == "active",
                )
            stmt = stmt.order_by(
                Memory.importance.desc(),
                Memory.created_at.desc(),
            ).limit(fetch_limit)
            rows = session.execute(stmt).all()
            results = [
                {
                    "id": r[0], "content": r[1], "memory_type": r[2],
                    "importance": r[3], "status": r[4], "meta": r[5],
                    "created_at": r[6], "accessed_at": r[7], "branch": r[8],
                    "scope": r[9],
                    "_score": r[3],  # importance as base score for empty query
                }
                for r in rows
            ]
        else:
            # Escape user input: wrap in double-quotes to force phrase matching
            # and prevent FTS5 operator injection (e.g., OR, AND, NOT, NEAR).
            safe_query = '"' + query.replace('"', '""') + '"'

            if scope == "project":
                scope_filter = "AND m.namespace = :namespace AND m.scope = 'project'"
            elif scope == "global":
                scope_filter = "AND m.scope = 'global'"
            elif scope == "all":
                scope_filter = "AND (m.namespace = :namespace OR m.scope = 'global')"
            else:
                scope_filter = "AND m.namespace = :namespace"

            rows = session.execute(
                text(
                    "SELECT m.id, m.content, m.memory_type, m.importance, m.status, "
                    "m.meta, m.created_at, m.accessed_at, m.branch, m.scope, "
                    "(-bm25(memories_fts, 5.0, 2.0, 1.0)) * m.importance * "
                    "  exp(-0.0077 * (julianday('now') - julianday(m.created_at))) * "
                    "  CASE m.status WHEN 'active' THEN 1.0 ELSE 0.3 END AS _score "
                    "FROM memories_fts fts "
                    "JOIN memories m ON m.rowid = fts.rowid "
                    f"WHERE memories_fts MATCH :query {scope_filter} "
                    "AND m.status != 'deleted' "
                    "ORDER BY _score DESC "
                    "LIMIT :limit"
                ),
                {"query": safe_query, "namespace": namespace, "limit": fetch_limit},
            ).all()
            results = [
                {
                    "id": r[0], "content": r[1], "memory_type": r[2],
                    "importance": r[3], "status": r[4], "meta": r[5],
                    "created_at": r[6], "accessed_at": r[7], "branch": r[8],
                    "scope": r[9], "_score": r[10],
                }
                for r in rows
            ]

    if not branch or not repo_path:
        # Strip internal score before returning
        for r in results:
            r.pop("_score", None)
        return results[:limit]

    # Phase 2: Apply branch weighting
    return _apply_branch_scoring(db_path, results, branch, repo_path, limit)


def update_access(db_path: str, memory_id: str) -> None:
    """Update accessed_at and increment importance by +0.1 (capped at 10.0)."""
    now = _now_iso()

    with get_sync_session(db_path) as session:
        # Use text() for SQLite MIN function in UPDATE
        session.execute(
            text(
                "UPDATE memories SET accessed_at = :now, "
                "importance = MIN(importance + 0.1, 10.0) "
                "WHERE id = :mem_id"
            ),
            {"now": now, "mem_id": memory_id},
        )


def purge_deleted(db_path: str, retention_days: int = 30) -> int:
    """Hard-delete memories that were soft-deleted more than retention_days ago.
    Returns count of purged memories."""
    with get_sync_session(db_path) as session:
        # Use text() for SQLite datetime arithmetic
        rows = session.execute(
            text(
                "SELECT id FROM memories WHERE status = 'deleted' "
                "AND deleted_at < datetime('now', :offset || ' days')"
            ),
            {"offset": f"-{retention_days}"},
        ).all()
        ids = [r[0] for r in rows]
        if not ids:
            return 0

        # Build parameterized IN clause
        placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
        id_params = {f"id_{i}": mid for i, mid in enumerate(ids)}

        session.execute(
            text(f"DELETE FROM memory_citations WHERE memory_id IN ({placeholders})"),
            id_params,
        )
        # memory_links needs both memory_a and memory_b checked
        # Build separate params for both sides to avoid ambiguity
        a_params = {f"a_{i}": mid for i, mid in enumerate(ids)}
        b_params = {f"b_{i}": mid for i, mid in enumerate(ids)}
        a_placeholders = ", ".join(f":a_{i}" for i in range(len(ids)))
        b_placeholders = ", ".join(f":b_{i}" for i in range(len(ids)))
        session.execute(
            text(
                f"DELETE FROM memory_links WHERE memory_a IN ({a_placeholders}) "
                f"OR memory_b IN ({b_placeholders})"
            ),
            {**a_params, **b_params},
        )
        session.execute(
            text(f"DELETE FROM memory_branches WHERE memory_id IN ({placeholders})"),
            id_params,
        )
        session.execute(
            text(f"DELETE FROM memories WHERE id IN ({placeholders})"),
            id_params,
        )

    for mid in ids:
        log_audit(db_path, "purge", mid, {"retention_days": retention_days})
    return len(ids)


def log_audit(
    db_path: str,
    action: str,
    memory_id: Optional[str] = None,
    details: Optional[Dict] = None,
) -> None:
    """Write an entry to the memory audit log."""
    now = _now_iso()

    with get_sync_session(db_path) as session:
        audit = MemoryAuditLog(
            timestamp=now,
            action=action,
            memory_id=memory_id,
            details=json.dumps(details) if details else None,
        )
        session.add(audit)


def insert_branch_association(
    db_path: str,
    memory_id: str,
    branch_name: str,
    association_type: str = "origin",
) -> None:
    """Insert a branch association for a memory. Idempotent (ignores duplicates)."""
    now = _now_iso()

    with get_sync_session(db_path) as session:
        # Use text() for INSERT OR IGNORE since ORM doesn't support it directly
        session.execute(
            text(
                "INSERT OR IGNORE INTO memory_branches "
                "(memory_id, branch_name, association_type, created_at) "
                "VALUES (:memory_id, :branch_name, :association_type, :created_at)"
            ),
            {
                "memory_id": memory_id,
                "branch_name": branch_name,
                "association_type": association_type,
                "created_at": now,
            },
        )


def get_branch_associations(
    db_path: str, memory_id: str
) -> List[Dict[str, str]]:
    """Get all branch associations for a memory."""
    with get_sync_session(db_path) as session:
        rows = session.execute(
            select(
                MemoryBranch.branch_name,
                MemoryBranch.association_type,
                MemoryBranch.created_at,
            ).where(MemoryBranch.memory_id == memory_id)
        ).all()
        return [
            {"branch": r[0], "type": r[1], "created_at": r[2]}
            for r in rows
        ]
