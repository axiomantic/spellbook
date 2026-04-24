"""Shared helper functions for admin list endpoints.

Builds on the lower-level primitives from spellbook.db.helpers and adds
the admin-specific response envelope {items, total, page, per_page, pages}.
"""

import math
import statistics
from typing import Optional


def validate_sort_order(order: str) -> str:
    """Normalize sort order to 'asc' or 'desc'.

    Invalid values default to 'desc' (most-recent-first is the common case).
    """
    return "asc" if order.lower() == "asc" else "desc"


def compute_pagination(total: int, page: int, per_page: int) -> dict:
    """Compute pagination metadata.

    Clamps page to valid range (1..pages).
    """
    pages = max(1, math.ceil(total / per_page)) if per_page > 0 else 1
    clamped_page = min(page, pages)
    return {
        "total": total,
        "page": clamped_page,
        "per_page": per_page,
        "pages": pages,
    }


def build_list_response(
    items: list[dict],
    total: int,
    page: int,
    per_page: int,
) -> dict:
    """Build the standard list response envelope.

    All admin list endpoints should return this shape:
    {items: [...], total: N, page: N, per_page: N, pages: N}
    """
    meta = compute_pagination(total, page, per_page)
    return {"items": items, **meta}


def percentile(sorted_xs: list[int], pct: int) -> Optional[int]:
    """Nearest-rank percentile over a pre-sorted ascending list.

    ``statistics.quantiles(n=100, method='inclusive')`` returns 99
    cutpoints; ``pct=95`` maps to index 94. The boundary cases
    (``pct <= 0`` and ``pct >= 100``) bypass ``quantiles`` entirely and
    return the min / max of the sample — clamping into the cutpoint array
    would yield the 1st / 99th percentile instead of the true extrema.

    For a single sample, ``statistics.quantiles`` raises; fall back to
    the lone value. Returns ``None`` for an empty list so callers can
    distinguish "no data" from "genuinely 0 ms".
    """
    if not sorted_xs:
        return None
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    if pct <= 0:
        return int(sorted_xs[0])
    if pct >= 100:
        return int(sorted_xs[-1])
    quantiles = statistics.quantiles(sorted_xs, n=100, method="inclusive")
    idx = int(pct) - 1
    return int(quantiles[idx])
