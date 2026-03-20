"""Async SQLAlchemy engines and session factories for all 4 databases.

Each database gets an independent async engine with NullPool (avoids stale
pooled connections, appropriate for SQLite) and a 5-second busy timeout
to mitigate "database is locked" contention under concurrent writes.
WAL mode and recommended PRAGMAs are applied on each new connection.
"""

import os
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

DB_DIR = Path.home() / ".local" / "spellbook"
DB_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(str(DB_DIR), 0o700)


def _sqlite_url(name: str) -> str:
    """Build an aiosqlite connection URL for the given database file."""
    return f"sqlite+aiosqlite:///{DB_DIR / name}"


def _setup_pragmas(dbapi_conn, connection_record):
    """Enable WAL mode and recommended PRAGMAs on each new connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# One engine per database
spellbook_engine = create_async_engine(
    _sqlite_url("spellbook.db"),
    connect_args={"timeout": 5},
    poolclass=NullPool,
)

fractal_engine = create_async_engine(
    _sqlite_url("fractal.db"),
    connect_args={"timeout": 5},
    poolclass=NullPool,
)

forged_engine = create_async_engine(
    _sqlite_url("forged.db"),
    connect_args={"timeout": 5},
    poolclass=NullPool,
)

coordination_engine = create_async_engine(
    _sqlite_url("coordination.db"),
    connect_args={"timeout": 5},
    poolclass=NullPool,
)

# Register PRAGMAs on all engines
for _eng in (spellbook_engine, fractal_engine, forged_engine, coordination_engine):
    event.listen(_eng.sync_engine, "connect", _setup_pragmas)

# Session factories (expire_on_commit=False for detached use in route handlers)
SpellbookSession = async_sessionmaker(spellbook_engine, expire_on_commit=False)
FractalSession = async_sessionmaker(fractal_engine, expire_on_commit=False)
ForgedSession = async_sessionmaker(forged_engine, expire_on_commit=False)
CoordinationSession = async_sessionmaker(coordination_engine, expire_on_commit=False)
