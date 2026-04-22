"""Hook observability API routes.

Serves the admin ``/hooks`` page: paginated hook event list + rolling
metrics over the trailing ``window_hours``. Both endpoints sit behind
``require_admin_auth`` to match every other admin route.

Query shapes
------------
``GET /api/hooks/events`` supports ``limit``, ``offset``, ``event_name``,
``hook_name``, ``since_ms``, ``sort``, ``order``. Sort columns are
whitelisted against the ``HookEvent`` ORM columns; unknown sort falls
back to ``timestamp``.

``GET /api/hooks/metrics`` groups the rows from the trailing
``window_hours`` by (hook_name, event_name) and returns count,
avg/p50/p95 duration_ms, and error_rate per group, plus a top-level
summary. The window is time-based (hours) to match
``/api/worker-llm/metrics`` so the admin UI presents a consistent
"1h / 6h / 24h" control across both observability pages. The background
retention + notifier loops still express their caps as row counts
because those are operator tuning knobs, not dashboard windows.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.routes.list_helpers import (
    build_list_response,
    percentile,
    validate_sort_order,
)
from spellbook.db import spellbook_db
from spellbook.db.helpers import apply_pagination
from spellbook.db.spellbook_models import HookEvent

router = APIRouter(prefix="/hooks", tags=["hooks"])

# Whitelist the HookEvent columns. Unknown sort values silently fall back
# to ``timestamp``.
_SORT_WHITELIST = {
    "id",
    "timestamp",
    "hook_name",
    "event_name",
    "tool_name",
    "duration_ms",
    "exit_code",
    "error",
}


@router.get("/events")
async def hook_events(
    event_name: Optional[str] = Query(None, description="Filter by event_name"),
    hook_name: Optional[str] = Query(None, description="Filter by hook_name"),
    since_ms: Optional[int] = Query(
        None, description="Lower bound epoch ms on timestamp",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("timestamp", description="Sort column (whitelist)"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Paginated hook event list with event_name/hook_name/since_ms filters.

    ``since_ms`` is an epoch milliseconds value. It is converted to an ISO
    string internally before comparing against the ``timestamp`` column
    (which stores ISO-8601 UTC).
    """
    if since_ms is not None and since_ms < 0:
        raise HTTPException(
            status_code=400,
            detail=f"invalid `since_ms` (must be >= 0): {since_ms}",
        )

    query = select(HookEvent)
    if event_name is not None:
        query = query.where(HookEvent.event_name == event_name)
    if hook_name is not None:
        query = query.where(HookEvent.hook_name == hook_name)
    if since_ms is not None:
        since_iso = datetime.fromtimestamp(
            since_ms / 1000.0, tz=timezone.utc,
        ).isoformat()
        query = query.where(HookEvent.timestamp >= since_iso)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    sort_col = sort if sort in _SORT_WHITELIST else "timestamp"
    direction = validate_sort_order(order)
    col = getattr(HookEvent, sort_col)
    query = query.order_by(col.desc() if direction == "desc" else col.asc())

    # Convert limit/offset to page/per_page for apply_pagination reuse.
    per_page = limit
    page = (offset // per_page) + 1 if per_page else 1
    query = apply_pagination(query, page=page, per_page=per_page)

    result = await db.execute(query)
    items = [r.to_dict() for r in result.scalars().all()]
    return build_list_response(items, total=total, page=page, per_page=per_page)


@router.get("/metrics")
async def hook_metrics(
    window_hours: int = Query(24, ge=1, le=720),
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Aggregate metrics over the trailing ``window_hours``.

    Takes hours (not a row count) and filters by ``timestamp >= cutoff``
    so the window control aligns with ``/api/worker-llm/metrics``. A
    row-count window would give the two admin pages different mental
    models for the same "1h / 6h / 24h" chip row.

    Returns an envelope:

        {
          "total": int,
          "window_hours": int,
          "groups": [
            {
              "hook_name": str,
              "event_name": str,
              "count": int,
              "avg_duration_ms": float | None,
              "p50_duration_ms": int | None,
              "p95_duration_ms": int | None,
              "error_rate": float,
            },
            ...
          ],
          "summary": {
            "avg_duration_ms": float | None,
            "p95_duration_ms": int | None,
            "error_rate": float,
          }
        }

    A row counts as an error when ``exit_code != 0`` OR ``error`` is set.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=window_hours)
    ).isoformat()
    query = select(HookEvent).where(HookEvent.timestamp >= cutoff)
    result = await db.execute(query)
    rows = list(result.scalars().all())

    total = len(rows)
    if total == 0:
        return {
            "total": 0,
            "window_hours": window_hours,
            "groups": [],
            "summary": {
                "avg_duration_ms": None,
                "p95_duration_ms": None,
                "error_rate": 0.0,
            },
        }

    groups: dict[tuple[str, str], list[HookEvent]] = defaultdict(list)
    for r in rows:
        groups[(r.hook_name, r.event_name)].append(r)

    group_out = []
    for (hname, ename), members in sorted(groups.items()):
        durations = sorted(int(m.duration_ms) for m in members)
        errors = sum(
            1 for m in members if m.exit_code != 0 or (m.error or "")
        )
        count = len(members)
        group_out.append({
            "hook_name": hname,
            "event_name": ename,
            "count": count,
            "avg_duration_ms": (
                sum(durations) / count if count else None
            ),
            "p50_duration_ms": percentile(durations, 50),
            "p95_duration_ms": percentile(durations, 95),
            "error_rate": errors / count if count else 0.0,
        })

    all_durations = sorted(int(r.duration_ms) for r in rows)
    all_errors = sum(
        1 for r in rows if r.exit_code != 0 or (r.error or "")
    )

    return {
        "total": total,
        "window_hours": window_hours,
        "groups": group_out,
        "summary": {
            "avg_duration_ms": sum(all_durations) / total,
            "p95_duration_ms": percentile(all_durations, 95),
            "error_rate": all_errors / total,
        },
    }
