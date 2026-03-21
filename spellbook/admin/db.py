"""Async database query helpers for admin routes.

All admin routes reuse existing connection functions. These helpers
wrap synchronous sqlite3 queries in asyncio.to_thread() to avoid
blocking the event loop.
"""

import asyncio
import sqlite3
from typing import Any


def _rows_to_dicts(rows: list) -> list[dict[str, Any]]:
    """Convert sqlite3.Row objects to plain dicts."""
    return [dict(row) for row in rows]


async def query_spellbook_db(
    sql: str, params: tuple = ()
) -> list[dict[str, Any]]:
    """Run a query against spellbook.db in a thread pool."""
    from spellbook.core.db import get_connection

    def _run():
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql, params)
        return _rows_to_dicts(cursor.fetchall())

    return await asyncio.to_thread(_run)


