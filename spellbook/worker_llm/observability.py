"""Persist one row per worker-LLM call into the ``worker_llm_calls`` table.

Invoked fire-and-forget from ``publish_call`` (daemon path) and from the
``/api/events/publish`` route handler (subprocess path). All failures are
swallowed — the LLM call must never be blocked by observability.

See design doc §3 and impl plan Step 5 for the rationale of the
first-failure-loud log policy (mirrors ``events.py:_publish_failures``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from spellbook.db.engines import get_spellbook_sync_session
from spellbook.db.spellbook_models import WorkerLLMCall

log = logging.getLogger(__name__)

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
