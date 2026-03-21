"""SQLAlchemy engines and session factories for all 4 databases.

Each database gets an independent async engine with NullPool (avoids stale
pooled connections, appropriate for SQLite) and a 5-second busy timeout
to mitigate "database is locked" contention under concurrent writes.
WAL mode and recommended PRAGMAs are applied on each new connection.

Sync engine support is provided for modules that cannot use async
(security tools, CLI hooks, config). Use ``get_sync_session()`` for
arbitrary database paths or ``get_spellbook_sync_session()`` for the
default spellbook.db location.
"""

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
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

# ---------------------------------------------------------------------------
# Sync engine support for synchronous callers (security tools, CLI, config)
# ---------------------------------------------------------------------------

_sync_engines: dict[str, object] = {}
_sync_engines_lock = threading.Lock()


def _get_or_create_sync_engine(db_path: str):
    """Get or create a sync SQLAlchemy engine for the given database path.

    Engines are cached by path. Each engine uses NullPool and applies
    WAL mode pragmas on connect, matching the async engine configuration.

    Args:
        db_path: Absolute path to the SQLite database file.

    Returns:
        A sync SQLAlchemy Engine instance.
    """
    with _sync_engines_lock:
        if db_path in _sync_engines:
            return _sync_engines[db_path]

        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"timeout": 5},
            poolclass=NullPool,
        )
        event.listen(engine, "connect", _setup_pragmas)
        _sync_engines[db_path] = engine
        return engine


@contextmanager
def get_sync_session(db_path: str) -> Generator[Session, None, None]:
    """Context manager yielding a sync SQLAlchemy session for the given db path.

    Commits on clean exit, rolls back on exception. The session uses
    expire_on_commit=False so returned ORM objects remain usable after
    the context exits.

    Args:
        db_path: Absolute path to the SQLite database file.

    Yields:
        A bound SQLAlchemy Session.
    """
    engine = _get_or_create_sync_engine(db_path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_spellbook_sync_session() -> Generator[Session, None, None]:
    """Context manager yielding a sync session for the default spellbook.db.

    Convenience wrapper around ``get_sync_session()`` using the standard
    database path (~/.local/spellbook/spellbook.db).
    """
    db_path = str(DB_DIR / "spellbook.db")
    with get_sync_session(db_path) as session:
        yield session


def dispose_sync_engines() -> None:
    """Dispose all cached sync engines. Used for test cleanup."""
    with _sync_engines_lock:
        for engine in _sync_engines.values():
            engine.dispose()
        _sync_engines.clear()
