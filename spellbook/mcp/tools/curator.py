"""MCP tools for context-curator analytics.

Backs the OpenCode ``context-curator`` extension, which posts prune events here
and reads cumulative statistics back. The extension degrades gracefully when the
server is unreachable, so these tools are analytics-only: no caller depends on
them for pruning itself.
"""

__all__ = [
    "mcp_curator_track_prune",
    "mcp_curator_get_stats",
]

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.db import get_spellbook_session
from spellbook.db.spellbook_models import CuratorEvent
from spellbook.mcp.server import mcp


async def _record_prune(
    session: AsyncSession,
    session_id: str,
    tool_ids: list[str],
    tokens_saved: int,
    strategy: str,
) -> dict[str, Any]:
    event = CuratorEvent(
        session_id=session_id,
        tool_ids=json.dumps(tool_ids),
        tokens_saved=tokens_saved,
        strategy=strategy,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    session.add(event)
    await session.flush()
    return {
        "success": True,
        "event_id": event.id,
        "session_id": session_id,
        "tools_pruned": len(tool_ids),
    }


async def _read_stats(session: AsyncSession, session_id: str) -> dict[str, Any]:
    totals_stmt = select(
        func.coalesce(func.sum(CuratorEvent.tokens_saved), 0).label("total_tokens"),
    ).where(CuratorEvent.session_id == session_id)
    total_tokens = (await session.execute(totals_stmt)).one().total_tokens

    strategy_stmt = (
        select(
            CuratorEvent.strategy,
            func.count().label("count"),
            func.coalesce(func.sum(CuratorEvent.tokens_saved), 0).label("tokens"),
        )
        .where(CuratorEvent.session_id == session_id)
        .group_by(CuratorEvent.strategy)
    )
    by_strategy = {
        row.strategy: {"count": row.count, "tokens_saved": row.tokens}
        for row in (await session.execute(strategy_stmt)).all()
    }

    # The extension writes extracts under the "extract" strategy; everything
    # else is a prune. Splitting here keeps the extension's two counters honest.
    extract_events = by_strategy.get("extract", {}).get("count", 0)
    prune_events = sum(v["count"] for k, v in by_strategy.items() if k != "extract")

    return {
        "sessionId": session_id,
        "totalTokensSaved": total_tokens,
        "pruneEvents": prune_events,
        "extractEvents": extract_events,
        "byStrategy": by_strategy,
    }


@mcp.tool()
async def mcp_curator_track_prune(
    session_id: str,
    tool_ids: list,
    tokens_saved: int,
    strategy: str,
) -> dict:
    """Record a context-pruning event for analytics.

    Args:
        session_id: The session identifier.
        tool_ids: Tool call IDs that were pruned.
        tokens_saved: Estimated tokens reclaimed by this prune.
        strategy: The strategy that triggered the prune.

    Returns:
        Status dict carrying the new event id.
    """
    async with get_spellbook_session() as owned:
        return await _record_prune(owned, session_id, list(tool_ids), tokens_saved, strategy)


@mcp.tool()
async def mcp_curator_get_stats(
    session_id: str,
) -> dict:
    """Return cumulative pruning statistics for one session.

    Args:
        session_id: The session identifier.

    Returns:
        Totals and a per-strategy breakdown, keyed as the extension expects.
    """
    async with get_spellbook_session() as owned:
        return await _read_stats(owned, session_id)
