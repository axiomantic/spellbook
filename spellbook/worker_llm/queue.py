"""Async fire-and-forget queue for worker-LLM calls.

Fire-and-forget callers (transcript_harvest from the Stop hook, warm pings
from tool_safety cold-start detection) do not want to block on the worker
endpoint. When the queue is enabled, callers enqueue a ``WorkerTask`` and
return immediately; a single background consumer coroutine, owned by the
daemon lifespan, drains the queue and calls ``client.call`` per task.

Runtime shape
-------------
The queue and consumer live **inside the daemon event loop only**. The
helpers ``is_available`` and ``enqueue`` check that shape before routing.
Subprocess callers (hook scripts) that want to enqueue must POST to the
``/api/worker-llm/enqueue`` endpoint (see ``spellbook/mcp/routes.py``),
which runs inside the daemon loop and calls ``enqueue`` on their behalf.

Drop policy
-----------
When the queue is at capacity, ``enqueue`` drops the **OLDEST** queued
task (not the incoming one; the incoming call is the most recent signal).
The drop fires a ``publish_call(status='dropped', error='queue_overflow')``
so the overflow is observable.

Callback failures
-----------------
If a task provides ``callback``, the consumer awaits it inside a ``try``
block; any exception is logged and swallowed so one bad callback never
takes down the consumer (and therefore the queue).

This module does NOT double-publish ``call_ok`` / ``call_failed`` events
-- ``client.call``'s ``finally`` block already emits those. The queue
emits exactly one additional event-type (``dropped``) in addition to
whatever the underlying call emits.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from spellbook.core.config import config_get
from spellbook.worker_llm import client
from spellbook.worker_llm.events import publish_call

log = logging.getLogger(__name__)


# Result carrier passed to the callback. Exactly one of ``text`` / ``error``
# is set: success -> text populated, error -> error populated.
@dataclass
class WorkerResult:
    """Outcome of a consumer-side ``client.call`` for a queued task."""

    task_name: str
    text: Optional[str] = None
    error: Optional[BaseException] = None
    context: dict[str, Any] = field(default_factory=dict)


# Simple record describing one enqueued task. ``prompt`` is used as the
# single ``user_prompt`` -- the system prompt, per-task overrides, and
# max_tokens are loaded from the registered task handler rather than being
# carried through the queue, to keep the queue schema task-agnostic.
@dataclass
class WorkerTask:
    """One enqueued fire-and-forget worker-LLM call."""

    task_name: str
    prompt: str
    callback: Optional[Callable[[WorkerResult], Awaitable[None]]] = None
    enqueued_at: float = field(default_factory=time.monotonic)
    context: dict[str, Any] = field(default_factory=dict)


# Module-level queue / consumer state. The daemon lifespan creates exactly
# one queue + consumer per process. ``None`` when the queue is not running
# in this process (subprocess callers, CLI runs, test processes without the
# lifespan hook).
_queue: Optional[asyncio.Queue[WorkerTask]] = None
_consumer_task: Optional[asyncio.Task] = None
_queue_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_max_depth() -> int:
    """Return the configured queue depth, clamped to a minimum of 1.

    Guard against a pathologically small / non-numeric config value: the
    queue would otherwise raise at ``asyncio.Queue(maxsize=0)`` -- which
    creates an *unbounded* queue. Clamp to >= 1 so the drop-oldest path
    always has something to drop when full.
    """
    raw = config_get("worker_llm_queue_max_depth")
    try:
        depth = int(raw)
    except (TypeError, ValueError):
        depth = 256
    return max(1, depth)


def is_available() -> bool:
    """True iff the queue + consumer are running in the current process / loop.

    Used by sync enqueue shims and by callers deciding whether to fall back
    to the sync client path when the async queue is unavailable.
    """
    if _queue is None or _consumer_task is None:
        return False
    if _consumer_task.done():
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    return loop is _queue_loop


async def enqueue(
    task_name: str,
    prompt: str,
    callback: Optional[Callable[[WorkerResult], Awaitable[None]]] = None,
    context: Optional[dict[str, Any]] = None,
) -> bool:
    """Enqueue a fire-and-forget worker task.

    Returns:
        ``True`` if the task was queued without evicting anything.
        ``False`` if the queue was full and the oldest task was dropped to
        make room -- the incoming task is still queued.

    Raises:
        RuntimeError: The queue has not been started in this process
            (``is_available()`` is ``False``). Callers are expected to
            check availability first and fall back otherwise.
    """
    if _queue is None or not is_available():
        raise RuntimeError("worker_llm queue is not running in this process")

    task = WorkerTask(
        task_name=task_name,
        prompt=prompt,
        callback=callback,
        context=dict(context or {}),
    )

    dropped = False
    if _queue.full():
        # Drop the oldest queued task. ``get_nowait`` cannot raise here
        # because the queue is full, but guard anyway: a concurrent
        # consumer pull could drain it between our ``full()`` check and
        # the ``get_nowait``.
        try:
            victim = _queue.get_nowait()
            _queue.task_done()
            publish_call(
                task=victim.task_name,
                model="",
                latency_ms=0,
                status="dropped",
                prompt_len=len(victim.prompt),
                response_len=0,
                error="queue_overflow",
            )
            dropped = True
        except asyncio.QueueEmpty:
            # Someone beat us to it; proceed to enqueue normally.
            pass

    await _queue.put(task)
    return not dropped


def enqueue_nowait(
    task_name: str,
    prompt: str,
    callback: Optional[Callable[[WorkerResult], Awaitable[None]]] = None,
    context: Optional[dict[str, Any]] = None,
) -> bool:
    """Sync variant of ``enqueue`` for callers holding a ref to the daemon loop.

    Schedules ``enqueue`` on ``_queue_loop`` via ``call_soon_threadsafe``.
    Returns ``True`` if scheduled, ``False`` if the queue is not running.

    Unlike ``enqueue``, the boolean return does NOT reflect drop-oldest
    behavior (there is no synchronous way to observe the queued task's
    fate). Callers needing the drop-oldest signal must use ``enqueue``.
    """
    if _queue_loop is None or not _queue_loop.is_running():
        return False

    async def _do() -> None:
        try:
            await enqueue(task_name, prompt, callback=callback, context=context)
        except Exception:  # noqa: BLE001  (best-effort schedule)
            log.warning("enqueue_nowait: enqueue raised", exc_info=True)

    # Schedule on the daemon loop. ``ensure_future`` must run on that loop,
    # so we use ``call_soon_threadsafe`` to hop threads if needed.
    def _schedule() -> None:
        asyncio.ensure_future(_do(), loop=_queue_loop)

    _queue_loop.call_soon_threadsafe(_schedule)
    return True


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------


async def _run_task(task: WorkerTask) -> WorkerResult:
    """Execute one queued task via ``client.call`` and build a ``WorkerResult``.

    The underlying ``client.call`` already emits its own ``publish_call``
    via its ``finally`` block, so we do NOT emit a call event from here.
    """
    # Late-import the task handler so the queue does not pull every task's
    # dependencies into the daemon boot path.
    from spellbook.worker_llm import prompts

    try:
        system, override = prompts.load(task.task_name)
    except Exception as e:
        # Prompt load failure is the same fail-open condition as the sync
        # path; surface it as the task error.
        return WorkerResult(task_name=task.task_name, error=e, context=task.context)

    try:
        text = await client.call(
            system_prompt=system,
            user_prompt=task.prompt,
            task=task.task_name,
            override_loaded=override,
        )
        return WorkerResult(task_name=task.task_name, text=text, context=task.context)
    except BaseException as e:  # noqa: BLE001 -- capture for the callback
        return WorkerResult(task_name=task.task_name, error=e, context=task.context)


async def _consumer_loop() -> None:
    """Drain the queue forever; one task at a time, failure-isolated.

    The consumer runs serially by design: siesta is a single-writer small
    model, and running multiple worker calls in parallel would not reduce
    end-to-end latency. If parallelism becomes useful later, spawn N
    consumers against the same queue.
    """
    assert _queue is not None  # invariant: consumer only started after queue
    while True:
        try:
            task = await _queue.get()
        except asyncio.CancelledError:
            raise
        try:
            result = await _run_task(task)
            if task.callback is not None:
                try:
                    await task.callback(result)
                except Exception:  # noqa: BLE001 -- callback isolation
                    log.warning(
                        "worker_llm queue callback raised for task %r",
                        task.task_name,
                        exc_info=True,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- never crash the consumer loop
            log.warning(
                "worker_llm queue consumer: unhandled exception on task %r",
                task.task_name,
                exc_info=True,
            )
        finally:
            _queue.task_done()


# ---------------------------------------------------------------------------
# Lifespan hooks
# ---------------------------------------------------------------------------


async def start_queue() -> None:
    """Create the queue + spawn the consumer task.

    Called from ``admin/app.py:_lifespan`` at daemon startup when
    ``worker_llm_queue_enabled`` is True. Idempotent: calling twice leaves
    the existing queue / consumer in place.
    """
    global _queue, _consumer_task, _queue_loop
    if _queue is not None and _consumer_task is not None and not _consumer_task.done():
        return
    _queue = asyncio.Queue(maxsize=_get_max_depth())
    _queue_loop = asyncio.get_running_loop()
    _consumer_task = asyncio.create_task(
        _consumer_loop(), name="spellbook-worker-llm-queue"
    )


async def stop_queue() -> None:
    """Cancel + await the consumer; release module state.

    Called from the daemon lifespan's shutdown branch. Any queued tasks
    not yet picked up are discarded -- fire-and-forget semantics mean we
    do not owe the caller a completion signal.
    """
    global _queue, _consumer_task, _queue_loop
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        except Exception:
            log.debug(
                "worker_llm queue consumer raised during shutdown",
                exc_info=True,
            )
    _queue = None
    _consumer_task = None
    _queue_loop = None


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _reset_for_tests() -> None:
    """Clear module state between tests. NOT part of the public API."""
    global _queue, _consumer_task, _queue_loop
    _queue = None
    _consumer_task = None
    _queue_loop = None
