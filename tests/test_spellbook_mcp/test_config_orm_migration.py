"""Tests for config.py ORM migration (Task 18a).

Verifies that telemetry_enable, telemetry_disable, and telemetry_status
work correctly using SQLAlchemy ORM instead of raw SQL. Tables are created
via SQLAlchemy metadata (SpellbookBase.metadata.create_all) rather than
init_db() raw DDL.
"""

import bigfoot
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from spellbook.db.base import SpellbookBase
from spellbook.db.spellbook_models import TelemetryConfig


@pytest.fixture()
def orm_db(tmp_path):
    """Create a fresh SQLite database with ORM-created tables.

    Returns the db_path string. Tables are created via SQLAlchemy metadata,
    NOT via init_db() raw DDL. This proves the migrated code works with
    ORM-managed schema.
    """
    db_path = str(tmp_path / "orm_test.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"timeout": 5})

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SpellbookBase.metadata.create_all(engine)
    engine.dispose()
    return db_path


class TestTelemetryEnableORM:
    """telemetry_enable must use SQLAlchemy ORM, not raw SQL."""

    def test_enable_creates_telemetry_record(self, orm_db):
        """Enable telemetry with ORM-created tables (no init_db)."""
        from spellbook.core.config import telemetry_enable

        result = telemetry_enable(db_path=orm_db)

        assert result == {"status": "enabled", "endpoint_url": None}

    def test_enable_with_custom_endpoint(self, orm_db):
        """Enable with custom endpoint URL and verify full return value."""
        from spellbook.core.config import telemetry_enable

        result = telemetry_enable(
            endpoint_url="https://custom.example.com/tel",
            db_path=orm_db,
        )

        assert result == {
            "status": "enabled",
            "endpoint_url": "https://custom.example.com/tel",
        }

    def test_enable_is_idempotent(self, orm_db):
        """Calling enable twice does not error or duplicate rows."""
        from spellbook.core.config import telemetry_enable

        result1 = telemetry_enable(db_path=orm_db)
        result2 = telemetry_enable(db_path=orm_db)

        assert result1 == {"status": "enabled", "endpoint_url": None}
        assert result2 == {"status": "enabled", "endpoint_url": None}

        # Verify only one row exists
        engine = create_engine(f"sqlite:///{orm_db}")
        with Session(engine) as session:
            count = session.query(TelemetryConfig).count()
            assert count == 1
        engine.dispose()

    def test_enable_preserves_existing_endpoint_when_none_passed(self, orm_db):
        """When re-enabling without endpoint, existing endpoint is preserved."""
        from spellbook.core.config import telemetry_enable, telemetry_status

        telemetry_enable(
            endpoint_url="https://original.example.com",
            db_path=orm_db,
        )
        # Re-enable without specifying endpoint
        telemetry_enable(db_path=orm_db)

        status = telemetry_status(db_path=orm_db)
        assert status == {
            "enabled": True,
            "endpoint_url": "https://original.example.com",
            "last_sync": None,
        }

    def test_enable_updates_endpoint_when_new_one_passed(self, orm_db):
        """When re-enabling with new endpoint, endpoint is updated."""
        from spellbook.core.config import telemetry_enable, telemetry_status

        telemetry_enable(
            endpoint_url="https://old.example.com",
            db_path=orm_db,
        )
        telemetry_enable(
            endpoint_url="https://new.example.com",
            db_path=orm_db,
        )

        status = telemetry_status(db_path=orm_db)
        assert status == {
            "enabled": True,
            "endpoint_url": "https://new.example.com",
            "last_sync": None,
        }

    def test_enable_writes_orm_model_to_db(self, orm_db):
        """Verify the ORM model is correctly written to the database."""
        from spellbook.core.config import telemetry_enable

        telemetry_enable(
            endpoint_url="https://verify.example.com",
            db_path=orm_db,
        )

        # Read back via ORM to verify the model
        engine = create_engine(f"sqlite:///{orm_db}")
        with Session(engine) as session:
            row = session.get(TelemetryConfig, 1)
            assert row is not None
            assert row.id == 1
            assert row.enabled == 1
            assert row.endpoint_url == "https://verify.example.com"
            assert row.updated_at is not None
            assert row.last_sync is None
        engine.dispose()


class TestTelemetryDisableORM:
    """telemetry_disable must use SQLAlchemy ORM, not raw SQL."""

    def test_disable_sets_enabled_false(self, orm_db):
        """Disable telemetry after enabling it."""
        from spellbook.core.config import telemetry_disable, telemetry_enable

        telemetry_enable(db_path=orm_db)
        result = telemetry_disable(db_path=orm_db)

        assert result == {"status": "disabled"}

    def test_disable_without_prior_enable(self, orm_db):
        """Disable when no record exists (upsert creates disabled row)."""
        from spellbook.core.config import telemetry_disable, telemetry_status

        result = telemetry_disable(db_path=orm_db)
        assert result == {"status": "disabled"}

        status = telemetry_status(db_path=orm_db)
        assert status["enabled"] is False

    def test_disable_preserves_endpoint_url(self, orm_db):
        """Disabling does not clear the endpoint URL."""
        from spellbook.core.config import (
            telemetry_disable,
            telemetry_enable,
            telemetry_status,
        )

        telemetry_enable(
            endpoint_url="https://preserved.example.com",
            db_path=orm_db,
        )
        telemetry_disable(db_path=orm_db)

        status = telemetry_status(db_path=orm_db)
        assert status == {
            "enabled": False,
            "endpoint_url": "https://preserved.example.com",
            "last_sync": None,
        }

    def test_disable_writes_orm_model(self, orm_db):
        """Verify the ORM model reflects disabled state."""
        from spellbook.core.config import telemetry_disable

        telemetry_disable(db_path=orm_db)

        engine = create_engine(f"sqlite:///{orm_db}")
        with Session(engine) as session:
            row = session.get(TelemetryConfig, 1)
            assert row is not None
            assert row.id == 1
            assert row.enabled == 0
            assert row.updated_at is not None
        engine.dispose()


class TestTelemetryStatusORM:
    """telemetry_status must use SQLAlchemy ORM, not raw SQL."""

    def test_status_when_not_configured(self, orm_db):
        """No telemetry record returns disabled defaults."""
        from spellbook.core.config import telemetry_status

        status = telemetry_status(db_path=orm_db)

        assert status == {
            "enabled": False,
            "endpoint_url": None,
            "last_sync": None,
        }

    def test_status_after_enable(self, orm_db):
        """Status reflects enabled state."""
        from spellbook.core.config import telemetry_enable, telemetry_status

        telemetry_enable(
            endpoint_url="https://status.example.com",
            db_path=orm_db,
        )

        status = telemetry_status(db_path=orm_db)

        assert status == {
            "enabled": True,
            "endpoint_url": "https://status.example.com",
            "last_sync": None,
        }

    def test_status_after_disable(self, orm_db):
        """Status reflects disabled state with preserved endpoint."""
        from spellbook.core.config import (
            telemetry_disable,
            telemetry_enable,
            telemetry_status,
        )

        telemetry_enable(
            endpoint_url="https://status2.example.com",
            db_path=orm_db,
        )
        telemetry_disable(db_path=orm_db)

        status = telemetry_status(db_path=orm_db)

        assert status == {
            "enabled": False,
            "endpoint_url": "https://status2.example.com",
            "last_sync": None,
        }

    def test_status_error_handling(self, tmp_path):
        """Status on non-existent database returns error gracefully."""
        from spellbook.core.config import telemetry_status

        # Use a path that doesn't have the schema
        bad_db = str(tmp_path / "nonexistent_dir" / "bad.db")

        status = telemetry_status(db_path=bad_db)

        assert status["enabled"] is False
        assert status["endpoint_url"] is None
        assert status["last_sync"] is None
        assert status["status"] == "error"
        assert "message" in status


class TestTelemetryEnableErrorORM:
    """Error handling for telemetry_enable with ORM."""

    def test_enable_error_on_bad_db(self, tmp_path):
        """Enable returns error dict on database failure."""
        from spellbook.core.config import telemetry_enable

        bad_db = str(tmp_path / "nonexistent_dir" / "bad.db")

        result = telemetry_enable(db_path=bad_db)

        assert result["status"] == "error"
        assert "message" in result


class TestTelemetryDisableErrorORM:
    """Error handling for telemetry_disable with ORM."""

    def test_disable_error_on_bad_db(self, tmp_path):
        """Disable returns error dict on database failure."""
        from spellbook.core.config import telemetry_disable

        bad_db = str(tmp_path / "nonexistent_dir" / "bad.db")

        result = telemetry_disable(db_path=bad_db)

        assert result["status"] == "error"
        assert "message" in result


class TestNoRawSQLInTelemetry:
    """Verify telemetry functions do NOT use raw sqlite3 or get_connection.

    These tests enforce the ORM migration by asserting that the old
    raw SQL path (spellbook.core.db.get_connection) is never called.
    """

    def test_telemetry_enable_does_not_use_get_connection(self, orm_db):
        """telemetry_enable must not call get_connection (raw SQL)."""
        from spellbook.core.config import telemetry_enable

        mock_get_conn = bigfoot.mock("spellbook.core.db:get_connection")
        mock_get_conn.__call__.required(False)

        with bigfoot:
            telemetry_enable(db_path=orm_db)

    def test_telemetry_disable_does_not_use_get_connection(self, orm_db):
        """telemetry_disable must not call get_connection (raw SQL)."""
        from spellbook.core.config import telemetry_disable

        mock_get_conn = bigfoot.mock("spellbook.core.db:get_connection")
        mock_get_conn.__call__.required(False)

        with bigfoot:
            telemetry_disable(db_path=orm_db)

    def test_telemetry_status_does_not_use_get_connection(self, orm_db):
        """telemetry_status must not call get_connection (raw SQL)."""
        from spellbook.core.config import telemetry_status

        mock_get_conn = bigfoot.mock("spellbook.core.db:get_connection")
        mock_get_conn.__call__.required(False)

        with bigfoot:
            telemetry_status(db_path=orm_db)

    def test_telemetry_enable_does_not_import_sqlite3(self, orm_db):
        """telemetry_enable must not catch sqlite3.Error (uses SQLAlchemy exceptions)."""
        import inspect
        from spellbook.core.config import telemetry_enable

        source = inspect.getsource(telemetry_enable)
        assert "sqlite3" not in source, (
            "telemetry_enable still references sqlite3; migrate to SQLAlchemy"
        )

    def test_telemetry_disable_does_not_import_sqlite3(self, orm_db):
        """telemetry_disable must not catch sqlite3.Error."""
        import inspect
        from spellbook.core.config import telemetry_disable

        source = inspect.getsource(telemetry_disable)
        assert "sqlite3" not in source, (
            "telemetry_disable still references sqlite3; migrate to SQLAlchemy"
        )

    def test_telemetry_status_does_not_import_sqlite3(self, orm_db):
        """telemetry_status must not catch sqlite3.Error."""
        import inspect
        from spellbook.core.config import telemetry_status

        source = inspect.getsource(telemetry_status)
        assert "sqlite3" not in source, (
            "telemetry_status still references sqlite3; migrate to SQLAlchemy"
        )
