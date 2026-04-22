"""Tests for ``spellbook.worker_llm.observability.record_call``.

Strategy
--------
Per design §3, ``record_call`` writes via ``get_spellbook_sync_session()``.
We swap that dependency for a real tmp-file SQLite database whose
``worker_llm_calls`` table is created in the fixture. This exercises the
real SQLAlchemy ORM insert path (not a mock of a mock) while keeping the
test hermetic.

Bigfoot has a ``db_mock`` state-machine plugin for sqlite3/DB-API-level
assertions, but the production code goes through SQLAlchemy's ORM — the
DB-API calls are compiled by SQLAlchemy and therefore fragile across
SQLAlchemy versions. The impl plan (Step 5) explicitly permits the
"in-memory SQLite via ``get_spellbook_sync_session`` with a conftest
fixture that ensures the table exists" alternative; we use a tmp-file DB
(sqlite in-memory is per-connection, which breaks across sessions).

``caplog`` is allowed by AGENTS.md for log assertions; this file uses it
because the bigfoot ``log_mock`` plugin requires every log interaction to
be asserted and the record_call happy path intentionally emits no logs.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import select

from spellbook.db.engines import get_sync_session
from spellbook.db.spellbook_models import SpellbookBase, WorkerLLMCall
from spellbook.worker_llm import observability


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    """Create a tmp-file sqlite DB with the ``worker_llm_calls`` table and
    redirect ``observability.get_spellbook_sync_session`` to it."""
    db_path = str(tmp_path / "spellbook.db")

    # Create every SpellbookBase-registered table (including worker_llm_calls)
    # on the tmp DB. Using the sync engine builder keeps this path lock-free.
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{db_path}")
    SpellbookBase.metadata.create_all(engine)
    engine.dispose()

    # Swap the module-local reference to the sync-session context manager so
    # ``record_call`` writes into the tmp DB instead of the real spellbook.db.
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
    """Each test starts with a clean ``_record_call_failures`` counter so the
    first-loud/rest-quiet log policy is asserted per-test, not globally."""
    monkeypatch.setattr(observability, "_record_call_failures", 0)


def test_record_call_writes_row(fresh_db):
    """Happy path: every kwarg lands on the row verbatim.

    ESCAPE: test_record_call_writes_row
      CLAIM:    record_call inserts a WorkerLLMCall row populated from kwargs.
      PATH:     record_call -> get_spellbook_sync_session -> session.add -> commit.
      CHECK:    A single row exists; every column equals the expected value.
      MUTATION: If record_call dropped any kwarg or hard-coded a column, the
                full-equality assertion on to_dict() would fail.
      ESCAPE:   A no-op implementation is caught by the row-count check; a
                partial implementation is caught by the full-equality check.
      IMPACT:   Observability dashboard would miss fields or show wrong values.
    """
    observability.record_call(
        task="tool_safety",
        model="gpt-test",
        latency_ms=123,
        status="success",
        prompt_len=456,
        response_len=789,
        error=None,
        override_loaded=True,
    )

    # Open a fresh session against the same tmp DB to read back the row.
    with get_sync_session(fresh_db) as session:
        rows = session.execute(select(WorkerLLMCall)).scalars().all()

    assert len(rows) == 1
    row = rows[0].to_dict()
    # ``timestamp`` is ``datetime.now(UTC).isoformat()`` — genuinely
    # unknowable before the call, so we extract-and-validate separately
    # rather than leak ``pychoir.IsInstance`` here. Every OTHER field is
    # asserted by full dict equality below.
    ts = row.pop("timestamp")
    assert ts.endswith("+00:00")  # UTC ISO-8601 marker
    # Row id is autoincrement-assigned by SQLite; first row -> 1.
    assert row == {
        "id": 1,
        "task": "tool_safety",
        "model": "gpt-test",
        "status": "success",
        "latency_ms": 123,
        "prompt_len": 456,
        "response_len": 789,
        "error": None,
        "override_loaded": True,
    }


def test_record_call_uses_provided_timestamp(fresh_db):
    """When ``timestamp`` kwarg is passed, record_call writes it verbatim
    (no re-generation via ``datetime.now``)."""
    observability.record_call(
        task="t",
        model="m",
        latency_ms=0,
        status="success",
        prompt_len=0,
        response_len=0,
        timestamp="2026-04-20T12:00:00+00:00",
    )

    with get_sync_session(fresh_db) as session:
        rows = session.execute(select(WorkerLLMCall)).scalars().all()

    assert len(rows) == 1
    assert rows[0].timestamp == "2026-04-20T12:00:00+00:00"


def test_record_call_swallows_error_first_failure_warns(
    fresh_db, monkeypatch, caplog,
):
    """First failure -> WARNING, counter=1; no exception escapes.

    ESCAPE: test_record_call_swallows_error_first_failure_warns
      CLAIM:    First record_call exception logs at WARNING, increments counter.
      PATH:     record_call -> session.add raises -> except branch -> log.warning.
      CHECK:    No exception propagates; one WARNING record exists; counter==1.
      MUTATION: If the except clause re-raised, the test would fail with the
                forced RuntimeError. If the counter didn't increment, the next
                test (debug) would fail. If warning-vs-debug were swapped on
                the first call, the level assertion would fail.
      ESCAPE:   Silently swallowing WITHOUT logging: the WARNING assertion
                would fail. Crashing on the first call: the forced exception
                would escape.
      IMPACT:   An operator would miss the first disk-full / schema-drift
                signal that this log line is designed to surface.
    """
    def boom(*args, **kwargs):
        raise RuntimeError("forced for test")

    monkeypatch.setattr(observability, "WorkerLLMCall", boom)

    with caplog.at_level(logging.DEBUG, logger="spellbook.worker_llm.observability"):
        # Must not raise.
        observability.record_call(
            task="t",
            model="m",
            latency_ms=0,
            status="error",
            prompt_len=0,
            response_len=0,
            error="oops",
        )

    records = [
        r for r in caplog.records
        if r.name == "spellbook.worker_llm.observability"
    ]
    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert "record_call failed" in records[0].message
    assert "RuntimeError" in records[0].message
    assert observability._record_call_failures == 1


def test_record_call_subsequent_failures_log_debug(
    fresh_db, monkeypatch, caplog,
):
    """Second-and-later failures -> DEBUG; counter keeps incrementing.

    ESCAPE: test_record_call_subsequent_failures_log_debug
      CLAIM:    After the first failure, further failures log at DEBUG.
      PATH:     record_call (1st call) -> warn; record_call (2nd) -> debug.
      CHECK:    First record at WARNING, second at DEBUG; counter==2.
      MUTATION: If every failure logged WARNING, the second assertion fails.
                If the counter didn't increment, both calls would be treated
                as "first" and both would be WARNING — caught here.
      ESCAPE:   A broken impl that logs WARNING for all calls would fail the
                level check on the second record.
      IMPACT:   Under a sustained DB-lock, WARNING-every-time would produce a
                log stampede that drowns other signals.
    """
    def boom(*args, **kwargs):
        raise RuntimeError("forced for test")

    monkeypatch.setattr(observability, "WorkerLLMCall", boom)

    with caplog.at_level(logging.DEBUG, logger="spellbook.worker_llm.observability"):
        observability.record_call(
            task="t", model="m", latency_ms=0, status="error",
            prompt_len=0, response_len=0, error="1",
        )
        observability.record_call(
            task="t", model="m", latency_ms=0, status="error",
            prompt_len=0, response_len=0, error="2",
        )

    records = [
        r for r in caplog.records
        if r.name == "spellbook.worker_llm.observability"
    ]
    assert len(records) == 2
    assert records[0].levelname == "WARNING"
    assert records[1].levelname == "DEBUG"
    assert observability._record_call_failures == 2
