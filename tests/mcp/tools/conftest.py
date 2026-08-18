"""Fixtures for MCP tool tests that need a real spellbook database.

The tools under test accept an injected ``AsyncSession`` precisely so their
behaviour can be exercised against a real schema rather than a mock. An
in-memory SQLite database on a ``StaticPool`` keeps the created tables visible
across the connections a single test makes.
"""

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from spellbook.db.base import SpellbookBase


def _setup_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest_asyncio.fixture
async def spellbook_session():
    """Yield an async session bound to an in-memory spellbook.db."""
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
