"""Dashboard API route: aggregated health, counts, and recent activity."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.events import event_bus
from spellbook.admin.routes.schemas import DashboardResponse
from spellbook.db import (
    get_coordination_session,
    get_fractal_session,
    get_spellbook_session,
)
from spellbook.db.coordination_models import Swarm
from spellbook.db.fractal_models import FractalGraph
from spellbook.db.spellbook_models import Experiment, Memory, SecurityEvent

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_start_time = time.time()


def _get_db_size() -> int:
    """Get the spellbook database file size in bytes."""
    from spellbook.core.db import get_db_path

    db_path = get_db_path()
    return db_path.stat().st_size if db_path.exists() else 0


def _count_session_files() -> int:
    """Count Claude Code session JSONL files in ~/.claude/projects/.

    This matches the same data source used by the Sessions page, which scans
    these files for session metadata. We only need the count here, so we
    avoid reading file contents.
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return 0
    count = 0
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                if jsonl_file.stat().st_size > 0:
                    count += 1
            except (OSError, PermissionError):
                continue
    return count


async def _query_spellbook_counts() -> tuple[int, int, int, list, list]:
    """Query spellbook.db for dashboard counts and recent activity.

    Returns (memories_count, security_count, experiments_count,
             recent_security_events, recent_memories).
    """
    async with get_spellbook_session() as session:
        # Count active memories
        result = await session.execute(
            select(func.count()).select_from(Memory).where(
                Memory.status == "active"
            )
        )
        memories_count = result.scalar_one()

        # Count security events in last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        result = await session.execute(
            select(func.count()).select_from(SecurityEvent).where(
                SecurityEvent.created_at > cutoff_str
            )
        )
        security_count = result.scalar_one()

        # Count running/paused experiments
        result = await session.execute(
            select(func.count()).select_from(Experiment).where(
                Experiment.status.in_(["running", "paused"])
            )
        )
        experiments_count = result.scalar_one()

        # Recent security events
        result = await session.execute(
            select(SecurityEvent)
            .order_by(SecurityEvent.created_at.desc())
            .limit(20)
        )
        recent_security = list(result.scalars().all())

        # Recent memories
        result = await session.execute(
            select(Memory)
            .order_by(Memory.created_at.desc())
            .limit(20)
        )
        recent_memories = list(result.scalars().all())

    return (
        memories_count,
        security_count,
        experiments_count,
        recent_security,
        recent_memories,
    )


async def _query_coordination_counts() -> int:
    """Query coordination.db for running swarm count."""
    async with get_coordination_session() as session:
        result = await session.execute(
            select(func.count()).select_from(Swarm).where(
                Swarm.status == "running"
            )
        )
        return result.scalar_one()


async def _query_fractal_counts() -> int:
    """Query fractal.db for total graph count."""
    async with get_fractal_session() as session:
        result = await session.execute(
            select(func.count()).select_from(FractalGraph)
        )
        return result.scalar_one()


async def get_dashboard_data() -> dict:
    """Gather dashboard data from all databases in parallel."""
    version = pkg_version("spellbook")

    # Parallel database queries across spellbook, coordination, and fractal DBs
    # plus filesystem scan for session count (matches Sessions page data source)
    (
        session_count,
        spellbook_result,
        swarms_result,
        graphs_result,
    ) = await asyncio.gather(
        asyncio.to_thread(_count_session_files),
        _query_spellbook_counts(),
        _query_coordination_counts(),
        _query_fractal_counts(),
        return_exceptions=True,
    )

    # Unpack spellbook results (or defaults on error)
    if isinstance(spellbook_result, Exception):
        memories_count = 0
        security_count = 0
        experiments_count = 0
        recent_security_events: list = []
        recent_memories: list = []
    else:
        (
            memories_count,
            security_count,
            experiments_count,
            recent_security_events,
            recent_memories,
        ) = spellbook_result

    # Transform ORM objects to activity dicts
    security_activity = [
        {
            "type": ev.event_type,
            "timestamp": ev.created_at,
            "summary": ev.detail if ev.detail else ev.event_type,
        }
        for ev in recent_security_events
    ]
    memory_activity = [
        {
            "type": "memory_created",
            "timestamp": mem.created_at,
            "summary": mem.content[:80],
        }
        for mem in recent_memories
    ]

    # Merge and sort recent activity by timestamp descending
    activity = sorted(
        security_activity + memory_activity,
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )[:20]

    db_size = _get_db_size()

    def safe_int(value: object, default: int = 0) -> int:
        """Extract an int result, defaulting on exception."""
        if isinstance(value, Exception):
            return default
        return value

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
            "active_sessions": safe_int(session_count),
            "total_memories": memories_count,
            "security_events_24h": security_count,
            "running_swarms": safe_int(swarms_result),
            "open_experiments": experiments_count,
            "fractal_graphs": safe_int(graphs_result),
        },
        "recent_activity": activity,
    }


@router.get("", response_model=DashboardResponse)
async def get_dashboard(_session: str = Depends(require_admin_auth)):
    """Return aggregated dashboard data."""
    return await get_dashboard_data()
