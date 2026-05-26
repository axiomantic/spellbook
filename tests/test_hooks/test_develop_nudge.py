"""Tests for the develop accountability nudge (design §6, impl Tasks 6/7/8).

The nudge lives on UserPromptSubmit (`_handle_user_prompt_submit`) and fires
iff ALL of (design §6.1):

1. `active_skill == "develop"` in workflow_state, AND
2. develop is past Phase 0 (`skill_phase` set and not "0"), AND
3. `develop_gate_ledger` is absent/empty.

It is duration-blind (NOT wall-clock). Debounce is via a marker FILE keyed by
`session_id` (NOT an in-process flag — hooks are per-event subprocesses), at
`${SPELLBOOK_CONFIG_DIR}/runtime/develop-nudge/<session_id>.nudged`. The marker
is removed on SessionStart (Task 7 — no SessionEnd handler exists) so a later
run of the same session can nudge again.

These tests exercise the handler functions directly (not via the hook
subprocess) so we can assert exact-equality against the complete produced
message. The marker directory is isolated to a tmp path via the
`SPELLBOOK_CONFIG_DIR` env override.

IMP-1 (`test_no_nudge_during_phase0_wizard`): proves the interactive Phase-0
wizard does not false-fire the nudge on every prompt.

IMP-2 (`test_nudge_debounced_via_marker_file`): proves the debounce is a marker
FILE that survives across separate (subprocess-simulating) handler invocations.
An in-process flag would fail this test because each call is fresh state — the
ONLY thing persisting between the two calls is the on-disk marker file.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import tripwire

# Ensure hooks/ is on sys.path so we can import spellbook_hook directly.
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

# The verbatim nudge message (design §6.2). Asserted by exact equality.
EXPECTED_NUDGE = (
    "[develop accountability] The develop skill is marked active for this project but no develop\n"
    "phase/progress has been recorded in workflow_state. If you are mid-develop, record your current\n"
    'phase and remaining gates now via workflow_state_update({"develop_gate_ledger": {...}}). If develop\n'
    "is no longer active here, clear it. Unrecorded progress will be lost on the next context compaction."
)

CWD = "/some/project"


def _stub_workflow_state(state: dict | None, *, expected_calls: int = 1):
    """Register a tripwire mock for `_mcp_call` returning the given state.

    Mirrors the real MCP return shape: a `workflow_state_load` call returns
    `{"found": bool, "state": {...}}`. Any other tool call (e.g. memory
    recall/autostore the handler also makes) returns None so it is inert.

    The nudge handler reaches `_mcp_call` at most once per invocation (the
    `workflow_state_load`), so callers register one `.calls(...)` per expected
    invocation (tripwire pops from a FIFO queue) and assert that many times
    after the sandbox. Tests whose predicate short-circuits before any
    `_mcp_call` pass `expected_calls=0` and must NOT register a mock at all —
    registering an unused mock raises `UnusedMocksError` at teardown. The
    short-circuit paths are: empty/malformed session_id (rejected first) and
    an already-nudged session (the existing marker is checked BEFORE the DB
    read), so the debounced second prompt makes no `_mcp_call`.

    Returns the registered mock, or None when `expected_calls == 0`.
    """

    def fake_mcp_call(tool_name, arguments=None):
        if tool_name == "workflow_state_load":
            if state is None:
                return {"found": False, "state": {}}
            return {"found": True, "state": state}
        return None

    if expected_calls == 0:
        return None

    mock = tripwire.mock("spellbook_hook:_mcp_call")
    for _ in range(expected_calls):
        mock.calls(fake_mcp_call)
    return mock


def _isolate_marker_dir(monkeypatch, tmp_path: Path) -> None:
    """Point SPELLBOOK_CONFIG_DIR at a tmp dir so markers never touch ~."""
    monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path))


def _marker_path(tmp_path: Path, session_id: str) -> Path:
    return tmp_path / "runtime" / "develop-nudge" / f"{session_id}.nudged"


def _event(session_id: str = "sess-abc") -> dict:
    return {"prompt": "do the thing", "cwd": CWD, "session_id": session_id}


def test_nudge_fires_when_develop_active_past_phase0_no_ledger(monkeypatch, tmp_path):
    """develop active, past Phase 0, no ledger -> exact nudge message present."""
    _isolate_marker_dir(monkeypatch, tmp_path)
    mock = _stub_workflow_state({"active_skill": "develop", "skill_phase": "1"})

    with tripwire:
        outputs = spellbook_hook._handle_user_prompt_submit(_event())

    mock.assert_call(
        args=("workflow_state_load", {"project_path": CWD}), kwargs={}
    )
    assert outputs == [EXPECTED_NUDGE]


def test_no_nudge_during_phase0_wizard(monkeypatch, tmp_path):
    """IMP-1: skill_phase == "0" (wizard) with no ledger -> predicate FALSE -> no nudge."""
    _isolate_marker_dir(monkeypatch, tmp_path)
    mock = _stub_workflow_state({"active_skill": "develop", "skill_phase": "0"})

    with tripwire:
        outputs = spellbook_hook._handle_user_prompt_submit(_event())

    mock.assert_call(
        args=("workflow_state_load", {"project_path": CWD}), kwargs={}
    )
    assert outputs == []


def test_no_nudge_during_legitimate_long_phase(monkeypatch, tmp_path):
    """A populated ledger (condition 3 false) -> no nudge, regardless of phase age."""
    _isolate_marker_dir(monkeypatch, tmp_path)
    mock = _stub_workflow_state(
        {
            "active_skill": "develop",
            "skill_phase": "4",
            "develop_gate_ledger": {
                "current_phase": "4",
                "remaining_gates": "code review",
            },
        },
    )

    with tripwire:
        outputs = spellbook_hook._handle_user_prompt_submit(_event())

    mock.assert_call(
        args=("workflow_state_load", {"project_path": CWD}), kwargs={}
    )
    assert outputs == []


def test_no_nudge_when_develop_not_active(monkeypatch, tmp_path):
    """active_skill != "develop" (condition 1 false) -> no nudge."""
    _isolate_marker_dir(monkeypatch, tmp_path)
    mock = _stub_workflow_state({"active_skill": "debugging", "skill_phase": "1"})

    with tripwire:
        outputs = spellbook_hook._handle_user_prompt_submit(_event())

    mock.assert_call(
        args=("workflow_state_load", {"project_path": CWD}), kwargs={}
    )
    assert outputs == []


def test_no_nudge_when_no_workflow_state(monkeypatch, tmp_path):
    """No workflow_state at all (fail-open) -> no nudge, no crash."""
    _isolate_marker_dir(monkeypatch, tmp_path)
    mock = _stub_workflow_state(None)

    with tripwire:
        outputs = spellbook_hook._handle_user_prompt_submit(_event())

    mock.assert_call(
        args=("workflow_state_load", {"project_path": CWD}), kwargs={}
    )
    assert outputs == []


def test_no_nudge_when_session_id_missing(monkeypatch, tmp_path):
    """Empty session_id cannot be debounced safely -> skip nudge entirely."""
    _isolate_marker_dir(monkeypatch, tmp_path)
    # The nudge predicate short-circuits on the empty session_id BEFORE any
    # `_mcp_call`, so no mock is registered (an unused mock would raise
    # `UnusedMocksError`).
    _stub_workflow_state({"active_skill": "develop", "skill_phase": "2"}, expected_calls=0)

    event = {"prompt": "x", "cwd": CWD, "session_id": ""}
    outputs = spellbook_hook._handle_user_prompt_submit(event)

    assert outputs == []


def test_no_nudge_when_session_id_malformed(monkeypatch, tmp_path):
    """A session_id with path-traversal characters is rejected (no nudge, no
    file written outside the marker dir).

    The session_id becomes part of a filename; an unvalidated value like
    "../../evil" would escape the marker directory. The handler validates the
    session_id against the same constraint used elsewhere in the hook and
    skips the nudge for anything that does not match.
    """
    _isolate_marker_dir(monkeypatch, tmp_path)
    # The nudge predicate rejects the malformed session_id BEFORE any
    # `_mcp_call`, so no mock is registered.
    _stub_workflow_state({"active_skill": "develop", "skill_phase": "2"}, expected_calls=0)

    event = {"prompt": "x", "cwd": CWD, "session_id": "../../evil"}
    outputs = spellbook_hook._handle_user_prompt_submit(event)

    assert outputs == []
    # No marker file was created anywhere under the isolated config dir.
    assert list(tmp_path.rglob("*.nudged")) == []


def test_nudge_debounced_via_marker_file(monkeypatch, tmp_path):
    """IMP-2: two separate (subprocess-simulating) invocations with the same
    session_id and unchanged predicate-true state -> message present on the
    first, ABSENT on the second; the marker FILE exists after the first.

    Each call passes a FRESH `data` dict and the handler holds no module-level
    "already nudged" state, so the two calls model two per-event subprocesses.
    The only state surviving between them is the on-disk marker file: if the
    debounce were an in-process flag, BOTH calls would emit (the flag would
    reset per process) and this test would fail.

    The already-nudged short-circuit is checked BEFORE the workflow_state_load
    DB read, so the SECOND invocation returns without calling `_mcp_call` at
    all. Only the FIRST invocation reaches `workflow_state_load`, so exactly
    ONE `_mcp_call` is registered (registering a second, unused mock would
    raise `UnusedMocksError` at teardown — which independently proves the
    second call never hits the DB).
    """
    _isolate_marker_dir(monkeypatch, tmp_path)
    # Only the FIRST invocation reaches `_mcp_call` (workflow_state_load); the
    # second short-circuits on the existing marker before the DB read.
    mock = _stub_workflow_state(
        {"active_skill": "develop", "skill_phase": "1"}, expected_calls=1
    )

    session_id = "sess-debounce"
    marker = _marker_path(tmp_path, session_id)
    assert not marker.exists()

    with tripwire:
        first = spellbook_hook._handle_user_prompt_submit(_event(session_id))
        assert first == [EXPECTED_NUDGE]
        assert marker.exists()

        second = spellbook_hook._handle_user_prompt_submit(_event(session_id))
        assert second == []

    # Exactly one workflow_state_load (the first invocation). The single
    # registered mock being fully consumed (no UnusedMocksError) confirms the
    # second invocation never reached the DB read.
    mock.assert_call(
        args=("workflow_state_load", {"project_path": CWD}), kwargs={}
    )


def test_nudge_marker_cleanup_on_session_start(monkeypatch, tmp_path):
    """Task 7: SessionStart removes the session's marker so a later prompt in
    that same session can nudge again.

    No SessionEnd handler exists (verified) — cleanup hooks into SessionStart.
    A non-compact SessionStart with no orphan returns None; the side effect
    under test is the marker removal.
    """
    _isolate_marker_dir(monkeypatch, tmp_path)
    # SessionStart's orphan backstop calls into agent2agent; stub it inert.
    mock_orphan = tripwire.mock("spellbook_hook:_agent2agent_check_orphaned_chain")
    mock_orphan.returns(None)

    session_id = "sess-cleanup"
    marker = _marker_path(tmp_path, session_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    assert marker.exists()

    with tripwire:
        result = spellbook_hook._handle_session_start(
            {"source": "startup", "cwd": CWD, "session_id": session_id}
        )

    mock_orphan.assert_call(
        args=({"source": "startup", "cwd": CWD, "session_id": session_id},),
        kwargs={},
    )
    assert result is None
    assert not marker.exists()


def test_nudge_marker_cleanup_prunes_stale_markers(monkeypatch, tmp_path):
    """SessionStart prunes *.nudged markers older than one day, leaving fresh ones.

    Guards against unbounded accumulation in the marker dir across sessions.
    """
    _isolate_marker_dir(monkeypatch, tmp_path)
    mock_orphan = tripwire.mock("spellbook_hook:_agent2agent_check_orphaned_chain")
    mock_orphan.returns(None)

    marker_dir = tmp_path / "runtime" / "develop-nudge"
    marker_dir.mkdir(parents=True, exist_ok=True)

    stale = marker_dir / "old-session.nudged"
    fresh = marker_dir / "recent-session.nudged"
    stale.touch()
    fresh.touch()
    # Backdate the stale marker to 2 days ago.
    two_days_ago = time.time() - (2 * 86400)
    os.utime(stale, (two_days_ago, two_days_ago))

    with tripwire:
        spellbook_hook._handle_session_start(
            {"source": "startup", "cwd": CWD, "session_id": "current-session"}
        )

    mock_orphan.assert_call(
        args=({"source": "startup", "cwd": CWD, "session_id": "current-session"},),
        kwargs={},
    )
    assert not stale.exists()
    assert fresh.exists()
