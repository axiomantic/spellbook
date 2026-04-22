"""Persist one row per hook dispatcher invocation into ``hook_events``.

Invoked fire-and-forget from the daemon-side ``/api/hooks/record`` route
handler (subprocess path). All failures are swallowed -- the hook must
never be blocked by observability.

Mirrors ``spellbook.worker_llm.observability`` in structure: a best-effort
synchronous writer with first-failure-warn/rest-debug log policy, plus a
retention purge loop with time-cap and count-cap passes, each batched at
``LIMIT 500`` rows per transaction with a fresh
``get_spellbook_sync_session()`` per batch so the SQLite writer lock is
released between batches.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from spellbook.core.config import config_get
from spellbook.db.engines import get_spellbook_sync_session
from spellbook.db.spellbook_models import HookEvent

log = logging.getLogger(__name__)

# Purge loop tuning. The LIMIT-per-batch is intentionally a module-level
# constant (not a config key) because its value is a function of the SQLite
# writer-lock-duration trade-off, not an operator preference. 500 keeps
# each DELETE+COMMIT under ~50ms on typical hardware.
_PURGE_BATCH_LIMIT: int = 500
_PURGE_LOOP_BACKOFF_SECONDS: float = 30.0

# Observability-of-observability: mirror ``worker_llm.observability`` so the
# FIRST ``record_hook_event`` failure in this process is loud
# (``log.warning``) and every subsequent failure is quiet (``log.debug``).
# Single-writer invariant: only ``record_hook_event`` writes this counter.
# Reset only on process restart.
_record_event_failures: int = 0


def record_hook_event(
    hook_name: str,
    event_name: str,
    duration_ms: int,
    exit_code: int,
    tool_name: str | None = None,
    error: str | None = None,
    notes: str | None = None,
    timestamp: str | None = None,
) -> None:
    """Insert a ``HookEvent`` row. Best-effort; all exceptions swallowed.

    Args:
        hook_name: Short hook identifier (e.g. ``"spellbook_hook"``).
        event_name: Claude Code hook event (e.g. ``"PreToolUse"``, ``"Stop"``,
            ``"SessionStart"``).
        duration_ms: Wall-clock duration of the hook invocation in ms.
        exit_code: Hook exit code; 0 for success, 1/2 for block/error.
        tool_name: Tool name for PreToolUse/PostToolUse events; None otherwise.
        error: Exception name or short reason on failure; None on success.
        notes: Optional JSON-ish string (e.g. tool_input summary). Truncated
            by the caller; the DB column is unbounded TEXT.
        timestamp: Optional pre-formatted ISO-8601 UTC; if ``None``,
            ``now()`` is used.
    """
    global _record_event_failures
    try:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with get_spellbook_sync_session() as session:
            session.add(
                HookEvent(
                    timestamp=ts,
                    hook_name=hook_name,
                    event_name=event_name,
                    tool_name=tool_name,
                    duration_ms=int(duration_ms),
                    exit_code=int(exit_code),
                    error=error,
                    notes=notes,
                ),
            )
            # ``get_spellbook_sync_session`` commits on clean exit and rolls
            # back on exception, so no explicit flush/commit is needed here.
    except Exception as exc:
        if _record_event_failures == 0:
            log.warning(
                "record_hook_event failed (best-effort): %s: %s. "
                "Further failures will be logged at DEBUG.",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
        else:
            log.debug("record_hook_event failed (best-effort)", exc_info=True)
        _record_event_failures += 1


# Single-writer invariant: ONLY ``_run_purge_once`` writes this after a
# successful iteration.
_last_purge_run_ts: datetime | None = None


def _run_purge_once() -> None:
    """Enforce retention caps. Best-effort; caller swallows exceptions.

    Two passes, in order:

    1. **Time cap:** delete rows whose ``timestamp`` is older than
       ``hook_observability_retention_hours``. Batched at
       ``_PURGE_BATCH_LIMIT`` rows per transaction, each batch in a fresh
       ``get_spellbook_sync_session()`` context so the writer lock is
       released between batches. Breaks when a DELETE returns 0 rows.

    2. **Count cap:** delete the oldest rows beyond the
       ``hook_observability_max_rows`` cap. Same batched-fresh-session
       pattern. Breaks when the DELETE reports 0 rows OR when the
       post-delete total row count is at/under the cap.
    """
    global _last_purge_run_ts
    retention_hours = int(config_get("hook_observability_retention_hours"))
    max_rows = int(config_get("hook_observability_max_rows"))

    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    ).isoformat()

    # --- Time cap pass ---
    while True:
        with get_spellbook_sync_session() as session:
            subq = (
                select(HookEvent.id)
                .where(HookEvent.timestamp < cutoff)
                .limit(_PURGE_BATCH_LIMIT)
            )
            result = session.execute(
                delete(HookEvent).where(HookEvent.id.in_(subq)),
            )
            if result.rowcount == 0:
                break

    # --- Count cap pass ---
    # Gemini review HIGH 4: same rewrite as worker_llm.observability.
    # Previously used ``DELETE WHERE id NOT IN (SELECT ... LIMIT max_rows)``
    # which has compile-time-optional LIMIT-inside-subquery support on
    # SQLite and degrades to O(N*M). Inline a scalar subquery that returns
    # the id of the (``max_rows`` + 1)-th row in id-DESC order; rows with
    # ``id <= threshold`` are deletable. When the table reaches max_rows,
    # the OFFSET + LIMIT 1 returns NULL and ``id <= NULL`` yields no
    # victims -> rowcount 0 -> break.
    while True:
        with get_spellbook_sync_session() as session:
            threshold_subq = (
                select(HookEvent.id)
                .order_by(HookEvent.id.desc())
                .offset(max_rows)
                .limit(1)
                .scalar_subquery()
            )
            victim_ids = (
                select(HookEvent.id)
                .where(HookEvent.id <= threshold_subq)
                .limit(_PURGE_BATCH_LIMIT)
            )
            result = session.execute(
                delete(HookEvent).where(HookEvent.id.in_(victim_ids)),
            )
            if result.rowcount == 0:
                break

    _last_purge_run_ts = datetime.now(timezone.utc)


async def purge_loop() -> None:
    """Async forever-loop wrapper around ``_run_purge_once``.

    Reads ``hook_observability_purge_interval_seconds`` from config on every
    iteration so an operator can retune without a daemon restart (the next
    tick picks up the new value). Runs the synchronous ``_run_purge_once``
    in a worker thread via ``asyncio.to_thread`` so the daemon event loop
    is never blocked by DB I/O.

    Exception policy: any exception from ``_run_purge_once`` is logged at
    DEBUG. The loop then sleeps for ``_PURGE_LOOP_BACKOFF_SECONDS`` before
    retrying so a persistent failure doesn't hot-loop the CPU.
    """
    while True:
        try:
            interval = int(
                config_get("hook_observability_purge_interval_seconds"),
            )
            # Minimum 10s floor: a pathologically small interval would
            # starve every other writer.
            interval = max(10, interval)
            await asyncio.sleep(interval)
            await asyncio.to_thread(_run_purge_once)
        except asyncio.CancelledError:
            # Lifespan shutdown. Propagate so the awaiter sees the cancel.
            raise
        except Exception:
            log.debug("purge_loop iteration failed", exc_info=True)
            await asyncio.sleep(_PURGE_LOOP_BACKOFF_SECONDS)
