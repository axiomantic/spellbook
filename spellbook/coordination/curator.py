"""
Context Curator MCP tools for analytics tracking.

Uses SQLAlchemy ORM (CuratorEvent model) with async sessions.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.db.spellbook_models import CuratorEvent


def init_curator_tables() -> None:
    """Initialize curator database tables.

    Legacy function kept for backward compatibility with server startup.
    With ORM, table creation is handled by Alembic migrations or
    Base.metadata.create_all(). This is now a no-op.
    """
    pass


async def curator_track_prune(
    session_id: str,
    tool_ids: list[str],
    tokens_saved: int,
    strategy: str,
    session: Optional[AsyncSession] = None,
) -> dict[str, Any]:
    """
    Track a pruning event for analytics.

    Args:
        session_id: The session identifier
        tool_ids: List of tool IDs that were pruned
        tokens_saved: Estimated tokens saved by this prune
        strategy: The strategy that triggered the prune
        session: Optional async session (injected for testing)

    Returns:
        Status dict with event_id
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    tool_ids_json = json.dumps(tool_ids)

    event = CuratorEvent(
        session_id=session_id,
        tool_ids=tool_ids_json,
        tokens_saved=tokens_saved,
        strategy=strategy,
        timestamp=timestamp,
    )

    if session is not None:
        session.add(event)
        await session.flush()
        return {
            "success": True,
            "event_id": event.id,
            "session_id": session_id,
            "tools_pruned": len(tool_ids),
        }

    from spellbook.db import get_spellbook_session

    async with get_spellbook_session() as s:
        s.add(event)
        await s.flush()
        event_id = event.id

    return {
        "success": True,
        "event_id": event_id,
        "session_id": session_id,
        "tools_pruned": len(tool_ids),
    }


async def curator_get_stats(
    session_id: str,
    session: Optional[AsyncSession] = None,
) -> dict[str, Any]:
    """
    Get cumulative pruning statistics for a session.

    Args:
        session_id: The session identifier
        session: Optional async session (injected for testing)

    Returns:
        Statistics dict with totals and breakdowns
    """

    async def _query(s: AsyncSession) -> dict[str, Any]:
        # Get totals
        totals_stmt = select(
            func.count().label("event_count"),
            func.coalesce(func.sum(CuratorEvent.tokens_saved), 0).label("total_tokens"),
        ).where(CuratorEvent.session_id == session_id)

        result = await s.execute(totals_stmt)
        totals = result.one()
        total_tokens = totals.total_tokens

        # Get by strategy
        strategy_stmt = (
            select(
                CuratorEvent.strategy,
                func.count().label("count"),
                func.sum(CuratorEvent.tokens_saved).label("tokens"),
            )
            .where(CuratorEvent.session_id == session_id)
            .group_by(CuratorEvent.strategy)
        )

        result = await s.execute(strategy_stmt)
        by_strategy = {}
        for row in result.all():
            by_strategy[row.strategy] = {
                "count": row.count,
                "tokens_saved": row.tokens,
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

    if session is not None:
        return await _query(session)

    from spellbook.db import get_spellbook_session

    async with get_spellbook_session() as s:
        return await _query(s)
