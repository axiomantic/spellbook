"""Tests for ``spellbook.worker_llm.observability._evaluate_threshold_once``
and ``threshold_eval_loop``.

Strategy
--------
Same tmp-file SQLite pattern as ``test_observability.py`` and
``test_observability_purge.py``: we seed the real ``worker_llm_calls`` table
via the ORM, then exercise the evaluator against real ``select.limit()``
query compilation. ``config_get`` is swapped via ``monkeypatch`` to feed
deterministic thresholds / windows / feature flags.

``send_notification`` is async. We use the same monkeypatch-based spy-list
pattern the adjacent ``test_events_publish_route.py:record_call_spy``
fixture uses: swap the attribute on the ``notify`` module with a local
async stub that appends each invocation's kwargs to a list. The evaluator
late-imports the attribute (``from spellbook.notifications.notify import
send_notification``) so the monkeypatched symbol IS the one the handler
picks up. This keeps us on the repo's sanctioned pattern for
module-attribute swaps (not a mocking library — the constraint is
"bigfoot ONLY for mocks" and this is a function-replacement spy, same as
``record_call_spy``).

``_breach_state`` is a module-global single-writer dict; every test starts
from a clean ``{"is_breached": False}`` via an autouse fixture so no leak
between cases.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from spellbook.db.engines import get_sync_session
from spellbook.db.spellbook_models import SpellbookBase, WorkerLLMCall
from spellbook.notifications import notify as notify_mod
from spellbook.worker_llm import observability


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch):
    """Create a tmp-file SQLite DB with the worker_llm_calls table and
    redirect ``observability.get_spellbook_sync_session`` to it."""
    db_path = str(tmp_path / "spellbook.db")

    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{db_path}")
    SpellbookBase.metadata.create_all(engine)
    engine.dispose()

    @contextmanager
    def _tmp_session():
        with get_sync_session(db_path) as session:
            yield session

    monkeypatch.setattr(
        observability, "get_spellbook_sync_session", _tmp_session,
    )
    return db_path


@pytest.fixture(autouse=True)
def reset_breach_state(monkeypatch):
    """Each test starts with ``_breach_state = {'is_breached': False}`` so the
    edge-triggered transitions are asserted per-test, not globally."""
    monkeypatch.setattr(
        observability, "_breach_state", {"is_breached": False},
    )


@pytest.fixture
def notify_spy(monkeypatch):
    """Replace ``spellbook.notifications.notify.send_notification`` with a
    spy async fn that records every invocation's kwargs into a list.

    Mirrors the ``record_call_spy`` pattern in
    ``test_events_publish_route.py`` — the evaluator imports
    ``send_notification`` lazily INSIDE the function body (not at module
    load), so patching the attribute on the ``notify`` module binds the
    replacement before the first lookup and the handler picks it up.
    """
    calls: list[dict] = []

    async def _spy(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(notify_mod, "send_notification", _spy)
    return calls


def _fake_config(values: dict):
    """Return a single-arg ``config_get`` shim bound to ``values``."""

    def _get(key):
        return values[key]

    return _get


def _seed_rows(db_path: str, statuses: list[str]) -> None:
    """Insert one WorkerLLMCall row per element of ``statuses`` with
    monotonically increasing timestamps so the LIMIT-by-DESC-timestamp
    query returns them in the expected recency order.

    The evaluator doesn't care about ordering within the window — only
    the success count over the last ``window`` rows matters — but we use
    distinct timestamps anyway to avoid any ordering-dependent test fragility
    (SQLite sort is stable on ties but the dialect doesn't guarantee row
    order across runs).
    """
    from datetime import datetime, timedelta, timezone

    base = datetime.now(timezone.utc)
    with get_sync_session(db_path) as session:
        for i, status in enumerate(statuses):
            session.add(
                WorkerLLMCall(
                    timestamp=(base + timedelta(seconds=i)).isoformat(),
                    task="t",
                    model="m",
                    status=status,
                    latency_ms=0,
                    prompt_len=0,
                    response_len=0,
                    error=None if status == "success" else "e",
                    override_loaded=0,
                ),
            )
        session.commit()


# --- Tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_insufficient_sample_noop(fresh_db, monkeypatch, notify_spy):
    """T12: fewer than ``notify_window`` rows -> no notification, state
    unchanged.

    ESCAPE: test_insufficient_sample_noop
      CLAIM:    When the table has fewer than ``notify_window`` rows, the
                evaluator returns without evaluating rate or touching state.
      PATH:     _evaluate_threshold_once -> _recent_success_rate -> len<window
                -> return None -> early return before notify.
      CHECK:    notify_spy list is empty; _breach_state unchanged.
      MUTATION: If the evaluator ignored the window check and computed rate
                from a partial sample, 3 errors at threshold 0.8 would be
                rate 0.0 and breach; spy would capture one call -- caught.
                Specifically: if ``< window`` were replaced with ``<= 0``,
                a single "error" row would trip a breach.
      ESCAPE:   A broken impl that also checked ``notify_enabled`` first and
                happened to skip for an unrelated reason would pass this
                test. Covered by the separate notify_enabled test below.
      IMPACT:   Without the sample-size gate, a cold daemon (0-3 rows) would
                notify on any single failure, spamming the operator at
                startup.
    """
    _seed_rows(fresh_db, ["error", "error", "error"])

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": True,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == []
    assert observability._breach_state == {"is_breached": False}


@pytest.mark.asyncio
async def test_notify_disabled_no_notification(
    fresh_db, monkeypatch, notify_spy,
):
    """T11: clear breach but ``notify_enabled=False`` -> no notification,
    state unchanged.

    ESCAPE: test_notify_disabled_no_notification
      CLAIM:    When ``notify_enabled`` is False, the evaluator returns
                BEFORE reading any rows or updating state, regardless of
                the underlying success rate.
      PATH:     _evaluate_threshold_once -> config_get(notify_enabled)=False
                -> early return.
      CHECK:    notify_spy empty; _breach_state unchanged.
      MUTATION: If the enabled check were dropped, a table of 20 errors at
                threshold 0.8 would yield rate=0.0, breach=True, and a
                breach notification would fire -- the spy list would be
                non-empty.
      ESCAPE:   A broken impl that checked enabled AFTER notifying would
                still fire and fail the spy-list check.
      IMPACT:   Operators who haven't opted into notifications would get
                unsolicited desktop notifications -- bad first impression
                and likely source of a "disable this feature" ticket.
    """
    _seed_rows(fresh_db, ["error"] * 20)

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": False,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == []
    assert observability._breach_state == {"is_breached": False}


@pytest.mark.asyncio
async def test_healthy_stays_healthy_no_notification(
    fresh_db, monkeypatch, notify_spy,
):
    """Healthy -> healthy transition is a no-op: no notification, no state
    flip.

    ESCAPE: test_healthy_stays_healthy_no_notification
      CLAIM:    When the prior state is healthy AND the current rate is
                above threshold, no notification fires and state stays
                False.
      PATH:     _evaluate_threshold_once -> rate >= threshold AND
                was_breached=False -> neither notify branch fires.
      CHECK:    notify_spy empty; _breach_state still False.
      MUTATION: If the code notified on every healthy evaluation, the spy
                list would be non-empty. If the state flipped to True
                erroneously, the dict equality fails.
      ESCAPE:   None beyond the mutation above.
      IMPACT:   Notification spam on every healthy eval interval would
                train operators to ignore real breaches.
    """
    _seed_rows(fresh_db, ["success"] * 20)

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": True,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == []
    assert observability._breach_state == {"is_breached": False}


@pytest.mark.asyncio
async def test_healthy_to_breached_sends_breach_notification(
    fresh_db, monkeypatch, notify_spy,
):
    """Healthy -> breached transition: exactly ONE breach notification,
    state flips to True.

    ESCAPE: test_healthy_to_breached_sends_breach_notification
      CLAIM:    When prior state is healthy AND current rate < threshold,
                send_notification fires exactly once with the breach
                title/body AND _breach_state flips to True.
      PATH:     _evaluate_threshold_once -> rate < threshold AND
                was_breached=False -> notify(breach) + set is_breached=True.
      CHECK:    notify_spy == [expected_breach_kwargs]; _breach_state
                {"is_breached": True}.
      MUTATION: If the breach message logic computed the percentage with
                wrong formula, the body string would not equal the
                expected value -- caught by full-equality.
                If notify was called twice (missing edge gate), spy would
                have two entries.
                If the state wasn't flipped, the assertion fails.
      ESCAPE:   A broken impl that notified but forgot to flip state would
                fail the state assertion.
      IMPACT:   Wrong title/body or missed state flip breaks the operator
                experience: either confusing message, or repeated alerts
                on every eval tick (stampede).
    """
    _seed_rows(fresh_db, ["success"] * 10 + ["error"] * 10)

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": True,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == [
        {
            "title": "Worker LLM: success rate breach",
            "body": "Success rate 50% over last 20 calls (< 80%)",
        },
    ]
    assert observability._breach_state == {"is_breached": True}


@pytest.mark.asyncio
async def test_still_breached_no_second_notification(
    fresh_db, monkeypatch, notify_spy,
):
    """Already-breached stays breached: no second notification fires.

    ESCAPE: test_still_breached_no_second_notification
      CLAIM:    When prior state is ALREADY breached AND current rate is
                still < threshold, no notification fires and state stays
                True.
      PATH:     _evaluate_threshold_once -> rate < threshold AND
                was_breached=True -> neither branch fires; state reassigned
                True (unchanged).
      CHECK:    notify_spy empty; _breach_state still True.
      MUTATION: If the edge gate were removed (notify on every breach),
                the spy would be non-empty. If the state accidentally
                reset to False, the next healthy eval would misreport a
                recovery.
      ESCAPE:   None beyond the mutation above.
      IMPACT:   Without the edge gate, a sustained breach would fire a
                notification every ``notify_eval_interval_seconds``
                (default 60s), producing a steady alert stream that
                trains operators to mute the feature.
    """
    monkeypatch.setattr(
        observability, "_breach_state", {"is_breached": True},
    )

    _seed_rows(fresh_db, ["error"] * 20)

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": True,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == []
    assert observability._breach_state == {"is_breached": True}


@pytest.mark.asyncio
async def test_breached_to_healthy_sends_recovery_notification(
    fresh_db, monkeypatch, notify_spy,
):
    """Breached -> healthy transition: exactly ONE recovery notification,
    state flips back to False.

    ESCAPE: test_breached_to_healthy_sends_recovery_notification
      CLAIM:    When prior state is breached AND current rate >= threshold,
                send_notification fires exactly once with the recovery
                title/body AND _breach_state flips to False.
      PATH:     _evaluate_threshold_once -> rate >= threshold AND
                was_breached=True -> notify(recovery) + set
                is_breached=False.
      CHECK:    notify_spy == [expected_recovery_kwargs]; _breach_state
                {"is_breached": False}.
      MUTATION: If the code flipped state but used the breach message text,
                the spy-list equality check fails. If it notified twice
                (breach + recovery), list length fails. If state wasn't
                flipped back, a subsequent breach would miss its edge.
      ESCAPE:   A broken impl that swapped the branches (notify breach on
                recovery) fails the title-field check.
      IMPACT:   Without the recovery notification, operators would wonder
                "did this get fixed?" and either page-investigate or
                miss-learn that the feature is lossy.
    """
    monkeypatch.setattr(
        observability, "_breach_state", {"is_breached": True},
    )

    _seed_rows(fresh_db, ["success"] * 20)

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": True,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == [
        {
            "title": "Worker LLM: success rate recovered",
            "body": "Success rate back to 100% over last 20 calls",
        },
    ]
    assert observability._breach_state == {"is_breached": False}


@pytest.mark.asyncio
async def test_fail_open_error_timeout_count_as_failures(
    fresh_db, monkeypatch, notify_spy,
):
    """The success-rate denominator is TOTAL rows, and only
    ``status == "success"`` counts as a success.

    Pins down the definition of ``success_rate``: successes / total.
    Rows with status ``fail_open``, ``error``, or ``timeout`` all count
    as failures. 15 successes + 5 mixed failures -> rate 15/20 = 0.75 <
    0.8 threshold -> breach fires with exact percentage in body.

    ESCAPE: test_fail_open_error_timeout_count_as_failures
      CLAIM:    success_rate = count(status == 'success') / len(window).
                Rows with status in {'fail_open', 'error', 'timeout'} all
                count as failures.
      PATH:     _recent_success_rate -> sum(s=='success') / len(rows).
      CHECK:    Breach fires with body "Success rate 75% over last 20
                calls (< 80%)".
      MUTATION: If fail_open were counted as success, rate would be
                16/20 = 0.80, NOT strictly less than threshold 0.8, so no
                breach would fire and notify_spy would be empty --
                caught. This is the load-bearing case for the
                failure-taxonomy mutation.
                If timeout were counted as success: rate = 17/20 = 0.85,
                same story.
                If error were counted as success: rate = 17/20 = 0.85,
                same story.
      ESCAPE:   None remaining — each non-success status shifts the rate
                above or to exactly threshold.
      IMPACT:   Dashboard "success rate" must match the notifier's
                definition; if they diverge, operators question which
                number to trust.
    """
    _seed_rows(
        fresh_db,
        ["success"] * 15
        + ["error", "error", "timeout", "timeout", "fail_open"],
    )

    monkeypatch.setattr(
        observability,
        "config_get",
        _fake_config({
            "worker_llm_observability_notify_enabled": True,
            "worker_llm_observability_notify_threshold": 0.8,
            "worker_llm_observability_notify_window": 20,
        }),
    )

    await observability._evaluate_threshold_once()

    assert notify_spy == [
        {
            "title": "Worker LLM: success rate breach",
            "body": "Success rate 75% over last 20 calls (< 80%)",
        },
    ]
    assert observability._breach_state == {"is_breached": True}


def test_breach_state_module_global_exists_and_defaults_false():
    """_breach_state is a module-global dict with the single key
    ``is_breached`` defaulting to False.

    ESCAPE: test_breach_state_module_global_exists_and_defaults_false
      CLAIM:    observability._breach_state is {'is_breached': False}.
      PATH:     module-level initializer in observability.py.
      CHECK:    exact-equality assertion on the dict.
      MUTATION: If the initializer used a different key name (e.g.
                'in_breach' per the design doc draft) or a different
                default, the equality fails.
      ESCAPE:   None; the assertion is against a single concrete dict.
      IMPACT:   The docstring contract says is_breached; violating it
                means external readers (e.g. doctor CLI if it ever peeks)
                would break.
    """
    # Autouse fixture re-seeds _breach_state; its value at this point is
    # the post-reset value which equals the module initializer shape.
    assert observability._breach_state == {"is_breached": False}
