"""SQLAlchemy database layer for spellbook.

Public API:
- get_spellbook_session(), get_fractal_session(), get_forged_session(),
  get_coordination_session(): async context managers for database sessions.
- spellbook_db(), fractal_db(), forged_db(), coordination_db():
  FastAPI dependency functions for route injection.
- Engine and session factory objects for direct access.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.db.engines import (
    CoordinationSession,
    ForgedSession,
    FractalSession,
    SpellbookSession,
    coordination_engine,
    dispose_sync_engines,
    forged_engine,
    fractal_engine,
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


@asynccontextmanager
async def get_fractal_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for fractal.db sessions."""
    async with FractalSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_forged_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for forged.db sessions."""
    async with ForgedSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_coordination_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for coordination.db sessions."""
    async with CoordinationSession() as session:
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


async def fractal_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a fractal.db session."""
    async with get_fractal_session() as session:
        yield session


async def forged_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a forged.db session."""
    async with get_forged_session() as session:
        yield session


async def coordination_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a coordination.db session."""
    async with get_coordination_session() as session:
        yield session


async def dispose_all_engines() -> None:
    """Dispose all database engines on shutdown."""
    await spellbook_engine.dispose()
    await fractal_engine.dispose()
    await forged_engine.dispose()
    await coordination_engine.dispose()


__all__ = [
    "get_spellbook_session",
    "get_fractal_session",
    "get_forged_session",
    "get_coordination_session",
    "get_sync_session",
    "get_spellbook_sync_session",
    "dispose_sync_engines",
    "spellbook_db",
    "fractal_db",
    "forged_db",
    "coordination_db",
    "dispose_all_engines",
    "spellbook_engine",
    "fractal_engine",
    "forged_engine",
    "coordination_engine",
    "SpellbookSession",
    "FractalSession",
    "ForgedSession",
    "CoordinationSession",
]
