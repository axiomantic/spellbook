"""Memory storage module: CRUD operations for the memory system.

All functions accept db_path as first argument to support testing with tmp_path.
Uses the shared connection pool from spellbook_mcp.db.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from spellbook_mcp.db import get_connection
from spellbook_mcp.memory_secrets import scan_for_secrets


def _content_hash(content: str) -> str:
    """SHA-256 of normalized content (lowercased, whitespace-collapsed)."""
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_memory(
    db_path: str,
    content: str,
    memory_type: str,
    namespace: str,
    tags: List[str],
    citations: List[Dict[str, Any]],
    importance: float = 1.0,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a memory, deduplicating by content_hash. Returns memory ID.

    If a memory with the same content_hash already exists, returns its ID
    without inserting a duplicate.

    Scans content for secrets and flags findings in meta (never blocks).
    """
    conn = get_connection(db_path)
    c_hash = _content_hash(content)

    # Dedup check
    cursor = conn.execute(
        "SELECT id FROM memories WHERE content_hash = ? AND namespace = ?",
        (c_hash, namespace),
    )
    existing = cursor.fetchone()
    if existing:
        return existing[0]

    mem_id = str(uuid.uuid4())
    now = _now_iso()

    # Secret detection (flag, never block)
    meta: Dict[str, Any] = {"tags": tags}
    secret_findings = scan_for_secrets(content)
    if secret_findings:
        meta["secret_findings"] = secret_findings

    if extra_meta:
        meta.update(extra_meta)

    conn.execute(
        "INSERT INTO memories (id, content, memory_type, namespace, importance, "
        "created_at, status, content_hash, meta) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
        (mem_id, content, memory_type, namespace, importance, now, c_hash,
         json.dumps(meta)),
    )

    # Get rowid for FTS5
    cursor = conn.execute("SELECT rowid FROM memories WHERE id = ?", (mem_id,))
    rowid = cursor.fetchone()[0]

    # Insert into FTS5 (standalone table -- must be kept in sync manually)
    citation_paths = " ".join(c.get("file_path", "") for c in citations)
    conn.execute(
        "INSERT INTO memories_fts (rowid, content, tags, citations) VALUES (?, ?, ?, ?)",
        (rowid, content, " ".join(tags), citation_paths),
    )

    # Insert citations
    for cit in citations:
        insert_citation(
            db_path, mem_id,
            cit["file_path"],
            cit.get("line_range"),
            cit.get("snippet"),
        )

    conn.commit()
    log_audit(db_path, "create", mem_id, {"memory_type": memory_type})
    return mem_id


def get_memory(db_path: str, memory_id: str) -> Optional[Dict[str, Any]]:
    """Get a single memory by ID, including its citations. Returns None if not found."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT id, content, memory_type, namespace, importance, created_at, "
        "accessed_at, status, deleted_at, content_hash, meta "
        "FROM memories WHERE id = ?",
        (memory_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    mem = {
        "id": row[0], "content": row[1], "memory_type": row[2],
        "namespace": row[3], "importance": row[4], "created_at": row[5],
        "accessed_at": row[6], "status": row[7], "deleted_at": row[8],
        "content_hash": row[9], "meta": row[10],
    }

    # Fetch citations
    cit_cursor = conn.execute(
        "SELECT file_path, line_range, content_snippet FROM memory_citations "
        "WHERE memory_id = ?",
        (memory_id,),
    )
    mem["citations"] = [
        {"file_path": r[0], "line_range": r[1], "snippet": r[2]}
        for r in cit_cursor.fetchall()
    ]
    return mem


def soft_delete_memory(db_path: str, memory_id: str) -> None:
    """Soft-delete a memory (set status='deleted', deleted_at=now).
    Also removes from FTS5 index."""
    conn = get_connection(db_path)
    now = _now_iso()

    # Get rowid for FTS5 cleanup
    cursor = conn.execute("SELECT rowid FROM memories WHERE id = ?", (memory_id,))
    row = cursor.fetchone()
    if row:
        conn.execute(
            "DELETE FROM memories_fts WHERE rowid = ?", (row[0],)
        )

    conn.execute(
        "UPDATE memories SET status = 'deleted', deleted_at = ? WHERE id = ?",
        (now, memory_id),
    )
    conn.commit()
    log_audit(db_path, "delete", memory_id, {"soft": True})


def insert_citation(
    db_path: str,
    memory_id: str,
    file_path: str,
    line_range: Optional[str] = None,
    snippet: Optional[str] = None,
) -> None:
    """Insert a citation for a memory. Ignores duplicates.

    Note: Does NOT commit. The caller (insert_memory or consolidate_batch)
    manages the transaction boundary. This prevents partial citation state
    on crash and reduces I/O from per-citation commits.
    """
    conn = get_connection(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO memory_citations (memory_id, file_path, line_range, content_snippet) "
        "VALUES (?, ?, ?, ?)",
        (memory_id, file_path, line_range, snippet),
    )


def insert_link(
    db_path: str,
    memory_a: str,
    memory_b: str,
    link_type: str,
    weight: float = 1.0,
) -> None:
    """Insert or update a link between two memories."""
    conn = get_connection(db_path)
    now = _now_iso()
    # Normalize order for consistency
    a, b = (memory_a, memory_b) if memory_a < memory_b else (memory_b, memory_a)
    conn.execute(
        "INSERT INTO memory_links (memory_a, memory_b, link_type, weight, last_seen) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(memory_a, memory_b, link_type) DO UPDATE SET "
        "weight = excluded.weight, last_seen = excluded.last_seen",
        (a, b, link_type, weight, now),
    )
    conn.commit()


def log_raw_event(
    db_path: str,
    session_id: str,
    project: str,
    event_type: str,
    tool_name: str,
    subject: str,
    summary: str,
    tags: str,
) -> int:
    """Log a raw observation event. Returns the event ID."""
    conn = get_connection(db_path)
    now = _now_iso()
    cursor = conn.execute(
        "INSERT INTO raw_events (session_id, timestamp, project, event_type, "
        "tool_name, subject, summary, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, now, project, event_type, tool_name, subject, summary, tags),
    )
    conn.commit()
    return cursor.lastrowid


def get_unconsolidated_events(
    db_path: str,
    limit: int = 50,
    namespace: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get unconsolidated raw events, optionally filtered by namespace (project)."""
    conn = get_connection(db_path)
    if namespace:
        cursor = conn.execute(
            "SELECT id, session_id, timestamp, project, event_type, tool_name, "
            "subject, summary, tags FROM raw_events "
            "WHERE consolidated = 0 AND project = ? ORDER BY id ASC LIMIT ?",
            (namespace, limit),
        )
    else:
        cursor = conn.execute(
            "SELECT id, session_id, timestamp, project, event_type, tool_name, "
            "subject, summary, tags FROM raw_events "
            "WHERE consolidated = 0 ORDER BY id ASC LIMIT ?",
            (limit,),
        )
    return [
        {
            "id": r[0], "session_id": r[1], "timestamp": r[2],
            "project": r[3], "event_type": r[4], "tool_name": r[5],
            "subject": r[6], "summary": r[7], "tags": r[8],
        }
        for r in cursor.fetchall()
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
    conn = get_connection(db_path)
    if namespace:
        cursor = conn.execute(
            "SELECT id, session_id, timestamp, project, event_type, tool_name, "
            "subject, summary, tags FROM raw_events "
            "WHERE consolidated = 1 AND timestamp > datetime('now', '-24 hours') "
            "AND project = ? ORDER BY id ASC LIMIT ?",
            (namespace, limit),
        )
    else:
        cursor = conn.execute(
            "SELECT id, session_id, timestamp, project, event_type, tool_name, "
            "subject, summary, tags FROM raw_events "
            "WHERE consolidated = 1 AND timestamp > datetime('now', '-24 hours') "
            "ORDER BY id ASC LIMIT ?",
            (limit,),
        )
    return [
        {
            "id": r[0], "session_id": r[1], "timestamp": r[2],
            "project": r[3], "event_type": r[4], "tool_name": r[5],
            "subject": r[6], "summary": r[7], "tags": r[8],
        }
        for r in cursor.fetchall()
    ]


def mark_events_consolidated(
    db_path: str, event_ids: List[int], batch_id: str
) -> None:
    """Mark raw events as consolidated with a batch ID."""
    if not event_ids:
        return
    conn = get_connection(db_path)
    placeholders = ",".join("?" for _ in event_ids)
    conn.execute(
        f"UPDATE raw_events SET consolidated = 1, batch_id = ? "
        f"WHERE id IN ({placeholders})",
        [batch_id] + event_ids,
    )
    conn.commit()


def recall_by_file_path(
    db_path: str,
    file_path: str,
    namespace: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Recall memories by cited file path (inverted index lookup).

    Uses unified relevance score: importance * temporal_decay * status_penalty.
    """
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT m.id, m.content, m.memory_type, m.importance, m.status, m.meta, "
        "m.created_at, m.accessed_at "
        "FROM memories m "
        "JOIN memory_citations mc ON m.id = mc.memory_id "
        "WHERE mc.file_path = ? AND m.namespace = ? AND m.status != 'deleted' "
        "ORDER BY m.importance * "
        "  exp(-0.0077 * (julianday('now') - julianday(m.created_at))) * "
        "  CASE m.status WHEN 'active' THEN 1.0 ELSE 0.3 END DESC "
        "LIMIT ?",
        (file_path, namespace, limit),
    )
    results = []
    for r in cursor.fetchall():
        results.append({
            "id": r[0], "content": r[1], "memory_type": r[2],
            "importance": r[3], "status": r[4], "meta": r[5],
            "created_at": r[6], "accessed_at": r[7],
        })
    return results


def recall_by_query(
    db_path: str,
    query: str,
    namespace: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Recall memories by FTS5 query. Empty query returns recent+important.

    Uses unified relevance score: (-bm25) * importance * temporal_decay * status_penalty.
    Escapes user input by wrapping in double-quotes to prevent FTS5 operator injection.
    """
    conn = get_connection(db_path)
    if not query.strip():
        cursor = conn.execute(
            "SELECT id, content, memory_type, importance, status, meta, "
            "created_at, accessed_at "
            "FROM memories WHERE namespace = ? AND status = 'active' "
            "ORDER BY importance DESC, created_at DESC LIMIT ?",
            (namespace, limit),
        )
    else:
        # Escape user input: wrap in double-quotes to force phrase matching
        # and prevent FTS5 operator injection (e.g., OR, AND, NOT, NEAR).
        safe_query = '"' + query.replace('"', '""') + '"'
        cursor = conn.execute(
            "SELECT m.id, m.content, m.memory_type, m.importance, m.status, "
            "m.meta, m.created_at, m.accessed_at, "
            "(-bm25(memories_fts, 5.0, 2.0, 1.0)) AS bm25_score "
            "FROM memories_fts fts "
            "JOIN memories m ON m.rowid = fts.rowid "
            "WHERE memories_fts MATCH ? AND m.namespace = ? AND m.status != 'deleted' "
            "ORDER BY bm25_score * m.importance * "
            "  exp(-0.0077 * (julianday('now') - julianday(m.created_at))) * "
            "  CASE m.status WHEN 'active' THEN 1.0 ELSE 0.3 END DESC "
            "LIMIT ?",
            (safe_query, namespace, limit),
        )
    return [
        {
            "id": r[0], "content": r[1], "memory_type": r[2],
            "importance": r[3], "status": r[4], "meta": r[5],
            "created_at": r[6], "accessed_at": r[7],
        }
        for r in cursor.fetchall()
    ]


def update_access(db_path: str, memory_id: str) -> None:
    """Update accessed_at and increment importance by +0.1 (capped at 10.0)."""
    conn = get_connection(db_path)
    now = _now_iso()
    conn.execute(
        "UPDATE memories SET accessed_at = ?, "
        "importance = MIN(importance + 0.1, 10.0) "
        "WHERE id = ?",
        (now, memory_id),
    )
    conn.commit()


def purge_deleted(db_path: str, retention_days: int = 30) -> int:
    """Hard-delete memories that were soft-deleted more than retention_days ago.
    Returns count of purged memories."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT id FROM memories WHERE status = 'deleted' "
        "AND deleted_at < datetime('now', ? || ' days')",
        (f"-{retention_days}",),
    )
    ids = [r[0] for r in cursor.fetchall()]
    if not ids:
        return 0

    placeholders = ",".join("?" for _ in ids)
    conn.execute(f"DELETE FROM memory_citations WHERE memory_id IN ({placeholders})", ids)
    conn.execute(
        f"DELETE FROM memory_links WHERE memory_a IN ({placeholders}) OR memory_b IN ({placeholders})",
        ids + ids,
    )
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
    conn.commit()

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
    conn = get_connection(db_path)
    now = _now_iso()
    conn.execute(
        "INSERT INTO memory_audit_log (timestamp, action, memory_id, details) "
        "VALUES (?, ?, ?, ?)",
        (now, action, memory_id, json.dumps(details) if details else None),
    )
    conn.commit()
