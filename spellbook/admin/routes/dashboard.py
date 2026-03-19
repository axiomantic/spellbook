"""Dashboard API route: aggregated health, counts, and recent activity."""

import asyncio
import time
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import APIRouter, Depends

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.db import (
    query_spellbook_db,
    query_fractal_db,
    query_coordination_db,
)
from spellbook.admin.events import event_bus
from spellbook.admin.routes.schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_start_time = time.time()


def _get_db_size() -> int:
    """Get the spellbook database file size in bytes."""
    from spellbook.core.db import get_db_path

    db_path = get_db_path()
    return db_path.stat().st_size if db_path.exists() else 0


async def get_dashboard_data() -> dict:
    """Gather dashboard data from all databases in parallel."""
    version = pkg_version("spellbook")

    # Parallel database queries across spellbook, coordination, and fractal DBs
    (
        sessions_result,
        memories_result,
        security_result,
        experiments_result,
        recent_security,
        recent_memories,
        swarms_result,
        graphs_result,
    ) = await asyncio.gather(
        query_spellbook_db(
            "SELECT COUNT(*) as cnt FROM souls "
            "WHERE bound_at > datetime('now', '-24 hours')"
        ),
        query_spellbook_db(
            "SELECT COUNT(*) as cnt FROM memories WHERE status = 'active'"
        ),
        query_spellbook_db(
            "SELECT COUNT(*) as cnt FROM security_events "
            "WHERE created_at > datetime('now', '-24 hours')"
        ),
        query_spellbook_db(
            "SELECT COUNT(*) as cnt FROM experiments "
            "WHERE status IN ('running', 'paused')"
        ),
        query_spellbook_db(
            "SELECT event_type as type, created_at as timestamp, "
            "COALESCE(detail, event_type) as summary FROM security_events "
            "ORDER BY created_at DESC LIMIT 20"
        ),
        query_spellbook_db(
            "SELECT 'memory_created' as type, created_at as timestamp, "
            "SUBSTR(content, 1, 80) as summary FROM memories "
            "ORDER BY created_at DESC LIMIT 20"
        ),
        query_coordination_db(
            "SELECT COUNT(*) as cnt FROM swarms WHERE status = 'running'"
        ),
        query_fractal_db("SELECT COUNT(*) as cnt FROM graphs"),
        return_exceptions=True,
    )

    def safe_count(result: object, default: int = 0) -> int:
        if isinstance(result, Exception) or not result:
            return default
        return result[0].get("cnt", default)

    def safe_list(result: object) -> list:
        if isinstance(result, Exception) or not result:
            return []
        return result

    # Merge and sort recent activity by timestamp descending
    activity = sorted(
        safe_list(recent_security) + safe_list(recent_memories),
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )[:20]

    db_size = _get_db_size()

    return {
        "health": {
            "status": "ok",
            "version": version,
            "uptime_seconds": round(time.time() - _start_time, 1),
            "db_size_bytes": db_size,
            "event_bus_subscribers": event_bus.subscriber_count,
            "event_bus_dropped_events": event_bus.total_dropped_events,
        },
        "counts": {
            "active_sessions": safe_count(sessions_result),
            "total_memories": safe_count(memories_result),
            "security_events_24h": safe_count(security_result),
            "running_swarms": safe_count(swarms_result),
            "open_experiments": safe_count(experiments_result),
            "fractal_graphs": safe_count(graphs_result),
        },
        "recent_activity": activity,
    }


@router.get("", response_model=DashboardResponse)
async def get_dashboard(_session: str = Depends(require_admin_auth)):
    """Return aggregated dashboard data."""
    return await get_dashboard_data()
