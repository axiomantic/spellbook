"""Shared fixtures for ORM migration tests.

Creates async databases for each test with the ORM schema.
Uses StaticPool with shared in-memory connections to keep tables visible.
"""

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from spellbook.db.base import CoordinationBase, ForgedBase, SpellbookBase


def _setup_pragmas(dbapi_conn, connection_record):
    """Enable WAL-compatible PRAGMAs on in-memory connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest_asyncio.fixture
async def forged_session():
    """Yield an async session connected to an in-memory forged.db."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine.sync_engine, "connect", _setup_pragmas)

    async with engine.begin() as conn:
        await conn.run_sync(ForgedBase.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def coordination_session():
    """Yield an async session connected to an in-memory coordination.db."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine.sync_engine, "connect", _setup_pragmas)

    async with engine.begin() as conn:
        await conn.run_sync(CoordinationBase.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def spellbook_session():
    """Yield an async session connected to an in-memory spellbook.db."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine.sync_engine, "connect", _setup_pragmas)

    async with engine.begin() as conn:
        await conn.run_sync(SpellbookBase.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()
