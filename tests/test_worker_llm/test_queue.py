"""Tests for ``spellbook.worker_llm.queue``.

Covers: availability gate, start/stop lifecycle, enqueue + drain, callback
invocation, callback failure isolation, drop-oldest on overflow, and the
``publish_call`` event emission on drops.

Strategy
--------
- HTTP mocking uses the existing ``worker_llm_transport`` bigfoot-backed
  fixture to intercept ``/chat/completions`` calls that the consumer
  dispatches via ``client.call``.
- Event emission is asserted via ``monkeypatch`` on the module-local
  ``publish_call`` name inside ``queue.py`` (no ``unittest.mock``). The
  carve-out mirrors ``test_transcript_harvest.py``'s file-scope comment:
  registering bigfoot mocks from inside a test body after the sandbox is
  already active breaks the sandbox exit gate.
- No ``unittest.mock`` anywhere.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from spellbook.worker_llm import queue as _queue


def _ok(content: str) -> dict:
    """Wrap ``content`` in an OpenAI-compatible chat-completion envelope."""
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture(autouse=True)
def _reset_queue_state():
    """Ensure each test starts with fresh module state."""
    _queue._reset_for_tests()
    yield
    _queue._reset_for_tests()


@pytest.fixture
def stub_prompts(monkeypatch):
    """Stub ``prompts.load`` so the consumer path does not need real prompt
    files on disk."""
    from spellbook.worker_llm import prompts

    def _fake_load(task_name: str) -> tuple[str, bool]:
        return (f"system-for-{task_name}", False)

    monkeypatch.setattr(prompts, "load", _fake_load)
    return _fake_load


# ---------------------------------------------------------------------------
# is_available + lifecycle
# ---------------------------------------------------------------------------


def test_is_available_false_before_start():
    assert _queue.is_available() is False


@pytest.mark.asyncio
async def test_start_then_stop_is_idempotent(stub_prompts):
    await _queue.start_queue()
    assert _queue.is_available() is True
    # Second start is a no-op; does not throw.
    await _queue.start_queue()
    assert _queue.is_available() is True
    await _queue.stop_queue()
    assert _queue.is_available() is False


# ---------------------------------------------------------------------------
# enqueue + consumer drain + callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_runs_task_and_invokes_callback(
    worker_llm_transport, worker_llm_config, stub_prompts
):
    """A queued task is consumed, client.call is invoked, and the callback
    receives the ``WorkerResult`` with the parsed text."""
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("hello-from-worker"))])

    received: list[_queue.WorkerResult] = []
    done = asyncio.Event()

    async def cb(result: _queue.WorkerResult) -> None:
        received.append(result)
        done.set()

    await _queue.start_queue()
    try:
        queued = await _queue.enqueue(
            "transcript_harvest", "some transcript", callback=cb
        )
        assert queued is True
        await asyncio.wait_for(done.wait(), timeout=2.0)
    finally:
        await _queue.stop_queue()

    assert len(received) == 1
    r = received[0]
    assert r.task_name == "transcript_harvest"
    assert r.text == "hello-from-worker"
    assert r.error is None


@pytest.mark.asyncio
async def test_callback_exception_does_not_crash_consumer(
    worker_llm_transport, worker_llm_config, stub_prompts
):
    """A throwing callback must not take the consumer down -- the next
    enqueue still runs end-to-end."""
    worker_llm_transport(
        [
            SimpleNamespace(status=200, body=_ok("one")),
            SimpleNamespace(status=200, body=_ok("two")),
        ]
    )

    ran: list[str] = []
    done_second = asyncio.Event()

    async def bad_cb(_result: _queue.WorkerResult) -> None:
        ran.append("first")
        raise RuntimeError("boom in callback")

    async def good_cb(result: _queue.WorkerResult) -> None:
        ran.append(f"second:{result.text}")
        done_second.set()

    await _queue.start_queue()
    try:
        await _queue.enqueue("transcript_harvest", "p1", callback=bad_cb)
        await _queue.enqueue("transcript_harvest", "p2", callback=good_cb)
        await asyncio.wait_for(done_second.wait(), timeout=2.0)
    finally:
        await _queue.stop_queue()

    # Both ran; the thrown exception did not block the second task.
    assert ran[0] == "first"
    assert ran[1] == "second:two"


@pytest.mark.asyncio
async def test_enqueue_raises_when_queue_not_running():
    with pytest.raises(RuntimeError, match="not running"):
        await _queue.enqueue("transcript_harvest", "p")


# ---------------------------------------------------------------------------
# Drop-oldest on overflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drop_oldest_on_overflow_publishes_drop_event(monkeypatch):
    """When the queue is full, the OLDEST task is evicted and a
    ``publish_call(status='dropped', error='queue_overflow')`` fires.

    We drive the queue directly (no consumer) so the full/drop-oldest
    behavior is deterministic. ``start_queue`` is bypassed; we install a
    pre-filled asyncio.Queue at module scope and call ``enqueue``
    directly. This avoids races between the consumer pulling items off
    and the test enqueuing new ones.
    """
    published: list[dict] = []

    def fake_publish_call(**kw):
        published.append(kw)

    monkeypatch.setattr(_queue, "publish_call", fake_publish_call)

    # Build a bounded queue with capacity 1 and plant a sentinel task so
    # the next ``enqueue`` call trips the drop-oldest path.
    q: asyncio.Queue[_queue.WorkerTask] = asyncio.Queue(maxsize=1)
    await q.put(
        _queue.WorkerTask(task_name="t_victim", prompt="oldest-payload")
    )

    # Monkeypatch the module globals so ``enqueue`` sees our queue as
    # "running in this loop".
    monkeypatch.setattr(_queue, "_queue", q)
    monkeypatch.setattr(
        _queue, "_consumer_task",
        # A dummy task that never completes so ``is_available`` stays True.
        asyncio.create_task(asyncio.sleep(60)),
    )
    monkeypatch.setattr(_queue, "_queue_loop", asyncio.get_running_loop())

    try:
        # Queue is full (size 1, one item). Enqueue triggers drop-oldest.
        result = await _queue.enqueue("t_new", "newest-payload")
        assert result is False  # indicates drop-oldest fired
    finally:
        _queue._consumer_task.cancel()
        try:
            await _queue._consumer_task
        except asyncio.CancelledError:
            pass

    # Exactly one drop published, for the victim task.
    drops = [p for p in published if p.get("status") == "dropped"]
    assert len(drops) == 1
    assert drops[0]["task"] == "t_victim"
    assert drops[0]["error"] == "queue_overflow"


# ---------------------------------------------------------------------------
# Regression: concurrent drain during ``full()`` -> ``get_nowait`` window.
#
# ``enqueue`` checks ``_queue.full()`` and then pulls the oldest task via
# ``get_nowait``. If a consumer drains between those two calls, the
# pre-fix code raised ``asyncio.QueueEmpty`` and leaked the exception to
# the caller. The guard swallows the ``QueueEmpty`` and suppresses the
# spurious ``dropped`` event.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_drain_between_full_check_and_get_nowait(monkeypatch):
    """Simulate a consumer winning the race between ``_queue.full()`` and
    ``_queue.get_nowait()`` by draining the queue inside a patched
    ``full()``. The enqueue path must not raise and must not publish a
    ``dropped`` event — there is nothing to drop once the consumer pulled
    the victim.
    """
    published: list[dict] = []

    def fake_publish_call(**kw):
        published.append(kw)

    monkeypatch.setattr(_queue, "publish_call", fake_publish_call)

    q: asyncio.Queue[_queue.WorkerTask] = asyncio.Queue(maxsize=1)
    await q.put(
        _queue.WorkerTask(task_name="t_victim", prompt="oldest-payload")
    )

    # Wrap ``full()`` so the first call returns True (invariant is still
    # "queue is at capacity at the check moment"), then drain the queue
    # before ``enqueue`` proceeds to ``get_nowait``. This deterministically
    # reproduces the race window.
    original_full = q.full
    call_count = {"n": 0}

    def racing_full() -> bool:
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Consumer drains after we report "full".
            try:
                q.get_nowait()
                q.task_done()
            except asyncio.QueueEmpty:
                pass
            return True
        return original_full()

    # Bind the patched ``full`` onto the queue instance.
    object.__setattr__(q, "full", racing_full)

    monkeypatch.setattr(_queue, "_queue", q)
    monkeypatch.setattr(
        _queue, "_consumer_task",
        asyncio.create_task(asyncio.sleep(60)),
    )
    monkeypatch.setattr(_queue, "_queue_loop", asyncio.get_running_loop())

    try:
        # Must NOT raise asyncio.QueueEmpty. The race guard falls through
        # to the ``put`` and returns True (nothing was dropped).
        result = await _queue.enqueue("t_new", "newest-payload")
        assert result is True, "No drop occurred — consumer beat us to it"
    finally:
        _queue._consumer_task.cancel()
        try:
            await _queue._consumer_task
        except asyncio.CancelledError:
            pass

    # No spurious ``dropped`` event should have been published.
    drops = [p for p in published if p.get("status") == "dropped"]
    assert drops == [], f"unexpected drop events: {drops!r}"


# ---------------------------------------------------------------------------
# Consumer surfaces worker errors to the callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_error_surfaced_on_result(
    worker_llm_transport, worker_llm_config, stub_prompts
):
    """``client.call`` raising propagates into ``WorkerResult.error``; the
    callback still runs so consumers can react."""
    import httpx

    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.TimeoutException("slow"))]
    )

    received: list[_queue.WorkerResult] = []
    done = asyncio.Event()

    async def cb(result: _queue.WorkerResult) -> None:
        received.append(result)
        done.set()

    await _queue.start_queue()
    try:
        await _queue.enqueue("transcript_harvest", "p", callback=cb)
        await asyncio.wait_for(done.wait(), timeout=2.0)
    finally:
        await _queue.stop_queue()

    assert len(received) == 1
    r = received[0]
    assert r.text is None
    assert r.error is not None
    # The worker_llm client wraps TimeoutException into WorkerLLMTimeout.
    from spellbook.worker_llm.errors import WorkerLLMTimeout

    assert isinstance(r.error, WorkerLLMTimeout)
