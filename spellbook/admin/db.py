"""Async database query helpers for admin routes.

All admin routes reuse existing connection functions. These helpers
wrap synchronous sqlite3 queries in asyncio.to_thread() to avoid
blocking the event loop.
"""

import asyncio
import sqlite3
from pathlib import Path
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


async def execute_spellbook_db(sql: str, params: tuple = ()) -> int:
    """Execute a write query against spellbook.db, return rows affected."""
    from spellbook.core.db import get_connection

    def _run():
        conn = get_connection()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount

    return await asyncio.to_thread(_run)


async def query_fractal_db(
    sql: str, params: tuple = ()
) -> list[dict[str, Any]]:
    """Run a query against fractal.db in a thread pool."""
    from spellbook.fractal.schema import get_fractal_connection

    def _run():
        conn = get_fractal_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql, params)
        return _rows_to_dicts(cursor.fetchall())

    return await asyncio.to_thread(_run)


async def query_forged_db(
    sql: str, params: tuple = ()
) -> list[dict[str, Any]]:
    """Run a query against forged.db in a thread pool."""
    from spellbook.forged.schema import get_forged_connection

    def _run():
        conn = get_forged_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql, params)
        return _rows_to_dicts(cursor.fetchall())

    return await asyncio.to_thread(_run)


async def query_coordination_db(
    sql: str, params: tuple = ()
) -> list[dict[str, Any]]:
    """Run a query against coordination.db in a thread pool."""

    def _run():
        db_path = Path.home() / ".local" / "spellbook" / "coordination.db"
        if not db_path.exists():
            return []
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql, params)
            return _rows_to_dicts(cursor.fetchall())
        finally:
            conn.close()

    return await asyncio.to_thread(_run)
