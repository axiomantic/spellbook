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
from dirty_equals import IsInstance

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


def _expected_reason(mode="fully", philosophy="hostile-review", goal="ship the stop hook"):
    """The complete block message, constructed independently of the hook.

    ``patterns/assertion-quality-standard.md`` requires the whole expected
    value, not a sample of it. The reason IS the mechanism here -- the hook
    decides nothing about the work and only hands the question back -- so a
    substring check passes against a message that has lost the escape
    phrase, the philosophy, or the instruction to raise a blocker through
    AskUserQuestion. The escape phrases are read from the shared tuple, the
    one value this file must not duplicate: a copy here would drift from
    what the hook prints and the drift would be invisible.
    """
    phrases = " / ".join(
        f'"{p}"' for p in spellbook_hook.AUTONOMOUS_ESCAPE_PHRASES
    )
    return (
        "Autonomous mode is ACTIVE for this session "
        f"(mode: {mode}, philosophy: {philosophy}).\n"
        "This turn-end is refused. Before ending a turn, answer this: are you "
        "DONE with the whole project goal, were you asked to PAUSE by the "
        "operator, or do you have a GENUINE BLOCKER?\n"
        "If you have a genuine blocker, you MUST use the AskUserQuestion tool "
        "to ask the operator how to continue -- do not end the turn on it.\n"
        "If none of the three holds, you are not finished. A long session, a "
        "finished list item, a returned subagent result, and a phase boundary "
        "are none of them. Keep working.\n"
        f"Goal: {goal}\n"
        f"To leave autonomous mode, the OPERATOR types one of: {phrases}. "
        "Nothing you do ends it."
    )


# ---- row 3: the block ------------------------------------------------------


class TestBlocks:
    def test_an_autonomous_session_is_blocked_from_ending_a_turn(self, tmp_path):
        _record()
        result = _decision(_stdin())
        assert result is not None
        assert result["decision"] == "block"

    def test_block_reason_is_exactly_the_message_the_hook_owes(self, tmp_path):
        """The whole reason, as a value.

        The hook decides nothing about the work: it refuses once and asks.
        A reason that stated the refusal without naming what would justify
        ending the turn -- done, paused, or genuinely blocked -- or that
        dropped the escape phrase would leave the model and the operator
        with a closed door and no handle.
        """
        _record()
        assert _decision(_stdin())["reason"] == _expected_reason()

    def test_block_reason_names_the_ACTIVE_philosophy_and_goal(self, tmp_path):
        """Both fields are read from the record, not from a default."""
        _record(philosophy="minimal-diff", goal="ship the valve")
        assert _decision(_stdin())["reason"] == _expected_reason(
            philosophy="minimal-diff", goal="ship the valve"
        )

    def test_each_block_increments_blocked_stops_by_one(self, tmp_path):
        _record()
        data = _stdin()
        _decision(data)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 1
        _decision(data)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 2


# ---- rows 1-2: every ALLOW path -------------------------------------------


class TestAllows:
    def test_row1_no_record_allows(self, tmp_path):
        assert _decision(_stdin()) is None

    def test_row1_record_for_a_different_session_allows(self, tmp_path):
        _record(session_id="some-other-session")
        assert _decision(_stdin()) is None


# ---- fail-open: every unknown resolves to ALLOW ---------------------------


class TestFailsOpen:
    def test_invalid_session_id_allows(self, tmp_path):
        """A record EXISTS under the valid id, so the allow can only come
        from the session-id guard rather than from the no-record row."""
        _record()
        assert _decision(_stdin(session_id="../../etc/passwd")) is None

    def test_invalid_session_id_allows_even_under_the_post_block_flag(
        self, tmp_path
    ):
        _record()
        assert (
            _decision(
                _stdin(stop_hook_active=True, session_id="../../etc/passwd")
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
        assert _submit("stop autonomous") == (
            "Autonomous mode CLEARED for this session by operator escape "
            "phrase. The Stop hook no longer blocks the end of a turn."
        )

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
        """One short of the limit is not yet evidence of thrashing."""
        _record()
        for _ in range(autonomous.BLOCK_WINDOW_LIMIT):
            decision = _decision(
                _stdin(stop_hook_active=True)
            )
            assert decision["decision"] == "block"

    def test_the_stop_after_the_limit_allows(self, tmp_path):
        """``BLOCK_WINDOW_LIMIT`` blocks inside the window is thrashing.

        The valve counts blocks already ISSUED, so the stop AFTER the limit
        is the first one it can open on: there is no way to hold that many
        recorded blocks without the last having been issued.
        """
        _record()
        for _ in range(autonomous.BLOCK_WINDOW_LIMIT):
            assert (
                _decision(_stdin(stop_hook_active=True))["decision"] == "block"
            )
        assert (
            _decision(_stdin(stop_hook_active=True))
            is None
        )

    def test_three_blocks_spread_beyond_the_window_keep_blocking(self, tmp_path):
        """The same blocks, spread over real work, are not thrashing."""
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window * 5), -(window * 3), -(window + 1.0)])
        decision = _decision(
            _stdin(stop_hook_active=True)
        )
        assert decision["decision"] == "block"

    def test_three_blocks_well_inside_the_window_allow(self, tmp_path):
        """The edge itself is pinned in ``test_core_autonomous.py``; this
        drives an unambiguously-inside window through ``dispatch``."""
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window / 2), -(window / 4), -1.0])
        assert (
            _decision(_stdin(stop_hook_active=True))
            is None
        )

    def test_only_the_most_recent_timestamps_are_kept(self, tmp_path):
        """The stored window is bounded; it cannot grow with the session."""
        _record()
        for _ in range(autonomous.BLOCK_WINDOW_LIMIT):
            _decision(_stdin(stop_hook_active=True))
        record = autonomous.read_autonomous_record(SID)
        assert record["blocked_stops"] == autonomous.BLOCK_WINDOW_LIMIT
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


# ---- row 3: a block that cannot be accounted for is not issued ------------
#
# The fault below is a REAL read-only directory, not a mock. The trap this
# guards against was reproduced exactly this way: with the state directory
# unwritable, reads succeed and writes fail, so the record still says
# "autonomous" while no block can ever be recorded. Mocking the writer would
# prove the branch and not the condition.


def _require_permission_bits():
    if os.name != "posix":
        pytest.skip("POSIX permission bits only")
    if os.geteuid() == 0:
        pytest.skip("root ignores permission bits; the fault would not fire")


@pytest.fixture
def readonly_autonomous_dir(tmp_path):
    """Make the records directory readable but not writable.

    Yields a callable that locks the directory down, so a test can write its
    record first and take the fault only on the write that follows.
    """
    _require_permission_bits()
    directory = get_data_dir() / "autonomous"
    directory.mkdir(parents=True, exist_ok=True)

    def lock_it():
        directory.chmod(0o500)  # r-x: reads succeed, every write fails
        return directory

    try:
        yield lock_it
    finally:
        directory.chmod(0o700)


class TestAnUnrecordableBlockIsNotIssued:
    def test_a_stop_is_allowed_when_the_block_cannot_be_recorded(
        self, tmp_path, readonly_autonomous_dir
    ):
        """The trap, at one stop: refusing here accumulates nothing.

        The valve opens on blocks that were RECORDED. A block issued when
        the record cannot be written can never contribute to opening it, so
        it must not be issued at all.
        """
        _record()
        readonly_autonomous_dir()
        assert _decision(_stdin()) is None

    def test_the_session_is_not_trapped_across_repeated_stops(
        self, tmp_path, readonly_autonomous_dir
    ):
        """The trap as reproduced: consecutive stops against a read-only dir.

        With the harness block cap disabled, the valve is the only bound on
        the loop. If any of these blocks, every later one blocks too and the
        session cannot end by any path the model controls.
        """
        _record()
        readonly_autonomous_dir()
        verdicts = [
            _decision(_stdin(stop_hook_active=i > 0))
            for i in range(6)
        ]
        assert verdicts == [None] * 6

    def test_the_record_still_says_autonomous_during_the_fault(
        self, tmp_path, readonly_autonomous_dir
    ):
        """Pins that the allow comes from row 3, not from a vanished record.

        Without this, a fault that made the record UNREADABLE would satisfy
        the two tests above through row 1 and leave row 3 unproven.
        """
        _record()
        readonly_autonomous_dir()
        record = autonomous.read_autonomous_record(SID)
        assert record is not None
        assert record["blocked_stops"] == 0
        assert _decision(_stdin()) is None

    def test_blocking_resumes_once_the_directory_is_writable_again(
        self, tmp_path, readonly_autonomous_dir
    ):
        """Row 3 is a response to the fault, not an exit from autonomous mode."""
        _record()
        directory = readonly_autonomous_dir()
        assert _decision(_stdin()) is None
        directory.chmod(0o700)
        assert _decision(_stdin())["decision"] == "block"


class TestTheEscapeHatchDoesNotClaimWhatItDidNotDo:
    def test_a_failed_clear_leaves_the_record_and_says_so(
        self, tmp_path, readonly_autonomous_dir
    ):
        """The operator's only exit must never report a success it did not get."""
        _record()
        readonly_autonomous_dir()
        out = _submit("stop autonomous")
        assert autonomous.read_autonomous_record(SID) is not None
        assert out is not None
        assert "COULD NOT BE CLEARED" in out
        assert "no longer blocks the end of a turn" not in out

    def test_a_failed_clear_names_what_the_operator_can_do(
        self, tmp_path, readonly_autonomous_dir
    ):
        """A failure notice with nothing actionable in it is not a notice."""
        _record()
        readonly_autonomous_dir()
        out = _submit("stop autonomous")
        assert str(autonomous._record_path(SID)) in out
        assert "end this session" in out

    def test_the_hook_keeps_refusing_after_a_failed_clear(
        self, tmp_path, readonly_autonomous_dir
    ):
        """The claim the notice makes about the hook is asserted, not assumed."""
        _record()
        directory = readonly_autonomous_dir()
        _submit("stop autonomous")
        directory.chmod(0o700)
        assert _decision(_stdin())["decision"] == "block"

    def test_the_success_line_is_emitted_only_once_the_record_is_gone(
        self, tmp_path
    ):
        """The confirmation is gated on the ARTIFACT, not on the call."""
        _record()
        out = _submit("stop autonomous")
        assert autonomous.read_autonomous_record(SID) is None
        assert autonomous._record_path(SID).exists() is False
        assert "COULD NOT BE CLEARED" not in out
        assert "Autonomous mode CLEARED" in out


# ---- the fail-open safety nets, each observed to fire ---------------------
#
# These three branches are what stop this feature trapping a session, and
# until now none had ever been seen to run. Each is driven by a PLANTED
# exception and asserted to ALLOW.
_STOP_BOOM = RuntimeError("valve bookkeeping on fire")


class TestFailOpenSafetyNets:
    def test_a_raising_valve_allows_the_stop(self, tmp_path):
        """The valve is the only bound on the block loop; a jam must release."""
        _record()
        valve = tripwire.mock("spellbook.core.autonomous:thrash_valve_open")
        valve.raises(_STOP_BOOM)

        with tripwire:
            decision = _decision(_stdin())

        valve.assert_call(
            # ``now`` is the wall clock the handler reads at call time.
            args=(autonomous.read_autonomous_record(SID),),
            kwargs={"now": IsInstance(float)},
            raised=_STOP_BOOM,
        )
        assert decision is None

    def test_a_raising_valve_records_no_block(self, tmp_path):
        """The released stop must not stamp the window it just failed to read."""
        _record()
        valve = tripwire.mock("spellbook.core.autonomous:thrash_valve_open")
        valve.raises(_STOP_BOOM)

        with tripwire:
            _decision(_stdin())

        valve.assert_call(
            args=(autonomous.read_autonomous_record(SID),),
            kwargs={"now": IsInstance(float)},
            raised=_STOP_BOOM,
        )
        record = autonomous.read_autonomous_record(SID)
        assert record["blocked_stops"] == 0
        assert autonomous.recent_block_times(record) == []

    def test_an_unimportable_state_module_allows_the_stop(self, tmp_path):
        """A partial checkout must not gate the operator's turn."""
        _record()
        module = tripwire.mock("spellbook_hook:_autonomous_module")
        module.returns(None)

        with tripwire:
            decision = _decision(_stdin())

        module.assert_call(args=(), kwargs={})
        assert decision is None

    def test_a_raising_stop_handler_allows_and_is_reported(self, tmp_path):
        """dispatch's own net: the failure is logged, and the stop allowed.

        ``_log_hook_error`` is mocked because the real one POSTs to the
        daemon, which the sandbox forbids; asserting it also pins that the
        failure was reported rather than swallowed.
        """
        _record()
        handler = tripwire.mock("spellbook_hook:_handle_stop")
        handler.raises(_STOP_BOOM)
        logged = tripwire.mock("spellbook_hook:_log_hook_error")
        logged.returns(None)

        with tripwire:
            raw = _dispatch(_stdin())

        handler.assert_call(args=(_stdin(),), kwargs={}, raised=_STOP_BOOM)
        logged.assert_call(args=("handle_stop", "Stop", _STOP_BOOM), kwargs={})
        assert raw is None
