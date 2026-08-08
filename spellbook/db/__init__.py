"""SQLAlchemy database layer for spellbook.

Public API:
- get_spellbook_session(): async context manager for database sessions.
- spellbook_db(): FastAPI dependency function for route injection.
- Engine and session factory objects for direct access.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.db.engines import (
    SpellbookSession,
    dispose_sync_engines,
    get_spellbook_sync_session,
    get_sync_session,
    spellbook_engine,
)


@asynccontextmanager
async def get_spellbook_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for spellbook.db sessions."""
    async with SpellbookSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# FastAPI dependency functions
async def spellbook_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a spellbook.db session."""
    async with get_spellbook_session() as session:
        yield session


async def dispose_all_engines() -> None:
    """Dispose all database engines on shutdown."""
    await spellbook_engine.dispose()


__all__ = [
    "get_spellbook_session",
    "get_sync_session",
    "get_spellbook_sync_session",
    "dispose_sync_engines",
    "spellbook_db",
    "dispose_all_engines",
    "spellbook_engine",
    "SpellbookSession",
]
