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


@pytest.fixture
def counting_session(tmp_path, monkeypatch):
    """tmp-file sqlite DB with the observability table + a connect counter.

    The fixture mirrors ``fresh_db`` but wraps the replaced
    ``get_spellbook_sync_session`` in a counter so purge-batch tests can
    assert the exact number of fresh-session-per-batch openings. The counter
    is exposed as ``counting_session.connect_count``; it increments on each
    ``__enter__`` of the context manager.

    Rationale for in-memory-style tmp-file SQLite over bigfoot.db_mock: the
    purge loop opens a fresh session per batch and SQLAlchemy ORM statements
    (SELECT + bulk DELETE) compile to multiple DB-API calls per batch, which
    makes the bigfoot.db_mock state-machine queue tedious to seed
    deterministically. Step 5's existing ``fresh_db`` fixture already
    established the tmp-file SQLite convention for ``observability.py``
    tests; T8 extends it by layering a connect counter on top, which keeps
    the "fresh session per batch" invariant assertable without bigfoot.
    """
    db_path = str(tmp_path / "spellbook.db")

    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{db_path}")
    SpellbookBase.metadata.create_all(engine)
    engine.dispose()

    from contextlib import contextmanager

    class _Counter:
        connect_count = 0

    counter = _Counter()

    @contextmanager
    def _tmp_session():
        counter.connect_count += 1
        with get_sync_session(db_path) as session:
            yield session

    monkeypatch.setattr(
        observability, "get_spellbook_sync_session", _tmp_session,
    )
    counter.db_path = db_path
    return counter


def test_run_purge_once_count_cap_only_4_batches(counting_session, monkeypatch):
    """T8: 12000 in-retention rows -> 1 time-cap probe + 5 count-cap batches.

    Seeds 12000 rows with timestamps WITHIN the retention window
    (now - 1 minute) so the time-cap pass finds zero deletable rows and
    breaks after exactly one probe SELECT. The count-cap pass then runs
    with an inlined threshold scalar subquery until the victim subquery
    returns zero rows.

    Gemini review HIGH 4: the previous ``NOT IN (SELECT ... LIMIT N)``
    implementation was replaced with an ``id <= (SELECT ... OFFSET
    max_rows LIMIT 1)`` batched scalar subquery. Under that design a
    12000-row seed produces FIVE count-cap iterations:

      - Batches 1-4 each delete exactly 500 rows (total 2000 deleted).
      - Batch 5 finds the threshold subquery returning NULL (table is now
        at max_rows), ``id <= NULL`` yields no victims, rowcount is 0,
        the loop breaks.

    Expected session sequence:
      1. Time-cap probe session (SELECT returns 0, break) -> 1 connect.
      2. Count-cap batch 1: 500 deletes -> 1 connect.
      3. Count-cap batch 2: 500 deletes -> 1 connect.
      4. Count-cap batch 3: 500 deletes -> 1 connect.
      5. Count-cap batch 4: 500 deletes -> 1 connect.
      6. Count-cap batch 5: 0 deletes (threshold NULL), break -> 1 connect.
      Total: 6 connects, final row count = 10000.

    The on-disk last-purge record (``_LAST_PURGE_PATH``) must be written
    after the purge run completes (used by Step 19's doctor CLI; see
    Gemini review MEDIUM 3 for why the record is cross-process).

    ESCAPE: test_run_purge_once_count_cap_only_4_batches
      CLAIM:    _run_purge_once opens a fresh session per batch; time-cap
                probes once (0 deletes) and count-cap runs 4 batches of
                500 deletes each plus 1 empty probe, leaving 10000 rows
                and writing the cross-process last-purge record.
      PATH:     _run_purge_once -> time-cap while loop probes + breaks ->
                count-cap while loop runs 5 fresh-session iterations
                (4 work + 1 empty) -> write_last_purge_ts() to disk.
      CHECK:    connect_count == 6; row count == 10000; the last-purge
                record on disk round-trips to a datetime.
      MUTATION: If _run_purge_once holds ONE session across all batches,
                connect_count would be 1 (or 2), not 6 — caught.
                If batch size were not 500, the row count would not be
                exactly 10000 — caught.
                If the time-cap pass ran no probe (skipped straight to
                count-cap), connect_count would be 5 — caught.
                If the last-purge record were never written, the final
                assertion would fail — caught.
      ESCAPE:   A no-op implementation would leave row count at 12000 and
                connect_count at 0 — caught by both assertions.
                An impl that deletes all 2000 overflow rows in a single
                batch (no LIMIT 500) would have connect_count == 2 (time
                probe + single delete), not 6 — caught.
      IMPACT:   Without fresh-session-per-batch discipline, the purge task
                holds a single writer lock for the entire DELETE sweep,
                starving every other SQLite writer (record_call,
                transcript_harvest, tool_safety) for seconds.
    """
    # Seed 12000 rows all WITHIN retention (ts = "now" - 60s).
    from datetime import datetime, timedelta, timezone

    recent_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=60)
    ).isoformat()
    with get_sync_session(counting_session.db_path) as session:
        session.bulk_save_objects([
            WorkerLLMCall(
                timestamp=recent_ts,
                task="t",
                model="m",
                status="success",
                latency_ms=0,
                prompt_len=0,
                response_len=0,
                error=None,
                override_loaded=0,
            )
            for _ in range(12000)
        ])
        session.commit()

    # Override config to deterministic values.
    def fake_config_get(key):
        return {
            "worker_llm_observability_retention_hours": 24,
            "worker_llm_observability_max_rows": 10000,
            "worker_llm_observability_purge_interval_seconds": 300,
        }.get(key)

    monkeypatch.setattr(observability, "config_get", fake_config_get)

    # Redirect the on-disk last-purge record to a tmp path and confirm
    # it is empty at the start so we can assert it was written.
    last_purge_path = Path(counting_session.db_path).parent / "last_purge.json"
    monkeypatch.setattr(observability, "_LAST_PURGE_PATH", last_purge_path)
    assert not last_purge_path.exists()

    # Reset connect counter after the seed phase; only purge connects count.
    counting_session.connect_count = 0

    observability._run_purge_once()

    # 1 time-cap probe + 4 count-cap work batches + 1 empty-threshold probe
    # = 6 sessions. The trailing probe is the HIGH 4 rewrite's natural
    # terminator: once the table is at max_rows, the scalar subquery
    # returns NULL, ``id <= NULL`` yields no victims, rowcount is 0, break.
    assert counting_session.connect_count == 6

    # Final row count is exactly 10000.
    with get_sync_session(counting_session.db_path) as session:
        remaining = session.execute(
            select(WorkerLLMCall),
        ).scalars().all()
    assert len(remaining) == 10000

    # The on-disk last-purge record round-trips to a datetime — this is the
    # signal the doctor CLI reads when the daemon is in another process.
    assert last_purge_path.exists()
    from datetime import datetime as _dt
    recorded = observability.read_last_purge_ts()
    assert isinstance(recorded, _dt)
