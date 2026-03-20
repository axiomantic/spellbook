"""Shared query helpers for pagination and sorting."""

import math

from sqlalchemy import asc, desc
from sqlalchemy.ext.asyncio import AsyncSession


def apply_pagination(query, page: int, per_page: int):
    """Apply LIMIT/OFFSET pagination to a SQLAlchemy select() query."""
    offset = (page - 1) * per_page
    return query.limit(per_page).offset(offset)


def apply_sorting(
    query,
    model,
    sort_column: str,
    sort_order: str,
    allowed_columns: set[str],
    default_column: str = "created_at",
):
    """Apply validated sorting to a query.

    If sort_column is not in allowed_columns, silently falls back to
    default_column.
    """
    if sort_column not in allowed_columns:
        sort_column = default_column
    col = getattr(model, sort_column)
    order_fn = asc if sort_order.lower() == "asc" else desc
    return query.order_by(order_fn(col))


async def paginated_query(
    session: AsyncSession,
    query,
    count_query,
    page: int,
    per_page: int,
) -> tuple[list, int, int]:
    """Execute a paginated query, returning (items, total, pages)."""
    result = await session.execute(count_query)
    total = result.scalar_one()
    pages = max(1, math.ceil(total / per_page))

    paginated = apply_pagination(query, page, per_page)
    result = await session.execute(paginated)
    items = list(result.scalars().all())

    return items, total, pages
