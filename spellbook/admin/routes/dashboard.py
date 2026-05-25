"""Dashboard API route: aggregated health, counts, and recent activity."""

import asyncio
import time
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.events import event_bus
from spellbook.admin.routes.schemas import DashboardResponse
from spellbook.db import (
    get_fractal_session,
    get_spellbook_session,
)
from spellbook.db.fractal_models import FractalGraph
from spellbook.db.spellbook_models import Experiment

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


async def _query_spellbook_counts() -> int:
    """Query spellbook.db for dashboard counts.

    Returns the count of running/paused experiments.
    """
    async with get_spellbook_session() as session:
        # Count running/paused experiments
        result = await session.execute(
            select(func.count()).select_from(Experiment).where(
                Experiment.status.in_(["running", "paused"])
            )
        )
        experiments_count = result.scalar_one()

    return experiments_count


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

    # Parallel database queries across spellbook and fractal DBs
    # plus filesystem scan for session count (matches Sessions page data source)
    (
        session_count,
        spellbook_result,
        graphs_result,
    ) = await asyncio.gather(
        asyncio.to_thread(_count_session_files),
        _query_spellbook_counts(),
        _query_fractal_counts(),
        return_exceptions=True,
    )

    # Unpack spellbook results (or defaults on error)
    if isinstance(spellbook_result, Exception):
        experiments_count = 0
    else:
        experiments_count = spellbook_result

    # Recent-activity feed: the only activity source was memory creation,
    # which has been removed. Left as an empty list so the dashboard
    # contract (recent_activity) is preserved.
    activity: list[dict] = []

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
            "open_experiments": experiments_count,
            "fractal_graphs": safe_int(graphs_result),
        },
        "recent_activity": activity,
    }


@router.get("", response_model=DashboardResponse)
async def get_dashboard(_session: str = Depends(require_admin_auth)):
    """Return aggregated dashboard data."""
    return await get_dashboard_data()
