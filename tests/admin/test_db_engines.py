"""Tests for SQLAlchemy engine setup and session factories."""

import pytest
from pathlib import Path

pytestmark = pytest.mark.allow("socket", "database")


class TestEngineCreation:
    def test_engines_importable(self):
        from spellbook.db.engines import (
            spellbook_engine,
            fractal_engine,
            forged_engine,
            coordination_engine,
        )

        expected_dir = Path.home() / ".local" / "spellbook"

        assert type(spellbook_engine).__name__ == "AsyncEngine"
        assert str(spellbook_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'spellbook.db'}"

        assert type(fractal_engine).__name__ == "AsyncEngine"
        assert str(fractal_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'fractal.db'}"

        assert type(forged_engine).__name__ == "AsyncEngine"
        assert str(forged_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'forged.db'}"

        assert type(coordination_engine).__name__ == "AsyncEngine"
        assert str(coordination_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'coordination.db'}"

    def test_session_factories_importable(self):
        from spellbook.db.engines import (
            SpellbookSession,
            FractalSession,
            ForgedSession,
            CoordinationSession,
        )
        assert type(SpellbookSession).__name__ == "async_sessionmaker"
        assert type(FractalSession).__name__ == "async_sessionmaker"
        assert type(ForgedSession).__name__ == "async_sessionmaker"
        assert type(CoordinationSession).__name__ == "async_sessionmaker"

    def test_engines_use_nullpool(self):
        from spellbook.db.engines import (
            spellbook_engine,
            fractal_engine,
            forged_engine,
            coordination_engine,
        )
        from sqlalchemy.pool import NullPool

        for engine in (spellbook_engine, fractal_engine, forged_engine, coordination_engine):
            assert isinstance(engine.pool, NullPool)

    def test_engine_urls_point_to_correct_db(self):
        from spellbook.db.engines import (
            spellbook_engine,
            fractal_engine,
            forged_engine,
            coordination_engine,
        )

        expected_dir = Path.home() / ".local" / "spellbook"
        assert str(spellbook_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'spellbook.db'}"
        assert str(fractal_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'fractal.db'}"
        assert str(forged_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'forged.db'}"
        assert str(coordination_engine.url) == f"sqlite+aiosqlite:///{expected_dir / 'coordination.db'}"


class TestSessionContextManager:
    @pytest.mark.asyncio
    async def test_get_spellbook_session_yields_session(self):
        """Test that get_spellbook_session yields an AsyncSession."""
        from spellbook.db import get_spellbook_session
        from sqlalchemy.ext.asyncio import AsyncSession

        async with get_spellbook_session() as session:
            assert isinstance(session, AsyncSession)


class TestHelpers:
    def test_apply_pagination(self):
        from spellbook.db.helpers import apply_pagination
        from sqlalchemy import Column, Integer
        from sqlalchemy.orm import DeclarativeBase
        from sqlalchemy import select

        class Base(DeclarativeBase):
            pass

        class Dummy(Base):
            __tablename__ = "dummy"
            id = Column(Integer, primary_key=True)

        query = select(Dummy)
        paginated = apply_pagination(query, page=2, per_page=25)
        compiled = str(paginated.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == "SELECT dummy.id \nFROM dummy\n LIMIT 25 OFFSET 25"

    def test_apply_sorting_valid_column(self):
        from spellbook.db.helpers import apply_sorting
        from sqlalchemy import select, Column, Integer, String
        from sqlalchemy.orm import DeclarativeBase

        class Base(DeclarativeBase):
            pass

        class Dummy(Base):
            __tablename__ = "dummy2"
            id = Column(Integer, primary_key=True)
            name = Column(String)
            created_at = Column(String)

        query = select(Dummy)
        sorted_q = apply_sorting(
            query, Dummy, "name", "asc",
            allowed_columns={"name", "created_at"},
            default_column="created_at",
        )
        compiled = str(sorted_q.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == "SELECT dummy2.id, dummy2.name, dummy2.created_at \nFROM dummy2 ORDER BY dummy2.name ASC"

    def test_apply_sorting_invalid_column_falls_back(self):
        from spellbook.db.helpers import apply_sorting
        from sqlalchemy import select, Column, Integer, String
        from sqlalchemy.orm import DeclarativeBase

        class Base(DeclarativeBase):
            pass

        class Dummy(Base):
            __tablename__ = "dummy3"
            id = Column(Integer, primary_key=True)
            created_at = Column(String)

        query = select(Dummy)
        sorted_q = apply_sorting(
            query, Dummy, "INVALID_COLUMN", "desc",
            allowed_columns={"created_at"},
            default_column="created_at",
        )
        compiled = str(sorted_q.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == "SELECT dummy3.id, dummy3.created_at \nFROM dummy3 ORDER BY dummy3.created_at DESC"


class TestDispose:
    @pytest.mark.asyncio
    async def test_dispose_all_engines_runs_without_error(self):
        from spellbook.db import dispose_all_engines

        await dispose_all_engines()


class TestPragmas:
    @pytest.mark.asyncio
    async def test_pragmas_applied_on_connection(self):
        """Verify WAL, synchronous, and foreign_keys pragmas are set."""
        from spellbook.db import get_spellbook_session
        import sqlalchemy

        async with get_spellbook_session() as session:
            result = await session.execute(sqlalchemy.text("PRAGMA journal_mode"))
            assert result.scalar() == "wal"

            result = await session.execute(sqlalchemy.text("PRAGMA synchronous"))
            # NORMAL = 1
            assert result.scalar() == 1

            result = await session.execute(sqlalchemy.text("PRAGMA foreign_keys"))
            assert result.scalar() == 1
