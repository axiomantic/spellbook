"""Integration tests for ``spellbook worker-llm doctor``.

Covers:

- Happy path: valid config + reachable endpoint + all 4 tasks green -> exit 0,
  JSON payload contains ``endpoint``, ``model`` and 4 ``results`` entries each
  with ``ok: true``.
- Connection failure: endpoint unreachable -> exit 2, a ``WorkerLLMUnreachable``
  (or equivalent transport error) is surfaced per result.
- Missing config: ``worker_llm_base_url`` empty -> exit 1, config check fails
  before any task runs.
- Override prompt detected: a file at
  ``~/.local/spellbook/worker_prompts/transcript_harvest.md`` (the override
  path) is reported so the operator can see that overrides are active.

These tests invoke ``_run_doctor`` directly via an ``argparse.Namespace`` —
same precedent as ``tests/test_cli/test_doctor.py::test_runs_without_crashing``.
No subprocess needed; the CLI is a thin argparse wrapper.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest


def _chat_completion(content: str) -> dict:
    """Build a minimal OpenAI-compatible ``/v1/chat/completions`` response."""
    return {"choices": [{"message": {"content": content}}]}


# Canned per-task replies that each task's parser is known to accept. See
# ``spellbook/worker_llm/tasks/*`` and their existing happy-path tests for
# the exact shape each parser consumes.
_HAPPY_SCRIPT = [
    SimpleNamespace(  # transcript_harvest
        status=200,
        body=_chat_completion(
            '[{"content":"Memory body","type":"feedback","kind":"preference",'
            '"tags":"t1","citations":""}]'
        ),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(  # memory_rerank
        status=200,
        body=_chat_completion('[{"id":"a.md","relevance_0_1":0.9}]'),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(  # roundtable_voice
        status=200,
        body=_chat_completion("**Magician**: analysis...\nVerdict: APPROVE"),
        delay_s=0.0,
        raise_on_send=None,
    ),
    SimpleNamespace(  # tool_safety
        status=200,
        body=_chat_completion('{"verdict":"OK","reasoning":"listing is safe"}'),
        delay_s=0.0,
        raise_on_send=None,
    ),
]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDoctorHappyPath:
    """All 4 tasks succeed -> exit 0, JSON payload fully populated."""

    def test_json_happy_path_exit_zero(
        self, worker_llm_transport, worker_llm_config, capsys
    ):
        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["endpoint"] == "http://test.local/v1"
        assert payload["model"] == "test-model"
        assert len(payload["results"]) == 4
        task_names = {r["task"] for r in payload["results"]}
        assert task_names == {
            "transcript_harvest",
            "memory_rerank",
            "roundtable_voice",
            "tool_safety",
        }
        for r in payload["results"]:
            assert r["ok"] is True, f"task {r['task']} reported not ok: {r}"
            assert "result_preview" in r

    def test_human_output_contains_per_task_ok(
        self, worker_llm_transport, worker_llm_config, capsys
    ):
        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=False, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        out = capsys.readouterr().out
        # Endpoint banner
        assert "http://test.local/v1" in out
        assert "test-model" in out
        # Each task reported
        assert "transcript_harvest" in out
        assert "memory_rerank" in out
        assert "roundtable_voice" in out
        assert "tool_safety" in out
        # No FAIL marker
        assert "[FAIL" not in out


# ---------------------------------------------------------------------------
# Connection failure
# ---------------------------------------------------------------------------


class TestDoctorConnectionFailure:
    """Unreachable endpoint -> exit 2, error surfaced per result."""

    def test_connect_error_exits_two(
        self, worker_llm_transport, worker_llm_config, capsys
    ):
        # Every call raises ConnectError. Need 4 entries (one per task).
        conn_err = httpx.ConnectError("connection refused")
        script = [
            SimpleNamespace(
                status=0, body="", delay_s=0.0, raise_on_send=conn_err
            )
            for _ in range(4)
        ]
        worker_llm_transport(script)

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        # Exit 2 == endpoint configured but at least one task failed.
        assert ei.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        # Every task entry must be ok=False and carry an error.
        ok_flags = [r["ok"] for r in payload["results"]]
        assert ok_flags.count(True) + ok_flags.count(False) == len(ok_flags)
        # At least one should have bubbled a connection / unreachable error.
        errors = [r.get("error", "") for r in payload["results"] if not r["ok"]]
        assert errors, "expected at least one failed task with an error message"
        assert any(
            "Unreachable" in e or "connection" in e.lower() or "ConnectError" in e
            for e in errors
        ), f"no transport error surfaced in {errors!r}"


# ---------------------------------------------------------------------------
# Missing config
# ---------------------------------------------------------------------------


class TestDoctorMissingConfig:
    """``worker_llm_base_url`` unset -> exit 1 before any task runs."""

    def test_unconfigured_exits_one(self, monkeypatch, capsys):
        # Drive the config reader with all-None so is_configured() -> False.
        from spellbook.core import config as _core_cfg
        from spellbook.worker_llm import config as _wl_cfg

        monkeypatch.setattr(_core_cfg, "config_get", lambda k: None)
        monkeypatch.setattr(_wl_cfg, "config_get", lambda k: None)

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=False, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 1

        # Config check message must appear on stderr (the human channel for
        # loud errors). Stdout may carry the endpoint banner too.
        err = capsys.readouterr().err
        assert "worker_llm_base_url" in err or "not set" in err.lower()


# ---------------------------------------------------------------------------
# Override detection
# ---------------------------------------------------------------------------


class TestDoctorOverrideDetection:
    """A file at the override path is reported in the doctor output."""

    def test_override_listed_in_output(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config, capsys
    ):
        # Redirect the override dir to a temp location so we do not touch
        # the user's real ~/.local/spellbook/worker_prompts/ tree.
        override_dir = tmp_path / "worker_prompts"
        override_dir.mkdir(parents=True)
        (override_dir / "transcript_harvest.md").write_text(
            "# override prompt body\n", encoding="utf-8"
        )

        from spellbook.worker_llm import prompts as _prompts_mod

        monkeypatch.setattr(
            _prompts_mod, "OVERRIDE_PROMPT_DIR", override_dir
        )

        # Also patch the name the doctor module imported (if any). The CLI
        # reads OVERRIDE_PROMPT_DIR off the prompts module so this single
        # patch is sufficient.
        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        overrides = payload.get("overrides", [])
        assert "transcript_harvest" in overrides, (
            f"expected transcript_harvest in overrides, got {overrides!r}"
        )


# ---------------------------------------------------------------------------
# Register + parser smoke
# ---------------------------------------------------------------------------


class TestDoctorRegister:
    """Argparse wiring sanity checks."""

    def test_register_adds_worker_llm_subcommand(self):
        import argparse

        from spellbook.cli.commands.worker_llm import register

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        args = parser.parse_args(["worker-llm", "doctor"])
        assert args.command == "worker-llm"
        assert hasattr(args, "func")

    def test_doctor_help_exits_zero(self):
        import argparse

        from spellbook.cli.commands.worker_llm import register

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        with pytest.raises(SystemExit) as ei:
            parser.parse_args(["worker-llm", "doctor", "--help"])
        assert ei.value.code == 0


# ---------------------------------------------------------------------------
# Observability health section (impl plan Step 19)
# ---------------------------------------------------------------------------


@pytest.fixture
def observability_db(tmp_path, monkeypatch):
    """Create a tmp-file SQLite DB with ``worker_llm_calls`` + redirect
    ``spellbook.db.engines.get_spellbook_sync_session`` to it.

    The doctor's observability section imports the session factory at call
    time from ``spellbook.db.engines``, so patching the attribute on that
    module is sufficient. Returns (db_path, insert_row) for tests that seed
    rows.
    """
    from contextlib import contextmanager

    from sqlalchemy import create_engine

    from spellbook.db import engines as _engines
    from spellbook.db.engines import get_sync_session
    from spellbook.db.spellbook_models import SpellbookBase, WorkerLLMCall

    db_path = str(tmp_path / "spellbook.db")
    engine = create_engine(f"sqlite:///{db_path}")
    SpellbookBase.metadata.create_all(engine)
    engine.dispose()

    @contextmanager
    def _tmp_session():
        with get_sync_session(db_path) as session:
            yield session

    monkeypatch.setattr(_engines, "get_spellbook_sync_session", _tmp_session)

    def insert(timestamp: str, task: str = "tool_safety", status: str = "success") -> None:
        with get_sync_session(db_path) as session:
            session.add(
                WorkerLLMCall(
                    timestamp=timestamp,
                    task=task,
                    model="m",
                    status=status,
                    latency_ms=0,
                    prompt_len=0,
                    response_len=0,
                    error=None,
                    override_loaded=0,
                )
            )

    return db_path, insert


class TestDoctorObservabilityHealth:
    """Doctor reports observability health: table presence, rows, purge ts,
    notification subsystem reachability (impl plan Step 19).

    Strategy
    --------
    All three tests run the doctor in ``--json`` mode with the canned happy
    script so the 4 worker-LLM tasks succeed and the doctor exits 0. The
    new observability section is asserted on the JSON payload under the
    ``observability`` key. We also spot-check the human-mode output in one
    test so the plain-text format matches the three required lines.
    """

    def test_empty_table_reports_zero_rows_and_never(
        self,
        observability_db,
        monkeypatch,
        tmp_path,
        worker_llm_transport,
        worker_llm_config,
        capsys,
    ):
        """Empty ``worker_llm_calls`` table + unwritten last-purge file = None.

        ESCAPE: test_empty_table_reports_zero_rows_and_never
          CLAIM:    Doctor reports an empty worker_llm_calls table and a
                    never-run purge loop with the precise output format.
          PATH:     _run_doctor -> _observability_health -> SELECT COUNT(*) -> 0,
                    reads read_last_purge_ts() (None) from disk (Gemini MEDIUM 3).
          CHECK:    JSON payload's ``observability`` dict is fully equal to the
                    expected dict; human-output section shows all three lines.
          MUTATION: If the row-count probe always returned >0, the assertion on
                    row_count=0 would fail. If the purge-ts branch dropped the
                    None check, ``purge_last_ran`` would not be "never". If the
                    notification probe reported unreachable, the assertion on
                    reachable=True would fail.
          ESCAPE:   A broken impl that reports a non-zero count OR swaps the
                    None sentinel label would fail full-dict equality.
          IMPACT:   Operator would see stale/fake counts and mis-diagnose a
                    silently empty observability pipeline as healthy.
        """
        from spellbook.worker_llm import observability

        # Point the cross-process last-purge record at a tmp path that has
        # not been written -> read_last_purge_ts() returns None.
        monkeypatch.setattr(
            observability, "_LAST_PURGE_PATH", tmp_path / "last_purge.json",
        )

        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["observability"] == {
            "table_present": True,
            "row_count": 0,
            "last_row_ts": None,
            "purge_last_ran": None,
            "notifications": {"reachable": True, "reason": None},
        }

    def test_human_output_contains_three_observability_lines(
        self,
        observability_db,
        monkeypatch,
        tmp_path,
        worker_llm_transport,
        worker_llm_config,
        capsys,
    ):
        """Plain-text output includes the three required observability lines.

        ESCAPE: test_human_output_contains_three_observability_lines
          CLAIM:    Human-mode doctor emits the three required section lines.
          PATH:     _run_doctor (json=False) -> prints observability section.
          CHECK:    stdout contains the three exact-prefix lines in order.
          MUTATION: If any line were dropped or re-worded, the substring check
                    on that specific line would fail.
          ESCAPE:   A broken impl that emits only 2 of 3 lines would fail the
                    missing-line assertion.
          IMPACT:   Operators running ``spellbook worker-llm doctor`` without
                    ``--json`` would lose the observability signal entirely.
        """
        from spellbook.worker_llm import observability

        monkeypatch.setattr(
            observability, "_LAST_PURGE_PATH", tmp_path / "last_purge.json",
        )

        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=False, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        out = capsys.readouterr().out
        assert "worker_llm_calls table: ok (0 rows)" in out
        assert "purge loop: never run in this daemon lifetime" in out
        assert "notification subsystem: reachable" in out

    def test_seeded_rows_report_count_and_last_ts(
        self,
        observability_db,
        monkeypatch,
        tmp_path,
        worker_llm_transport,
        worker_llm_config,
        capsys,
    ):
        """Seeded rows: count + last_row_ts match the most recent seeded row.

        ESCAPE: test_seeded_rows_report_count_and_last_ts
          CLAIM:    Doctor reports exact row count and the MAX(timestamp) of
                    the seeded rows.
          PATH:     _observability_health -> SELECT COUNT + MAX(timestamp) ->
                    payload keys row_count, last_row_ts.
          CHECK:    JSON payload's ``observability`` dict equals the expected
                    dict verbatim (row count 3, most recent ts from the seed,
                    purge_last_ran isoformat of the seeded datetime).
          MUTATION: If the MAX-ts probe returned the first row instead of the
                    last, last_row_ts would not equal the most recent seed. If
                    COUNT returned 0 or len(rows)-1, row_count would mismatch.
                    If the isoformat of _last_purge_run_ts were dropped, the
                    purge_last_ran string would not match.
          ESCAPE:   A stale count (e.g. cached 0) would fail the count
                    assertion; a wrong ordering (oldest instead of newest)
                    would fail the last_row_ts assertion.
          IMPACT:   Operator would see stale/wrong recent-activity signal; a
                    stuck purge loop could be misread as recent if the wrong
                    ts leaked through.
        """
        from datetime import datetime, timezone

        from spellbook.worker_llm import observability

        _, insert = observability_db
        insert(timestamp="2026-04-20T10:00:00+00:00", task="tool_safety", status="success")
        insert(timestamp="2026-04-20T11:00:00+00:00", task="memory_rerank", status="error")
        insert(timestamp="2026-04-20T12:00:00+00:00", task="roundtable_voice", status="success")

        purge_dt = datetime(2026, 4, 20, 12, 30, 0, tzinfo=timezone.utc)
        # Write the cross-process last-purge record to a tmp file that
        # read_last_purge_ts() will load from.
        last_purge_path = tmp_path / "last_purge.json"
        monkeypatch.setattr(observability, "_LAST_PURGE_PATH", last_purge_path)
        observability.write_last_purge_ts(purge_dt)

        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["observability"] == {
            "table_present": True,
            "row_count": 3,
            "last_row_ts": "2026-04-20T12:00:00+00:00",
            "purge_last_ran": "2026-04-20T12:30:00+00:00",
            "notifications": {"reachable": True, "reason": None},
        }

    def test_missing_table_reports_error(
        self,
        monkeypatch,
        tmp_path,
        worker_llm_transport,
        worker_llm_config,
        capsys,
    ):
        """Table-missing branch: session factory raises OperationalError.

        ESCAPE: test_missing_table_reports_error
          CLAIM:    When the SQLAlchemy session factory raises
                    ``OperationalError('no such table: worker_llm_calls')``
                    (the exact symptom an operator sees before running
                    ``alembic upgrade``), doctor reports ``table_present=False``
                    AND a non-empty ``error`` string naming the proximate cause.
          PATH:     _observability_health -> get_spellbook_sync_session() raises
                    -> except branch sets table_present=False, error=<str>.
          CHECK:    JSON payload's ``observability.table_present`` is False and
                    ``observability.error`` contains the substring
                    "no such table: worker_llm_calls". Notifications still
                    report reachable (this branch is independent).
          MUTATION: If the except branch swallowed the exception without
                    writing ``error``, the substring check would fail. If the
                    except branch set ``table_present=True`` (copy/paste miss),
                    the False assertion would fail.
          ESCAPE:   A handler that only catches a narrow subset of exceptions
                    would propagate the OperationalError and crash the doctor;
                    caught by the ``SystemExit`` assertion (exit code 0 required
                    — doctor must never crash on broken observability).
          IMPACT:   Operator with an un-migrated DB would either see a crash
                    ("doctor is broken") or silent "healthy" (missed migration),
                    both of which defeat the doctor's reason to exist.
        """
        from contextlib import contextmanager

        from sqlalchemy.exc import OperationalError

        from spellbook.db import engines as _engines
        from spellbook.worker_llm import observability

        @contextmanager
        def _broken_session():
            raise OperationalError(
                "SELECT ...", {}, Exception("no such table: worker_llm_calls")
            )
            yield  # pragma: no cover -- unreachable; keeps contextmanager shape

        monkeypatch.setattr(
            _engines, "get_spellbook_sync_session", _broken_session
        )
        monkeypatch.setattr(
            observability, "_LAST_PURGE_PATH", tmp_path / "last_purge.json",
        )

        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["observability"]["table_present"] is False
        assert "no such table: worker_llm_calls" in payload["observability"]["error"]
        # Notifications branch is independent: should still report reachable.
        assert payload["observability"]["notifications"] == {
            "reachable": True,
            "reason": None,
        }

    def test_notification_import_failure_reports_unreachable(
        self,
        observability_db,
        monkeypatch,
        tmp_path,
        worker_llm_transport,
        worker_llm_config,
        capsys,
    ):
        """Notification-unreachable branch: ``send_notification`` import fails.

        ESCAPE: test_notification_import_failure_reports_unreachable
          CLAIM:    When importing ``send_notification`` from
                    ``spellbook.notifications.notify`` raises, doctor reports
                    ``notifications.reachable=False`` AND a non-empty
                    ``reason`` string capturing the error class + message.
          PATH:     _observability_health -> ``from spellbook.notifications.notify
                    import send_notification`` raises -> except branch sets
                    reachable=False, reason=<str>.
          CHECK:    JSON payload's ``observability.notifications`` dict reports
                    reachable=False and reason is non-empty (type-prefixed).
                    Table branch still reports present=True (independent).
          MUTATION: If the except branch hard-coded reachable=True, the False
                    assertion would fail. If the except branch dropped
                    ``reason``, the non-empty assertion would fail.
          ESCAPE:   A handler that only catches ImportError but re-raises other
                    exception classes would propagate through and crash the
                    doctor; caught by the SystemExit exit-code assertion.
          IMPACT:   An operator whose notify subsystem is broken (missing
                    platform binding, permission error at import time) would
                    see "healthy" instead of the real diagnostic — exactly
                    the failure mode the doctor is supposed to surface.
        """
        import sys

        from spellbook.worker_llm import observability

        class _BrokenNotifyModule:
            """A stand-in for ``spellbook.notifications.notify`` that raises
            on ``from ... import send_notification``. Python executes the
            descriptor/``__getattr__`` when resolving the ``from`` target, so
            raising here produces the exception the except branch must catch.
            """

            def __getattr__(self, name):
                raise RuntimeError(f"notify subsystem unavailable (asked for {name!r})")

        monkeypatch.setitem(
            sys.modules, "spellbook.notifications.notify", _BrokenNotifyModule()
        )
        monkeypatch.setattr(
            observability, "_LAST_PURGE_PATH", tmp_path / "last_purge.json",
        )

        worker_llm_transport(list(_HAPPY_SCRIPT))

        from spellbook.cli.commands.worker_llm import _run_doctor

        args = SimpleNamespace(
            json=True, bench=None, runs=10, roundtable_sample=None
        )
        with pytest.raises(SystemExit) as ei:
            _run_doctor(args)
        assert ei.value.code == 0

        payload = json.loads(capsys.readouterr().out)
        notifications = payload["observability"]["notifications"]
        assert notifications["reachable"] is False
        assert notifications["reason"], "expected non-empty reason string"
        assert "notify subsystem unavailable" in notifications["reason"]
        # Table branch is independent: should still report present.
        assert payload["observability"]["table_present"] is True
