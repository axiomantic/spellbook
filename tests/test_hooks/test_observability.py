"""Tests for ``spellbook.hooks.observability.record_hook_event``.

Strategy mirrors ``tests/test_worker_llm/test_observability.py``: swap
``observability.get_spellbook_sync_session`` for a tmp-file SQLite DB
whose ``hook_events`` table is created in the fixture, then exercise
the real SQLAlchemy ORM insert path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import select

from spellbook.db.engines import get_sync_session
from spellbook.db.spellbook_models import HookEvent, SpellbookBase
from spellbook.hooks import observability


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    """Create a tmp-file sqlite DB and redirect the session factory."""
    db_path = str(tmp_path / "spellbook.db")

    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{db_path}")
    SpellbookBase.metadata.create_all(engine)
    engine.dispose()

    from contextlib import contextmanager

    @contextmanager
    def _tmp_session():
        with get_sync_session(db_path) as session:
            yield session

    monkeypatch.setattr(
        observability, "get_spellbook_sync_session", _tmp_session,
    )
    return db_path


@pytest.fixture(autouse=True)
def reset_failure_counter(monkeypatch):
    """Reset the per-process failure counter between tests."""
    monkeypatch.setattr(observability, "_record_event_failures", 0)


def test_record_hook_event_writes_row(fresh_db):
    """Happy path: every kwarg lands on the row verbatim."""
    observability.record_hook_event(
        hook_name="spellbook_hook",
        event_name="PreToolUse",
        duration_ms=42,
        exit_code=0,
        tool_name="Bash",
        error=None,
        notes='{"tool": "Bash"}',
    )

    with get_sync_session(fresh_db) as session:
        rows = session.execute(select(HookEvent)).scalars().all()

    assert len(rows) == 1
    row = rows[0].to_dict()
    ts = row.pop("timestamp")
    assert ts.endswith("+00:00")
    assert row == {
        "id": 1,
        "hook_name": "spellbook_hook",
        "event_name": "PreToolUse",
        "tool_name": "Bash",
        "duration_ms": 42,
        "exit_code": 0,
        "error": None,
        "notes": '{"tool": "Bash"}',
    }


def test_record_hook_event_uses_provided_timestamp(fresh_db):
    """When ``timestamp`` is passed, record writes it verbatim."""
    observability.record_hook_event(
        hook_name="h",
        event_name="Stop",
        duration_ms=10,
        exit_code=0,
        timestamp="2026-04-22T12:00:00+00:00",
    )

    with get_sync_session(fresh_db) as session:
        rows = session.execute(select(HookEvent)).scalars().all()

    assert len(rows) == 1
    assert rows[0].timestamp == "2026-04-22T12:00:00+00:00"


def test_record_hook_event_first_failure_warns(fresh_db, monkeypatch, caplog):
    """First failure -> WARNING, counter=1; no exception escapes."""
    def boom(*args, **kwargs):
        raise RuntimeError("forced for test")

    monkeypatch.setattr(observability, "HookEvent", boom)

    with caplog.at_level(logging.DEBUG, logger="spellbook.hooks.observability"):
        observability.record_hook_event(
            hook_name="spellbook_hook",
            event_name="Stop",
            duration_ms=0,
            exit_code=1,
            error="oops",
        )

    records = [
        r for r in caplog.records
        if r.name == "spellbook.hooks.observability"
    ]
    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert "record_hook_event failed" in records[0].message
    assert "RuntimeError" in records[0].message
    assert observability._record_event_failures == 1


def test_record_hook_event_subsequent_failures_log_debug(
    fresh_db, monkeypatch, caplog,
):
    """Second-and-later failures -> DEBUG; counter keeps incrementing."""
    def boom(*args, **kwargs):
        raise RuntimeError("forced for test")

    monkeypatch.setattr(observability, "HookEvent", boom)

    with caplog.at_level(logging.DEBUG, logger="spellbook.hooks.observability"):
        observability.record_hook_event(
            hook_name="h", event_name="e", duration_ms=0, exit_code=0,
        )
        observability.record_hook_event(
            hook_name="h", event_name="e", duration_ms=0, exit_code=0,
        )

    records = [
        r for r in caplog.records
        if r.name == "spellbook.hooks.observability"
    ]
    assert len(records) == 2
    assert records[0].levelname == "WARNING"
    assert records[1].levelname == "DEBUG"
    assert observability._record_event_failures == 2


def test_record_hook_event_swallows_unexpected_exception(fresh_db, monkeypatch):
    """Any exception type is swallowed; caller never sees it."""
    def boom(*args, **kwargs):
        raise ValueError("not a runtime error")

    monkeypatch.setattr(observability, "HookEvent", boom)

    # Must not raise.
    observability.record_hook_event(
        hook_name="h", event_name="e", duration_ms=0, exit_code=0,
    )
