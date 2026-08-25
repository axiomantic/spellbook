"""Tests for the autonomous-mode Stop hook in ``hooks/spellbook_hook.py``.

The hook is a gate on the operator's turn, so the tests below drive
``dispatch("Stop", ...)`` with constructed stdin and assert the returned
JSON -- the exact artifact the harness consumes. Real records are written
through ``spellbook.core.autonomous`` into a redirected HOME; nothing patches the
internals of the hook or of the state module, because a gate proven only
against stubs of itself is proven against nothing.

The block case is asserted on the CONTENT of the reason (escape phrase,
philosophy id, the question put to the model), not merely on
``decision == "block"``. The reason IS the mechanism here -- the hook decides
nothing about the work and only hands the question back -- so a reason that
lost the escape phrase or the instruction to raise a blocker through
AskUserQuestion is a broken gate that a decision-field assertion still
passes.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
import tripwire

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

from spellbook.core import autonomous  # noqa: E402
from spellbook.core.paths import get_data_dir  # noqa: E402

SID = "sess-abc_123.def"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect the only input that can decide the hook's verdict.

    The autonomous record is now the whole input, so the home variables are
    the whole isolation. The assertion below is the part that matters: a
    redirection that silently did not take effect would run every test here
    against the developer's real records.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert tmp_path in get_data_dir().parents, (
        f"data dir {get_data_dir()} is not under {tmp_path}; "
        "the redirection did not take effect"
    )
    return tmp_path


def _record(session_id=SID, **overrides):
    fields = dict(
        mode="fully",
        philosophy="hostile-review",
        goal="ship the stop hook",
        set_at="2026-08-24T00:00:00Z",
    )
    fields.update(overrides)
    assert autonomous.write_autonomous_record(session_id, **fields) is True


def _stdin(**overrides):
    data = {
        "hook_event_name": "Stop",
        "session_id": SID,
        # The harness sends this on every Stop; the handler ignores it. Kept
        # so the constructed stdin keeps the shape the hook is really given.
        "transcript_path": "",
        "stop_hook_active": False,
    }
    data.update(overrides)
    return data


def _dispatch(data):
    return spellbook_hook.dispatch("Stop", "", data)


def _decision(data):
    raw = _dispatch(data)
    return None if raw is None else json.loads(raw)


# ---- row 3: the block ------------------------------------------------------


class TestBlocks:
    def test_an_autonomous_session_is_blocked_from_ending_a_turn(self, tmp_path):
        _record()
        result = _decision(_stdin())
        assert result is not None
        assert result["decision"] == "block"

    def test_block_reason_restates_the_escape_phrase(self, tmp_path):
        _record()
        reason = _decision(_stdin())["reason"]
        for phrase in spellbook_hook.AUTONOMOUS_ESCAPE_PHRASES:
            assert phrase in reason
        assert "stop autonomous" in reason

    def test_block_reason_names_the_active_philosophy(self, tmp_path):
        _record(philosophy="minimal-diff")
        reason = _decision(_stdin())["reason"]
        assert "minimal-diff" in reason

    def test_block_reason_puts_the_three_questions_to_the_model(self, tmp_path):
        """The reason IS the mechanism, so its substance is asserted.

        The hook decides nothing about the work: it refuses once and asks.
        A reason that stated the refusal without naming what would justify
        ending the turn -- done, paused, or genuinely blocked -- would leave
        the model with a closed door and no handle, and a decision-field
        assertion would not notice.
        """
        _record()
        reason = _decision(_stdin())["reason"]
        assert "Autonomous mode is ACTIVE" in reason
        assert "DONE" in reason
        assert "PAUSE" in reason
        assert "GENUINE BLOCKER" in reason
        assert "AskUserQuestion" in reason

    def test_block_reason_carries_the_recorded_goal(self, tmp_path):
        _record(goal="ship the valve")
        assert "ship the valve" in _decision(_stdin())["reason"]

    def test_block_increments_blocked_stops_once(self, tmp_path):
        _record()
        data = _stdin()
        _decision(data)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 1
        _decision(data)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 2


# ---- rows 1-2: every ALLOW path -------------------------------------------


class TestAllows:
    def test_bad_session_id_allows_even_when_stop_hook_active(self, tmp_path):
        """A bad session id allows even under the post-block flag."""
        assert (
            _decision(
                _stdin(
                    stop_hook_active=True,
                    session_id="../../etc/passwd",
                )
            )
            is None
        )

    def test_row2_no_record_allows(self, tmp_path):
        assert _decision(_stdin()) is None

    def test_row2_record_for_a_different_session_allows(self, tmp_path):
        _record(session_id="some-other-session")
        assert _decision(_stdin()) is None


# ---- fail-open: every unknown resolves to ALLOW ---------------------------


class TestFailsOpen:
    def test_invalid_session_id_allows(self, tmp_path):
        _record()
        assert (
            _decision(
                _stdin(session_id="../../etc/passwd")
            )
            is None
        )

    def test_missing_session_id_allows(self, tmp_path):
        _record()
        data = _stdin()
        del data["session_id"]
        assert _decision(data) is None

    def test_malformed_record_allows(self, tmp_path):
        _record()
        path = get_data_dir() / "autonomous" / f"{SID}.json"
        path.write_text("{not json", encoding="utf-8")
        assert _decision(_stdin()) is None

    def test_record_with_wrong_shape_allows(self, tmp_path):
        _record()
        path = get_data_dir() / "autonomous" / f"{SID}.json"
        path.write_text(json.dumps({"mode": "sideways"}), encoding="utf-8")
        assert _decision(_stdin()) is None


# ---- the dispatch seam itself ---------------------------------------------


class TestDispatchShape:
    def test_returns_json_text_not_a_list(self, tmp_path):
        _record()
        raw = _dispatch(_stdin())
        assert isinstance(raw, str)
        assert json.loads(raw)["decision"] == "block"

    def test_other_events_are_unaffected(self):
        assert spellbook_hook.dispatch("NotAnEvent", "", _stdin()) is None


# ---- the isolation boundary itself ----------------------------------------


# ---- Task 4: the escape phrase --------------------------------------------


def _prompt_stdin(prompt, session_id=SID):
    return {
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "prompt": prompt,
    }


def _submit(prompt, session_id=SID):
    return spellbook_hook.dispatch(
        "UserPromptSubmit", "", _prompt_stdin(prompt, session_id)
    )


class TestEscapePhrase:
    def test_each_shared_phrase_clears_the_record(self, tmp_path):
        for phrase in spellbook_hook.AUTONOMOUS_ESCAPE_PHRASES:
            _record()
            assert autonomous.read_autonomous_record(SID) is not None
            _submit(f"ok, {phrase} now please")
            assert autonomous.read_autonomous_record(SID) is None

    def test_match_is_case_insensitive(self, tmp_path):
        _record()
        _submit("STOP AUTONOMOUS")
        assert autonomous.read_autonomous_record(SID) is None

    def test_match_is_a_substring_of_a_longer_prompt(self, tmp_path):
        _record()
        _submit("before text exit autonomous mode and then keep reading")
        assert autonomous.read_autonomous_record(SID) is None

    def test_an_ordinary_prompt_leaves_the_record_alone(self, tmp_path):
        _record()
        _submit("keep going, finish the feature")
        assert autonomous.read_autonomous_record(SID) is not None

    def test_a_near_miss_does_not_clear(self, tmp_path):
        """No synonyms, no inference -- only the literal phrases."""
        _record()
        for near in ("halt autonomous", "stop being autonomous", "autonomous stop"):
            _submit(near)
            assert autonomous.read_autonomous_record(SID) is not None

    def test_confirmation_is_injected_when_a_record_was_cleared(self, tmp_path):
        _record()
        out = _submit("stop autonomous")
        assert out is not None
        assert "CLEARED" in out

    def test_says_nothing_when_no_record_exists(self, tmp_path):
        assert _submit("stop autonomous") is None

    def test_a_record_for_another_session_is_untouched(self, tmp_path):
        _record(session_id="other-session")
        _submit("stop autonomous", session_id=SID)
        assert autonomous.read_autonomous_record("other-session") is not None

    def test_invalid_session_id_does_not_raise(self, tmp_path):
        _record()
        assert _submit("stop autonomous", session_id="../../etc/passwd") is None
        assert autonomous.read_autonomous_record(SID) is not None

    def test_non_string_prompt_does_not_raise(self, tmp_path):
        _record()
        assert (
            spellbook_hook.dispatch(
                "UserPromptSubmit", "", {"session_id": SID, "prompt": {"a": 1}}
            )
            is None
        )
        assert autonomous.read_autonomous_record(SID) is not None

    def test_missing_prompt_field_does_not_raise(self, tmp_path):
        _record()
        assert spellbook_hook.dispatch("UserPromptSubmit", "", {"session_id": SID}) is None
        assert autonomous.read_autonomous_record(SID) is not None


class TestEscapeOrdering:
    def test_escape_then_stop_in_the_same_turn_allows(self, tmp_path):
        """The load-bearing ordering: the clear lands on the prompt that
        carries the phrase, so THIS turn's Stop already sees no record."""
        _record()
        assert _decision(_stdin())["decision"] == "block"

        _record()
        _submit("stop autonomous")
        assert _decision(_stdin()) is None


# The escape handler shares ``_handle_user_prompt_submit`` with the
# agent2agent notify path. Every test below asserts the notify mock RECEIVED
# the exact stdin payload -- proving the notify path ran with the untouched
# prompt, not merely that a string reached the output.
_ESCAPE_BOOM = RuntimeError("state dir on fire")


class TestEscapeDoesNotDisturbAgent2Agent:
    def test_a2a_notify_still_runs_on_an_ordinary_prompt(self, tmp_path):
        notify = tripwire.mock("spellbook_hook:_agent2agent_notify_for_prompt")
        notify.returns("a2a-hint")

        with tripwire:
            out = _submit("just a prompt")

        # tripwire records ``returned`` only for spies, so the configured
        # return is pinned by the output assertion below instead.
        notify.assert_call(args=(_prompt_stdin("just a prompt"),), kwargs={})
        assert out is not None
        assert "a2a-hint" in out

    def test_a2a_notify_still_runs_on_an_escape_prompt(self, tmp_path):
        _record()
        notify = tripwire.mock("spellbook_hook:_agent2agent_notify_for_prompt")
        notify.returns("a2a-hint")

        with tripwire:
            out = _submit("stop autonomous")

        notify.assert_call(args=(_prompt_stdin("stop autonomous"),), kwargs={})
        assert "a2a-hint" in out
        assert "CLEARED" in out

    def test_a_failing_escape_does_not_stop_the_a2a_hint(self, tmp_path):
        """The fail-open contract: the escape raises, the hint still ships.

        ``_log_hook_error`` is mocked because the real one POSTs to the daemon,
        which the sandbox forbids; asserting it also pins that the failure was
        reported rather than swallowed.
        """
        read = tripwire.mock("spellbook.core.autonomous:read_autonomous_record")
        read.raises(_ESCAPE_BOOM)
        logged = tripwire.mock("spellbook_hook:_log_hook_error")
        logged.returns(None)
        notify = tripwire.mock("spellbook_hook:_agent2agent_notify_for_prompt")
        notify.returns("a2a-hint")

        with tripwire:
            out = _submit("stop autonomous")

        read.assert_call(args=(SID,), kwargs={}, raised=_ESCAPE_BOOM)
        logged.assert_call(
            args=("autonomous_escape", "UserPromptSubmit", _ESCAPE_BOOM), kwargs={}
        )
        notify.assert_call(args=(_prompt_stdin("stop autonomous"),), kwargs={})
        assert out is not None
        assert "a2a-hint" in out


# ---- the rolling-window valve ---------------------------------------------
#
# ``stop_hook_active`` is set by the harness on the stop FOLLOWING a block.
# Treating it as an unconditional ALLOW makes the hook block at most once per
# session, which is the one case the feature exists for. These tests pin the
# replacement: blocking PERSISTS, and the only thing that opens the valve is
# evidence of thrashing -- three blocks inside a 60-second window.
#
# Time is controlled by SEEDING the recorded block timestamps at explicit
# offsets from the current clock, never by sleeping. A sleeping test would
# have to sleep for a real minute to cross the window, which is slow and
# flaky on a loaded machine; seeding makes the elapsed-time question exact
# and the test instantaneous.


def _seed_block_times(offsets, session_id=SID):
    """Set the record's recorded block timestamps to ``now + offset`` each.

    Offsets are negative seconds: ``-5`` is "a block five seconds ago".
    Written straight into the record file so the seed does not depend on the
    writer API under test.
    """
    path = autonomous._record_path(session_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    now = time.time()
    payload["block_times"] = [now + offset for offset in offsets]
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestBlockingPersists:
    def test_blocks_again_when_stop_hook_active(self, tmp_path):
        """The whole point: a second turn-end after a block still blocks.

        ``stop_hook_active`` is true on exactly this stop. If it is read as
        an unconditional allow, the gate is a one-shot and the session ends
        on the very next turn.
        """
        _record()
        first = _decision(_stdin())
        assert first["decision"] == "block"

        second = _decision(
            _stdin(stop_hook_active=True)
        )
        assert second is not None, "the hook allowed the stop that follows a block"
        assert second["decision"] == "block"


class TestThrashValve:
    def test_third_stop_inside_the_window_still_blocks(self, tmp_path):
        """Two recorded blocks are not yet evidence of thrashing."""
        _record()
        for _ in range(3):
            decision = _decision(
                _stdin(stop_hook_active=True)
            )
            assert decision["decision"] == "block"

    def test_fourth_stop_allows_after_three_blocks_inside_the_window(self, tmp_path):
        """Three blocks inside 60s is thrashing; the next stop is allowed.

        The valve counts blocks already ISSUED, so the fourth stop is the
        first one it can open on: there is no way to have three recorded
        blocks without the third having been issued.
        """
        _record()
        for _ in range(3):
            assert (
                _decision(_stdin(stop_hook_active=True))[
                    "decision"
                ]
                == "block"
            )
        assert (
            _decision(_stdin(stop_hook_active=True))
            is None
        )

    def test_three_blocks_spread_beyond_the_window_keep_blocking(self, tmp_path):
        """The same three blocks, spread over real work, are not thrashing."""
        _record()
        _seed_block_times([-300.0, -180.0, -61.0])
        decision = _decision(
            _stdin(stop_hook_active=True)
        )
        assert decision["decision"] == "block"

    def test_the_window_edge_is_inclusive(self, tmp_path):
        """Exactly 60s apart counts as inside the window."""
        _record()
        _seed_block_times([-59.5, -30.0, -1.0])
        assert (
            _decision(_stdin(stop_hook_active=True))
            is None
        )

    def test_only_the_most_recent_timestamps_are_kept(self, tmp_path):
        """The stored window is bounded; it cannot grow with the session."""
        _record()
        for _ in range(3):
            _decision(_stdin(stop_hook_active=True))
        record = autonomous.read_autonomous_record(SID)
        assert record["blocked_stops"] == 3
        assert len(record["block_times"]) == autonomous.BLOCK_WINDOW_LIMIT

    def test_malformed_valve_state_allows(self, tmp_path):
        """Broken bookkeeping must not trap the session."""
        _record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["block_times"] = "not a list"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert _decision(_stdin()) is None


class TestOnlyBlocksAreRecorded:
    """An ALLOW must leave the block bookkeeping untouched.

    Nothing above this class asserts what an allowed stop does to the
    record. If ``record_blocked_stop`` were called before the allow rows
    instead of after them, every decision test would still pass while the
    valve's window filled up on turns the hook never refused -- the valve
    would then open on a session that was never held, and the feature would
    go inert exactly the way the ``stop_hook_active`` row did.
    """

    def _bookkeeping(self):
        record = autonomous.read_autonomous_record(SID)
        return record["blocked_stops"], autonomous.recent_block_times(record)


    def test_a_fail_open_allow_records_nothing(self, tmp_path):
        """The fail-open rows must not stamp the window either.

        Retargeted from an unreadable-transcript allow when the handler
        stopped reading transcripts. The behavior it guards is unchanged and
        is not asserted anywhere else: a row that ALLOWS because it could not
        establish the facts must leave the valve's bookkeeping alone, or the
        window fills on turns the hook never refused and the valve opens on a
        session that was never held.
        """
        _record()
        assert _decision(_stdin(session_id="../../etc/passwd")) is None
        assert self._bookkeeping() == (0, [])


    def test_the_valve_opening_records_nothing(self, tmp_path):
        """The stop the valve releases must not extend the window itself.

        A valve that stamped the stop it allowed would keep its own window
        full and latch open for the rest of the session.
        """
        _record()
        _seed_block_times([-3.0, -2.0, -1.0])
        before = self._bookkeeping()
        assert _decision(_stdin()) is None
        after = self._bookkeeping()
        assert after[0] == before[0]
        assert after[1] == before[1]


class TestTheValveIsNotALatch:
    def test_blocking_resumes_once_the_window_goes_stale(self, tmp_path):
        """One released stop is not a permanent exit from autonomous mode.

        Drives the valve open on a fresh window, then ages the same three
        blocks past the window and re-drives the hook. Nothing else in this
        file re-blocks AFTER an allow, so a valve implemented as a one-way
        latch would look correct.
        """
        _record()
        _seed_block_times([-3.0, -2.0, -1.0])
        assert _decision(_stdin()) is None

        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window + 30.0), -(window + 20.0), -(window + 10.0)])
        assert _decision(_stdin())["decision"] == "block"

    def test_two_blocks_inside_the_window_do_not_open_it(self, tmp_path):
        """The limit is a count, not "any recent block at all"."""
        _record()
        _seed_block_times([-2.0, -1.0])
        assert _decision(_stdin())["decision"] == "block"


class TestWindowBoundaryAtTheHook:
    """The window boundary, driven through ``dispatch`` and stated in terms
    of ``BLOCK_WINDOW_SECONDS`` so a change to the constant moves both sides
    together. The existing ``test_the_window_edge_is_inclusive`` seeds
    ``-59.5`` and so pins nothing about the edge itself; these bracket it
    from both directions.
    """

    def test_three_blocks_just_inside_the_window_allow(self, tmp_path):
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window - 1.0), -(window - 2.0), -(window - 3.0)])
        assert _decision(_stdin()) is None

    def test_three_blocks_just_outside_the_window_block(self, tmp_path):
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window + 3.0), -(window + 2.0), -(window + 1.0)])
        assert _decision(_stdin())["decision"] == "block"

    def test_the_oldest_of_three_decides_not_the_newest(self, tmp_path):
        """Two blocks moments ago plus one stale block is not thrashing.

        A valve reading the MOST RECENT timestamp instead of the
        ``BLOCK_WINDOW_LIMIT``-th most recent would open here.
        """
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window * 10), -2.0, -1.0])
        assert _decision(_stdin())["decision"] == "block"


class TestStopHookActiveIsInert:
    """``stop_hook_active`` must not change ANY row's verdict.

    The reversed row is pinned above for the block case. These pin that the
    flag is not consulted anywhere else either -- a reintroduced guard placed
    on a different row would otherwise be invisible.
    """

    @pytest.mark.parametrize("flag", [False, True])
    def test_the_block_row_is_identical_either_way(self, tmp_path, flag):
        _record()
        decision = _decision(
            _stdin(stop_hook_active=flag)
        )
        assert decision["decision"] == "block"

    @pytest.mark.parametrize("flag", [False, True])
    def test_the_valve_row_is_identical_either_way(self, tmp_path, flag):
        _record()
        _seed_block_times([-3.0, -2.0, -1.0])
        assert (
            _decision(_stdin(stop_hook_active=flag))
            is None
        )

    def test_a_missing_flag_blocks_exactly_as_a_present_one(self, tmp_path):
        _record()
        data = _stdin()
        del data["stop_hook_active"]
        assert _decision(data)["decision"] == "block"
