"""Tests for the fire-and-forget emitter drain in ``hooks/spellbook_hook.py``.

Before round-7 MEDIUM 1 the hook's ``main()`` spawned a daemon thread via
``_fire_and_forget`` to POST the hook-event record to the daemon and then
dropped straight into ``sys.exit``. The daemon thread could race process
exit and lose the record. The fix tracks outstanding emitter threads in
``_pending_emitter_threads`` and joins them with a short aggregate budget
before exit.

Strategy
--------
Exercise ``_drain_pending_emitters`` directly with two slow fake emitters
and assert:

1. Both threads complete when the budget is generous.
2. The function respects the deadline even when threads are still running.
3. The function never raises — each ``_wrapper`` logs its own failures.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_pending_threads():
    """Ensure each test starts with an empty pending-threads list so a
    previous test's residue cannot bleed through."""
    spellbook_hook._pending_emitter_threads.clear()
    yield
    spellbook_hook._pending_emitter_threads.clear()


def test_drain_waits_for_emitters_to_finish():
    """With a generous budget, every scheduled emitter completes."""
    completions: list[str] = []

    def _slow(label: str) -> None:
        time.sleep(0.05)
        completions.append(label)

    spellbook_hook._fire_and_forget(_slow, "a")
    spellbook_hook._fire_and_forget(_slow, "b")

    assert len(spellbook_hook._pending_emitter_threads) == 2

    spellbook_hook._drain_pending_emitters(1.0)

    # Both emitters finished within the budget.
    assert sorted(completions) == ["a", "b"]
    # Pending list cleared after drain regardless of outcome.
    assert spellbook_hook._pending_emitter_threads == []


def test_drain_respects_deadline_when_emitters_are_slow():
    """When the budget is too small for the scheduled emitters, drain
    returns at or near the deadline WITHOUT raising. Some emitters may
    still be running as daemons — they'll die with the process."""
    started = threading.Event()
    release = threading.Event()

    def _blocked() -> None:
        started.set()
        # Block well beyond the drain budget.
        release.wait(timeout=2.0)

    spellbook_hook._fire_and_forget(_blocked)
    spellbook_hook._fire_and_forget(_blocked)

    # Ensure the first thread is running before the drain starts.
    assert started.wait(timeout=1.0)

    t0 = time.monotonic()
    spellbook_hook._drain_pending_emitters(0.2)
    elapsed = time.monotonic() - t0

    # Budget is 0.2s; drain must not overrun by a large margin even with
    # two blocked emitters. Allow 0.5s slack for loaded test machines.
    assert elapsed < 0.7, (
        f"drain budget of 0.2s exceeded materially: elapsed={elapsed:.3f}s"
    )
    assert spellbook_hook._pending_emitter_threads == []

    # Release the blocked threads so they don't leak into later tests.
    release.set()


def test_drain_swallows_emitter_exceptions():
    """A target function that raises inside the daemon thread must not
    propagate out of ``_drain_pending_emitters`` — ``_fire_and_forget``'s
    wrapper logs via ``_log_hook_error`` and the join sees a terminated
    thread."""
    def _boom() -> None:
        raise RuntimeError("forced for test")

    spellbook_hook._fire_and_forget(_boom)

    # Must not raise.
    spellbook_hook._drain_pending_emitters(1.0)
    assert spellbook_hook._pending_emitter_threads == []


def test_drain_with_no_pending_emitters_is_noop():
    """Empty pending list returns immediately without raising."""
    assert spellbook_hook._pending_emitter_threads == []
    t0 = time.monotonic()
    spellbook_hook._drain_pending_emitters(1.0)
    elapsed = time.monotonic() - t0
    assert elapsed < 0.1
    assert spellbook_hook._pending_emitter_threads == []
