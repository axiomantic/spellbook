"""Worker-LLM observability API routes.

Serves the admin /worker-llm page: paginated call list + rolling metrics
over the trailing ``window_hours``. Both endpoints sit behind
``require_admin_auth`` to match every other admin route.

Query shapes
------------
``GET /api/worker-llm/calls`` supports ``task``, ``status``, ``since``,
``page``, ``per_page``, ``sort``, ``order``. ``since`` is validated as
ISO-8601 BEFORE the query runs (SQLite would otherwise string-compare
arbitrary garbage and silently return an empty result set). Sort columns
are whitelisted against the ``WorkerLLMCall`` ORM columns.

``GET /api/worker-llm/metrics`` computes success_rate and percentile
latencies over the trailing ``window_hours``. Percentiles are computed
in Python (``statistics.quantiles(n=100, method='inclusive')``) over the
raw rows -- portability over microseconds, per design §5. When there are
zero successful rows in the window, ``p95_latency_ms`` / ``p99_latency_ms``
are ``None``; the frontend renders null as an em-dash.
"""

from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.routes.list_helpers import (
    build_list_response,
    validate_sort_order,
)
from spellbook.db import spellbook_db
from spellbook.db.helpers import apply_pagination
from spellbook.db.spellbook_models import WorkerLLMCall

router = APIRouter(prefix="/worker-llm", tags=["worker-llm"])

# Whitelist the 10 WorkerLLMCall columns. Unknown sort values silently
# fall back to ``timestamp`` rather than 400 -- mirrors the
# ``validate_sort_order`` posture: accept anything, degrade to a safe
# default. 400 is reserved for input the caller could not have reasonably
# submitted (malformed ISO timestamp).
_SORT_WHITELIST = {
    "id",
    "timestamp",
    "task",
    "model",
    "status",
    "latency_ms",
    "prompt_len",
    "response_len",
    "error",
    "override_loaded",
}


@router.get("/calls")
async def worker_llm_calls(
    task: Optional[str] = Query(None, description="Filter by task name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    since: Optional[str] = Query(
        None, description="ISO-8601 UTC lower bound on timestamp"
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("timestamp", description="Sort column (whitelist)"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Paginated worker-LLM call list with task/status/since filters.

    The ``since`` value is validated as ISO-8601 before being applied to
    the query. SQLite stores ``timestamp`` as ``Text``, so an unvalidated
    string comparison would silently return an empty result set on
    malformed input; 400 is the safer signal.
    """
    if since is not None:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"invalid `since` (expected ISO-8601): {since!r}",
            )

    query = select(WorkerLLMCall)
    if task is not None:
        query = query.where(WorkerLLMCall.task == task)
    if status is not None:
        query = query.where(WorkerLLMCall.status == status)
    if since is not None:
        query = query.where(WorkerLLMCall.timestamp >= since)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    sort_col = sort if sort in _SORT_WHITELIST else "timestamp"
    direction = validate_sort_order(order)
    col = getattr(WorkerLLMCall, sort_col)
    query = query.order_by(col.desc() if direction == "desc" else col.asc())
    query = apply_pagination(query, page=page, per_page=per_page)

    result = await db.execute(query)
    items = [r.to_dict() for r in result.scalars().all()]
    return build_list_response(items, total=total, page=page, per_page=per_page)


def _percentile(sorted_xs: list[int], pct: int) -> Optional[int]:
    """Nearest-rank percentile over a pre-sorted list.

    ``statistics.quantiles(n=100, method='inclusive')`` returns 99
    cutpoints; ``pct=95`` maps to index 94. For a single sample,
    ``statistics.quantiles`` raises; fall back to the lone value.
    Returns ``None`` for an empty list so the route can distinguish
    "no data" from "genuinely 0 ms".
    """
    if not sorted_xs:
        return None
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    quantiles = statistics.quantiles(sorted_xs, n=100, method="inclusive")
    idx = max(0, min(98, int(pct) - 1))
    return int(quantiles[idx])


@router.get("/metrics")
async def worker_llm_metrics(
    window_hours: int = Query(24, ge=1, le=720),
    _session: str = Depends(require_admin_auth),
    db: AsyncSession = Depends(spellbook_db),
):
    """Aggregate metrics over the trailing ``window_hours``.

    Returns a six-key envelope:
    ``{success_rate, p95_latency_ms, p99_latency_ms, error_breakdown,
    total_calls, window_hours}``.

    When the window is empty (``total_calls == 0``), ``success_rate``,
    ``p95_latency_ms``, and ``p99_latency_ms`` are ``None`` and
    ``error_breakdown`` is ``{}``. When the window has rows but none
    successful, ``success_rate`` is numeric (0.0) while the latency
    percentiles remain ``None`` (no latency sample to compute over).
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=window_hours)
    ).isoformat()
    query = select(WorkerLLMCall).where(WorkerLLMCall.timestamp >= cutoff)
    result = await db.execute(query)
    rows = list(result.scalars().all())

    total = len(rows)
    if total == 0:
        return {
            "success_rate": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "error_breakdown": {},
            "total_calls": 0,
            "window_hours": window_hours,
        }

    successes = sum(1 for r in rows if r.status == "success")
    latencies = sorted(r.latency_ms for r in rows if r.status == "success")
    errors = Counter(
        (r.error or r.status) for r in rows if r.status != "success"
    )

    return {
        "success_rate": successes / total,
        "p95_latency_ms": _percentile(latencies, 95),
        "p99_latency_ms": _percentile(latencies, 99),
        "error_breakdown": dict(errors.most_common(10)),
        "total_calls": total,
        "window_hours": window_hours,
    }
