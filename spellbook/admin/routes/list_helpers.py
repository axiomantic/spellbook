"""Shared helper functions for admin list endpoints.

Builds on the lower-level primitives from spellbook.db.helpers and adds
the admin-specific response envelope {items, total, page, per_page, pages}.
"""

import math


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
