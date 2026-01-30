"""
Context Curator MCP tools for analytics tracking.
"""

import json
from datetime import datetime, timezone
from typing import Any

from .db import get_connection


def init_curator_tables() -> None:
    """Initialize curator database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS curator_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            tool_ids TEXT NOT NULL,
            tokens_saved INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_curator_session 
        ON curator_events(session_id)
    """)

    conn.commit()


async def curator_track_prune(
    session_id: str,
    tool_ids: list[str],
    tokens_saved: int,
    strategy: str
) -> dict[str, Any]:
    """
    Track a pruning event for analytics.

    Args:
        session_id: The session identifier
        tool_ids: List of tool IDs that were pruned
        tokens_saved: Estimated tokens saved by this prune
        strategy: The strategy that triggered the prune

    Returns:
        Status dict with event_id
    """
    conn = get_connection()
    cursor = conn.cursor()

    timestamp = datetime.now(timezone.utc).isoformat()
    tool_ids_json = json.dumps(tool_ids)

    cursor.execute(
        """
        INSERT INTO curator_events (session_id, tool_ids, tokens_saved, strategy, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, tool_ids_json, tokens_saved, strategy, timestamp)
    )

    event_id = cursor.lastrowid
    conn.commit()

    return {
        "success": True,
        "event_id": event_id,
        "session_id": session_id,
        "tools_pruned": len(tool_ids),
    }


async def curator_get_stats(session_id: str) -> dict[str, Any]:
    """
    Get cumulative pruning statistics for a session.

    Args:
        session_id: The session identifier

    Returns:
        Statistics dict with totals and breakdowns
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get totals
    cursor.execute(
        """
        SELECT 
            COUNT(*) as event_count,
            COALESCE(SUM(tokens_saved), 0) as total_tokens,
            COUNT(DISTINCT strategy) as strategy_count
        FROM curator_events
        WHERE session_id = ?
        """,
        (session_id,)
    )

    row = cursor.fetchone()
    event_count = row[0] if row else 0
    total_tokens = row[1] if row else 0

    # Get by strategy
    cursor.execute(
        """
        SELECT strategy, COUNT(*) as count, SUM(tokens_saved) as tokens
        FROM curator_events
        WHERE session_id = ?
        GROUP BY strategy
        """,
        (session_id,)
    )

    by_strategy = {}
    for row in cursor.fetchall():
        by_strategy[row[0]] = {
            "count": row[1],
            "tokens_saved": row[2],
        }

    # Count extract vs prune events
    prune_events = sum(
        v["count"] for k, v in by_strategy.items()
        if k != "extract"
    )
    extract_events = by_strategy.get("extract", {}).get("count", 0)

    return {
        "session_id": session_id,
        "totalTokensSaved": total_tokens,
        "pruneEvents": prune_events,
        "extractEvents": extract_events,
        "byStrategy": by_strategy,
    }
