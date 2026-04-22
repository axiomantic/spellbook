"""Persist one row per worker-LLM call into the ``worker_llm_calls`` table.

Invoked fire-and-forget from ``publish_call`` (daemon path) and from the
``/api/events/publish`` route handler (subprocess path). All failures are
swallowed — the LLM call must never be blocked by observability.

See design doc §3 and impl plan Step 5 for the rationale of the
first-failure-loud log policy (mirrors ``events.py:_publish_failures``).

This module also hosts the retention purge loop (impl plan Step 9):
``_run_purge_once`` performs two passes — time-cap and count-cap — each
batched at ``LIMIT 500`` rows per transaction with a FRESH
``get_spellbook_sync_session()`` per batch so the SQLite writer lock is
released between batches. ``purge_loop`` is the async wrapper.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, desc, func, select

from spellbook.core.config import config_get
from spellbook.db.engines import get_spellbook_sync_session
from spellbook.db.spellbook_models import WorkerLLMCall

log = logging.getLogger(__name__)

# Purge loop tuning. The LIMIT-per-batch is intentionally a module-level
# constant (not a config key) because its value is a function of the SQLite
# writer-lock-duration trade-off, not an operator preference. 500 keeps
# each DELETE+COMMIT under ~50ms on typical hardware.
_PURGE_BATCH_LIMIT: int = 500
_PURGE_LOOP_BACKOFF_SECONDS: float = 30.0

# Observability-of-observability: mirror the ``_publish_failures`` pattern in
# ``events.py:101-116`` so the FIRST ``record_call`` failure in this process
# is loud (``log.warning``) and every subsequent failure is quiet
# (``log.debug``). This surfaces persistent-failure conditions (disk full,
# schema drift, sustained DB lock) without drowning operator logs.
#
# Single-writer invariant: only ``record_call`` writes this counter. Reset
# only on process restart. External code should not toggle it.
_record_call_failures: int = 0


def record_call(
    task: str,
    model: str,
    latency_ms: int,
    status: str,
    prompt_len: int,
    response_len: int,
    error: str | None = None,
    override_loaded: bool = False,
    timestamp: str | None = None,
) -> None:
    """Insert a ``WorkerLLMCall`` row. Best-effort; all exceptions swallowed.

    Args:
        task: Observability tag (e.g. ``"transcript_harvest"``, ``"tool_safety"``).
        model: Model id sent to the worker.
        latency_ms: Wall-clock duration of the call in milliseconds.
        status: ``"success"`` | ``"error"`` | ``"timeout"`` | ``"fail_open"``.
        prompt_len: Character count of the rendered user prompt (pre-send).
        response_len: Character count of the raw worker response.
        error: Exception type name or short reason; ``None`` on success.
        override_loaded: ``True`` if the task used a user override prompt.
        timestamp: Optional pre-formatted ISO-8601 UTC; if ``None``, ``now()``
            is used.
    """
    global _record_call_failures
    try:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with get_spellbook_sync_session() as session:
            session.add(
                WorkerLLMCall(
                    timestamp=ts,
                    task=task,
                    model=model,
                    status=status,
                    latency_ms=int(latency_ms),
                    prompt_len=int(prompt_len),
                    response_len=int(response_len),
                    error=error,
                    override_loaded=1 if override_loaded else 0,
                ),
            )
            # ``get_spellbook_sync_session`` commits on clean exit and rolls
            # back on exception, so no explicit flush/commit is needed here.
    except Exception as exc:
        # First failure per process lifetime: loud warning naming the
        # exception type and the message. Every subsequent failure drops to
        # DEBUG to avoid log stampedes under sustained DB-locked conditions.
        # Mirror of ``events.py:_publish_failures`` (events.py:101-116).
        if _record_call_failures == 0:
            log.warning(
                "record_call failed (best-effort): %s: %s. "
                "Further failures will be logged at DEBUG.",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
        else:
            log.debug("record_call failed (best-effort)", exc_info=True)
        _record_call_failures += 1


# Single-writer invariant: ONLY ``_run_purge_once`` writes this after a
# successful iteration. ``doctor`` (impl plan Step 19) reads it.
# ``None`` sentinel means the purge loop has not yet run in this daemon
# lifetime. No lock needed because the purge task is single-threaded and
# the read in ``doctor`` only observes a monotonic timestamp — a stale
# read is acceptable (off by one iteration at most).
_last_purge_run_ts: datetime | None = None


def _run_purge_once() -> None:
    """Enforce retention caps. Best-effort; caller swallows exceptions.

    Two passes, in order:

    1. **Time cap:** delete rows whose ``timestamp`` is older than
       ``retention_hours``. Batched at ``_PURGE_BATCH_LIMIT`` rows per
       transaction, each batch in a fresh
       ``get_spellbook_sync_session()`` context so the writer lock is
       released between batches. Breaks when a DELETE returns 0 rows.

    2. **Count cap:** delete the oldest rows beyond the ``max_rows`` cap.
       Expressed as ``DELETE WHERE id NOT IN (top ``max_rows`` by
       timestamp DESC) LIMIT 500``. Same batched-fresh-session pattern.
       Breaks when the DELETE reports 0 rows OR when the post-delete
       total row count is at/under ``max_rows`` — the latter check
       avoids opening a redundant probe session after the last full
       batch.

    Why fresh session per batch? Holding one session across the whole
    sweep serializes every other SQLite writer (``record_call``,
    transcript_harvest, tool_safety, roundtable) for seconds. Per-batch
    commit releases the writer lock between batches.
    """
    global _last_purge_run_ts
    retention_hours = int(config_get("worker_llm_observability_retention_hours"))
    max_rows = int(config_get("worker_llm_observability_max_rows"))

    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    ).isoformat()

    # --- Time cap pass ---
    while True:
        with get_spellbook_sync_session() as session:
            # Subquery-based delete: SQLite's DELETE LIMIT is a
            # compile-time option not guaranteed to be present.
            subq = (
                select(WorkerLLMCall.id)
                .where(WorkerLLMCall.timestamp < cutoff)
                .limit(_PURGE_BATCH_LIMIT)
            )
            result = session.execute(
                delete(WorkerLLMCall).where(WorkerLLMCall.id.in_(subq)),
            )
            if result.rowcount == 0:
                break

    # --- Count cap pass ---
    # Keep the top-`max_rows` rows by ts DESC; delete the rest in
    # batches of 500. We pre-compute the id list per batch via
    # subquery so the DELETE is indexed.
    while True:
        with get_spellbook_sync_session() as session:
            # Subquery: ids of the rows to KEEP (top max_rows by ts DESC).
            keep_ids = (
                select(WorkerLLMCall.id)
                .order_by(WorkerLLMCall.timestamp.desc())
                .limit(max_rows)
            )
            # Delete LIMIT 500 rows not in the keep set.
            victim_ids = (
                select(WorkerLLMCall.id)
                .where(WorkerLLMCall.id.not_in(keep_ids))
                .limit(_PURGE_BATCH_LIMIT)
            )
            result = session.execute(
                delete(WorkerLLMCall).where(WorkerLLMCall.id.in_(victim_ids)),
            )
            if result.rowcount == 0:
                break
            total = session.execute(
                select(func.count()).select_from(WorkerLLMCall),
            ).scalar()
            if total is not None and total <= max_rows:
                break

    _last_purge_run_ts = datetime.now(timezone.utc)


async def purge_loop() -> None:
    """Async forever-loop wrapper around ``_run_purge_once``.

    Reads ``worker_llm_observability_purge_interval_seconds`` from config
    on every iteration so an operator can retune without a daemon restart
    (the next tick picks up the new value). Runs the synchronous
    ``_run_purge_once`` in a worker thread via ``asyncio.to_thread`` so
    the daemon event loop is never blocked by DB I/O.

    Exception policy: any exception from ``_run_purge_once`` is logged at
    DEBUG (the first-loud policy lives at the ``record_call`` site, not
    here — a purge crash is a DB-is-broken signal that will show up in
    ``doctor`` via ``_last_purge_run_ts`` staleness). The loop then
    sleeps for ``_PURGE_LOOP_BACKOFF_SECONDS`` before retrying so a
    persistent failure doesn't hot-loop the CPU.
    """
    while True:
        try:
            interval = int(
                config_get("worker_llm_observability_purge_interval_seconds"),
            )
            # Minimum 10s floor: a pathologically small interval would
            # starve every other writer. See design doc §6.
            interval = max(10, interval)
            await asyncio.sleep(interval)
            await asyncio.to_thread(_run_purge_once)
        except asyncio.CancelledError:
            # Lifespan shutdown. Propagate so the awaiter sees the cancel.
            raise
        except Exception:
            log.debug("purge_loop iteration failed", exc_info=True)
            await asyncio.sleep(_PURGE_LOOP_BACKOFF_SECONDS)


# Edge-triggered success-rate threshold notifier (design §6 / impl plan Step 10).
#
# ``_breach_state`` is module-global and assumes single-task concurrency:
# ``threshold_eval_loop`` is its SOLE writer (one task created in
# ``admin/app.py:_lifespan``). No lock is required under this invariant. A
# future parallel evaluator would need to replace this with per-task state
# or a lock. External readers (e.g. the ``doctor`` CLI) may read freely; a
# stale read is acceptable because the only meaningful assertion is
# "currently breached vs. currently healthy" and the state is self-healing
# on the next eval tick.
#
# Restart semantics: this state is in-memory only. A daemon restart during
# an active breach loses the breach record, so the first post-restart
# evaluation will either (a) re-notify on fresh detection or (b) silently
# treat recovery as "was never breached, is now healthy" -> no notification.
# Accepted trade-off per understanding doc §L2.
_breach_state: dict[str, bool] = {"is_breached": False}


async def _evaluate_threshold_once() -> None:
    """One iteration of the edge-triggered success-rate breach notifier.

    Reads the last ``notify_window`` rows from ``worker_llm_calls`` ordered
    by timestamp DESC, computes ``success_rate`` = (count of
    ``status == "success"``) / total, and fires
    ``spellbook.notifications.notify.send_notification`` ONLY on state
    transitions:

    - healthy -> breached: fires a breach notification.
    - breached -> healthy: fires a recovery notification.
    - healthy -> healthy, breached -> breached: silent (edge-triggered).

    Early-exits without reading rows or touching ``_breach_state`` when
    ``worker_llm_observability_notify_enabled`` is False. Early-exits
    (no-op) when the table has fewer than ``notify_window`` rows so a
    cold daemon doesn't alert on a single failure at startup.

    Statuses other than ``"success"`` (``"error"``, ``"timeout"``,
    ``"fail_open"``) all count as failures for the purpose of this metric.
    This must match the dashboard's ``success_rate`` definition (design §5).
    """
    if not config_get("worker_llm_observability_notify_enabled"):
        return

    threshold = float(
        config_get("worker_llm_observability_notify_threshold"),
    )
    window = int(config_get("worker_llm_observability_notify_window"))

    def _recent_success_rate() -> tuple[float | None, int]:
        """Read the last ``window`` rows (DESC by timestamp); return
        ``(rate, sample_size)`` or ``(None, n)`` if ``n < window``.

        Run under ``asyncio.to_thread`` so the sync DB I/O doesn't block
        the daemon event loop.
        """
        with get_spellbook_sync_session() as session:
            rows = session.execute(
                select(WorkerLLMCall.status)
                .order_by(desc(WorkerLLMCall.timestamp))
                .limit(window),
            ).scalars().all()
        if len(rows) < window:
            return None, len(rows)
        successes = sum(1 for s in rows if s == "success")
        return successes / len(rows), len(rows)

    rate, sample = await asyncio.to_thread(_recent_success_rate)
    if rate is None:
        # Not enough calls yet to evaluate. Do NOT touch _breach_state —
        # a cold start must not be interpreted as a recovery event.
        return

    # Late-import ``send_notification`` so tests that monkeypatch the
    # attribute on the ``notify`` module see the replacement (we bind the
    # function object at call-time, not import-time). Mirrors the
    # late-import pattern used in ``mcp/routes.py`` for ``record_call``.
    from spellbook.notifications.notify import send_notification

    was_breached = _breach_state["is_breached"]
    now_breached = rate < threshold

    if now_breached and not was_breached:
        await send_notification(
            title="Worker LLM: success rate breach",
            body=(
                f"Success rate {rate:.0%} over last {sample} calls "
                f"(< {threshold:.0%})"
            ),
        )
    elif was_breached and not now_breached:
        await send_notification(
            title="Worker LLM: success rate recovered",
            body=f"Success rate back to {rate:.0%} over last {sample} calls",
        )
    _breach_state["is_breached"] = now_breached


_THRESHOLD_LOOP_BACKOFF_SECONDS: float = 30.0


async def threshold_eval_loop() -> None:
    """Async forever-loop wrapper around ``_evaluate_threshold_once``.

    Reads ``worker_llm_observability_notify_eval_interval_seconds`` from
    config on every iteration so an operator can retune without a daemon
    restart (the next tick picks up the new value).

    Exception policy: any exception from ``_evaluate_threshold_once`` is
    logged at DEBUG and the loop then sleeps for
    ``_THRESHOLD_LOOP_BACKOFF_SECONDS`` before retrying so a persistent
    failure doesn't hot-loop the CPU. The 10s floor on the eval interval
    mirrors ``purge_loop``: a pathologically small interval would cause
    steady DB pressure.
    """
    while True:
        try:
            interval = int(
                config_get(
                    "worker_llm_observability_notify_eval_interval_seconds",
                ),
            )
            interval = max(10, interval)
            await asyncio.sleep(interval)
            await _evaluate_threshold_once()
        except asyncio.CancelledError:
            # Lifespan shutdown. Propagate so the awaiter sees the cancel.
            raise
        except Exception:
            log.debug("threshold_eval_loop iteration failed", exc_info=True)
            await asyncio.sleep(_THRESHOLD_LOOP_BACKOFF_SECONDS)
