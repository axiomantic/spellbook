"""Session content accumulator for split injection detection.

Tracks content fragments from external sources across tool calls
within a session. Triggers alerts when suspicious patterns emerge
(repeated source, volume threshold).
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from spellbook.core.db import get_db_path


_MAX_ENTRIES_PER_SESSION = 500
_REPEATED_SOURCE_THRESHOLD = 3


def do_accumulator_write(
    session_id: str,
    content_hash: str,
    source_tool: str,
    content_summary: str,
    content_size: int,
    db_path: str | None = None,
) -> dict:
    """Write a content entry to the session accumulator.

    Cleans up expired entries before inserting. Enforces max 500
    entries per session.

    Args:
        session_id: Current session identifier.
        content_hash: SHA-256 hash of the content.
        source_tool: Tool that produced the content.
        content_summary: First 500 chars of content.
        content_size: Total content size in bytes.
        db_path: Optional database path.

    Returns:
        Dict with success status and current entry count.
    """
    resolved = db_path or str(get_db_path())
    conn = sqlite3.connect(resolved)
    try:
        # Cleanup expired entries
        conn.execute(
            "DELETE FROM session_content_accumulator WHERE expires_at < datetime('now')"
        )

        # Enforce max entries per session
        count = conn.execute(
            "SELECT COUNT(*) FROM session_content_accumulator WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        if count >= _MAX_ENTRIES_PER_SESSION:
            excess = count - _MAX_ENTRIES_PER_SESSION + 1
            conn.execute(
                "DELETE FROM session_content_accumulator WHERE id IN "
                "(SELECT id FROM session_content_accumulator "
                "WHERE session_id = ? ORDER BY received_at ASC LIMIT ?)",
                (session_id, excess),
            )

        conn.execute(
            "INSERT INTO session_content_accumulator "
            "(session_id, content_hash, source_tool, content_summary, content_size) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, content_hash, source_tool, content_summary[:500], content_size),
        )
        conn.commit()

        new_count = conn.execute(
            "SELECT COUNT(*) FROM session_content_accumulator WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]

        return {"success": True, "entries_count": new_count}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def do_accumulator_status(
    session_id: str,
    db_path: str | None = None,
) -> dict:
    """Check session content accumulator state.

    Args:
        session_id: Session to check.
        db_path: Optional database path.

    Returns:
        Dict with entries count, total bytes, source distribution, and alerts.
    """
    resolved = db_path or str(get_db_path())
    conn = sqlite3.connect(resolved)
    try:
        rows = conn.execute(
            "SELECT source_tool, content_size, received_at "
            "FROM session_content_accumulator WHERE session_id = ? "
            "AND expires_at > datetime('now') ORDER BY received_at DESC",
            (session_id,),
        ).fetchall()

        entries = len(rows)
        total_bytes = sum(r[1] for r in rows)

        sources: dict[str, int] = {}
        for r in rows:
            sources[r[0]] = sources.get(r[0], 0) + 1

        # Generate alerts for repeated sources
        alerts: list[dict] = []
        for tool, count in sources.items():
            if count >= _REPEATED_SOURCE_THRESHOLD:
                alerts.append({
                    "type": "repeated_source",
                    "tool": tool,
                    "count": count,
                })

        # Check recent entries from same source within 5 minutes
        recent_rows = conn.execute(
            "SELECT source_tool, COUNT(*) as cnt "
            "FROM session_content_accumulator "
            "WHERE session_id = ? AND received_at > datetime('now', '-5 minutes') "
            "GROUP BY source_tool HAVING cnt >= ?",
            (session_id, _REPEATED_SOURCE_THRESHOLD),
        ).fetchall()
        for r in recent_rows:
            if not any(a["tool"] == r[0] and a["type"] == "burst_source" for a in alerts):
                alerts.append({
                    "type": "burst_source",
                    "tool": r[0],
                    "count": r[1],
                })

        return {
            "entries": entries,
            "total_content_bytes": total_bytes,
            "sources": sources,
            "alerts": alerts,
            "last_analysis": None,
        }
    except Exception as e:
        return {"entries": 0, "total_content_bytes": 0, "sources": {}, "alerts": [], "error": str(e)}
    finally:
        conn.close()
