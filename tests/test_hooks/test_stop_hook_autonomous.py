"""Tests for the autonomous-mode Stop hook in ``hooks/spellbook_hook.py``.

The hook is a gate on the operator's turn, so the tests below drive
``dispatch("Stop", ...)`` with constructed stdin and assert the returned
JSON -- the exact artifact the harness consumes. Real records are written
through ``spellbook.core.autonomous`` into a redirected HOME, and real
transcript files are written to disk; nothing patches the internals of the
hook or of the state module, because a gate proven only against stubs of
itself is proven against nothing.

The block case is asserted on the CONTENT of the reason (escape phrase,
philosophy id), not merely on ``decision == "block"``. A block message
missing the escape phrase makes the trap undiscoverable, and that defect is
invisible to a test that only reads the decision field.
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
    """Redirect every input that can decide the hook's verdict.

    The home variables redirect the autonomous record. ``SPELLBOOK_DEV_DIR``
    is the other one, and it is the dangerous one: ``_develop_ledger_path``
    reads it as an exact override, so a developer or CI runner with it
    exported at a FINISHED develop ledger makes completion verify for every
    test here and flips the block cases to allow. The suite would then run
    against a DISABLED gate -- the exact failure this feature exists to
    prevent, inside the tests that prove it.

    It is set to an empty directory rather than deleted. Deleting it would
    fall back to the state dir under the redirected HOME, which is correct
    only for as long as that redirection holds; pointing it at a directory
    that provably contains no ledger does not depend on any other variable.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    no_ledger = tmp_path / "no-develop-dir"
    no_ledger.mkdir()
    monkeypatch.setenv("SPELLBOOK_DEV_DIR", str(no_ledger))
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
        goal_criteria=["tests pass"],
        set_at="2026-08-24T00:00:00Z",
    )
    fields.update(overrides)
    assert autonomous.write_autonomous_record(session_id, **fields) is True


def _transcript(tmp_path, events, name="transcript.jsonl"):
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8"
    )
    return str(path)


def _user_prompt(text="do the thing"):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _tool_result(tool_use_id="toolu_1"):
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok"}
            ],
        },
    }


def _assistant_tool_use(name, tool_use_id="toolu_1"):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_use_id, "name": name, "input": {}}
            ],
        },
    }


def _stdin(**overrides):
    data = {
        "hook_event_name": "Stop",
        "session_id": SID,
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


# ---- row 5: the block ------------------------------------------------------


class TestBlocks:
    def test_autonomous_without_question_or_completion_blocks(self, tmp_path):
        _record()
        transcript = _transcript(
            tmp_path, [_user_prompt(), _assistant_tool_use("Bash")]
        )
        result = _decision(_stdin(transcript_path=transcript))
        assert result is not None
        assert result["decision"] == "block"

    def test_block_reason_restates_the_escape_phrase(self, tmp_path):
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        reason = _decision(_stdin(transcript_path=transcript))["reason"]
        for phrase in spellbook_hook.AUTONOMOUS_ESCAPE_PHRASES:
            assert phrase in reason
        assert "stop autonomous" in reason

    def test_block_reason_names_the_active_philosophy(self, tmp_path):
        _record(philosophy="minimal-diff")
        transcript = _transcript(tmp_path, [_user_prompt()])
        reason = _decision(_stdin(transcript_path=transcript))["reason"]
        assert "minimal-diff" in reason

    def test_block_reason_states_autonomous_active_and_what_was_missed(
        self, tmp_path
    ):
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        reason = _decision(_stdin(transcript_path=transcript))["reason"]
        assert "Autonomous mode is ACTIVE" in reason
        assert "AskUserQuestion" in reason
        assert "completion is not verified" in reason

    def test_block_increments_blocked_stops_once(self, tmp_path):
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        data = _stdin(transcript_path=transcript)
        _decision(data)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 1
        _decision(data)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 2


# ---- rows 1-4: every ALLOW path -------------------------------------------


class TestAllows:
    def test_bad_session_id_allows_even_when_stop_hook_active(self, tmp_path):
        """A bad session id and a bad transcript still allow, without raising."""
        assert (
            _decision(
                _stdin(
                    stop_hook_active=True,
                    session_id="../../etc/passwd",
                    transcript_path=str(tmp_path / "nope.jsonl"),
                )
            )
            is None
        )

    def test_row2_no_record_allows(self, tmp_path):
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_row2_record_for_a_different_session_allows(self, tmp_path):
        _record(session_id="some-other-session")
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_row3_ask_user_question_in_ending_turn_allows(self, tmp_path):
        _record()
        transcript = _transcript(
            tmp_path,
            [
                _user_prompt(),
                _assistant_tool_use("Bash"),
                _tool_result(),
                _assistant_tool_use("AskUserQuestion", "toolu_2"),
            ],
        )
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_row3_ask_user_question_in_an_earlier_turn_still_blocks(
        self, tmp_path
    ):
        """The question must be in the ENDING turn, not anywhere in history."""
        _record()
        transcript = _transcript(
            tmp_path,
            [
                _user_prompt("first ask"),
                _assistant_tool_use("AskUserQuestion", "toolu_1"),
                _user_prompt("second ask"),
                _assistant_tool_use("Bash", "toolu_2"),
            ],
        )
        assert _decision(_stdin(transcript_path=transcript))["decision"] == "block"

    def test_row3_tool_results_do_not_cut_the_ending_turn(self, tmp_path):
        """A tool_result is a response, not a prompt; the turn spans it."""
        _record()
        transcript = _transcript(
            tmp_path,
            [
                _user_prompt(),
                _assistant_tool_use("AskUserQuestion", "toolu_1"),
                _tool_result("toolu_1"),
            ],
        )
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_row4_unverified_completion_does_not_allow(self, tmp_path):
        """A declared criterion with no evidence artifact is not complete."""
        _record()
        assert (
            spellbook_hook._autonomous_completion_verified(
                autonomous.read_autonomous_record(SID), _stdin()
            )
            is False
        )

    def test_row4_verified_completion_allows_the_stop(self, tmp_path, monkeypatch):
        """The artifact path, driven end to end through ``dispatch``."""
        monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)
        evidence = tmp_path / "evidence.json"
        evidence.write_text(
            json.dumps(
                {
                    "criteria": [
                        {
                            "criterion": "tests pass",
                            "command": "uv run pytest -q",
                            "output": "134 passed",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        _record(evidence_path=str(evidence))
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_row4_artifact_missing_a_criterion_still_blocks(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)
        evidence = tmp_path / "evidence.json"
        evidence.write_text(json.dumps({"criteria": []}), encoding="utf-8")
        _record(goal_criteria=["tests pass"], evidence_path=str(evidence))
        transcript = _transcript(tmp_path, [_user_prompt()])
        result = _decision(_stdin(transcript_path=transcript))
        assert result is not None
        assert result["decision"] == "block"

    def test_row4_finished_develop_ledger_allows_the_stop(self, tmp_path, monkeypatch):
        """The develop path, driven end to end through ``dispatch``."""
        import develop_gate_ledger

        dev_dir = tmp_path / "dev"
        dev_dir.mkdir()
        monkeypatch.setenv("SPELLBOOK_DEV_DIR", str(dev_dir))
        develop_gate_ledger.write_ledger(
            {
                "current_phase": "4",
                "remaining_gates": "",
                "ceremony": {"locked_at": "t", "selected": "code review"},
            },
            path=dev_dir / "develop_gate_ledger.json",
        )
        _record(goal_criteria=[])
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None


# ---- fail-open: every unknown resolves to ALLOW ---------------------------


class TestFailsOpen:
    def test_invalid_session_id_allows(self, tmp_path):
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert (
            _decision(
                _stdin(session_id="../../etc/passwd", transcript_path=transcript)
            )
            is None
        )

    def test_missing_session_id_allows(self, tmp_path):
        _record()
        data = _stdin(transcript_path=_transcript(tmp_path, [_user_prompt()]))
        del data["session_id"]
        assert _decision(data) is None

    def test_malformed_record_allows(self, tmp_path):
        _record()
        path = get_data_dir() / "autonomous" / f"{SID}.json"
        path.write_text("{not json", encoding="utf-8")
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_record_with_wrong_shape_allows(self, tmp_path):
        _record()
        path = get_data_dir() / "autonomous" / f"{SID}.json"
        path.write_text(json.dumps({"mode": "sideways"}), encoding="utf-8")
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_unreadable_transcript_allows(self, tmp_path):
        """An unknown must not trap the session -- even while autonomous."""
        _record()
        assert (
            _decision(_stdin(transcript_path=str(tmp_path / "missing.jsonl")))
            is None
        )

    def test_transcript_path_is_a_directory_allows(self, tmp_path):
        _record()
        assert _decision(_stdin(transcript_path=str(tmp_path))) is None

    def test_missing_transcript_path_field_allows(self, tmp_path):
        """No path is the same unknown as an unreadable one."""
        _record()
        data = _stdin()
        del data["transcript_path"]
        assert _decision(data) is None

    def test_garbage_lines_in_transcript_do_not_raise(self, tmp_path):
        _record()
        path = tmp_path / "t.jsonl"
        path.write_text(
            "not json\n" + json.dumps(_user_prompt()) + "\n[]\nnull\n",
            encoding="utf-8",
        )
        assert _decision(_stdin(transcript_path=str(path)))["decision"] == "block"

    def test_binary_transcript_allows(self, tmp_path):
        """Readable bytes but no parseable event is still an unknown."""
        _record()
        path = tmp_path / "t.jsonl"
        path.write_bytes(b"\xff\xfe\x00\x01garbage")
        assert _decision(_stdin(transcript_path=str(path))) is None

    def test_empty_transcript_allows(self, tmp_path):
        _record()
        path = tmp_path / "t.jsonl"
        path.write_text("", encoding="utf-8")
        assert _decision(_stdin(transcript_path=str(path))) is None


# ---- the dispatch seam itself ---------------------------------------------


class TestDispatchShape:
    def test_returns_json_text_not_a_list(self, tmp_path):
        _record()
        raw = _dispatch(_stdin(transcript_path=_transcript(tmp_path, [_user_prompt()])))
        assert isinstance(raw, str)
        assert json.loads(raw)["decision"] == "block"

    def test_other_events_are_unaffected(self):
        assert spellbook_hook.dispatch("NotAnEvent", "", _stdin()) is None


# ---- the isolation boundary itself ----------------------------------------


class TestEnvironmentIsolation:
    """Guards on ``isolated_state``. A gate's tests are only evidence while
    their own inputs are controlled, and the inputs here are environment
    variables that a developer or CI runner may legitimately have exported."""

    def test_fixture_controls_the_develop_dir_variable(self, tmp_path):
        assert os.environ["SPELLBOOK_DEV_DIR"] == str(tmp_path / "no-develop-dir")

    def test_no_develop_ledger_is_reachable_from_these_tests(self, tmp_path):
        path = spellbook_hook._develop_ledger_path(str(tmp_path))
        assert path is not None
        assert not path.exists()

    def test_an_inherited_finished_ledger_does_not_reach_the_hook(
        self, tmp_path, monkeypatch
    ):
        """The concrete flip this fixture exists to stop.

        A finished ledger is written where an INHERITED ``SPELLBOOK_DEV_DIR``
        would have pointed. The block must survive it, which it can only do
        because the fixture overrode the variable.
        """
        import develop_gate_ledger

        inherited = tmp_path / "inherited-dev"
        inherited.mkdir()
        develop_gate_ledger.write_ledger(
            {
                "current_phase": "4",
                "remaining_gates": "",
                "ceremony": {"locked_at": "t", "selected": "code review"},
            },
            path=inherited / "develop_gate_ledger.json",
        )
        _record(goal_criteria=[])
        transcript = _transcript(tmp_path, [_user_prompt()])
        result = _decision(_stdin(transcript_path=transcript))
        assert result is not None
        assert result["decision"] == "block"


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
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript))["decision"] == "block"

        _record()
        _submit("stop autonomous")
        assert _decision(_stdin(transcript_path=transcript)) is None


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
        transcript = _transcript(tmp_path, [_user_prompt()])
        first = _decision(_stdin(transcript_path=transcript))
        assert first["decision"] == "block"

        second = _decision(
            _stdin(transcript_path=transcript, stop_hook_active=True)
        )
        assert second is not None, "the hook allowed the stop that follows a block"
        assert second["decision"] == "block"

    def test_ask_user_question_still_allows_while_stop_hook_active(self, tmp_path):
        """Persistence must not swallow the legal exits."""
        _record()
        blocking_transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=blocking_transcript))["decision"] == "block"
        asking = _transcript(
            tmp_path,
            [_user_prompt(), _assistant_tool_use("AskUserQuestion")],
            name="asking.jsonl",
        )
        assert (
            _decision(_stdin(transcript_path=asking, stop_hook_active=True)) is None
        )


class TestThrashValve:
    def test_third_stop_inside_the_window_still_blocks(self, tmp_path):
        """Two recorded blocks are not yet evidence of thrashing."""
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        for _ in range(3):
            decision = _decision(
                _stdin(transcript_path=transcript, stop_hook_active=True)
            )
            assert decision["decision"] == "block"

    def test_fourth_stop_allows_after_three_blocks_inside_the_window(self, tmp_path):
        """Three blocks inside 60s is thrashing; the next stop is allowed.

        The valve counts blocks already ISSUED, so the fourth stop is the
        first one it can open on: there is no way to have three recorded
        blocks without the third having been issued.
        """
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        for _ in range(3):
            assert (
                _decision(_stdin(transcript_path=transcript, stop_hook_active=True))[
                    "decision"
                ]
                == "block"
            )
        assert (
            _decision(_stdin(transcript_path=transcript, stop_hook_active=True))
            is None
        )

    def test_three_blocks_spread_beyond_the_window_keep_blocking(self, tmp_path):
        """The same three blocks, spread over real work, are not thrashing."""
        _record()
        _seed_block_times([-300.0, -180.0, -61.0])
        transcript = _transcript(tmp_path, [_user_prompt()])
        decision = _decision(
            _stdin(transcript_path=transcript, stop_hook_active=True)
        )
        assert decision["decision"] == "block"

    def test_the_window_edge_is_inclusive(self, tmp_path):
        """Exactly 60s apart counts as inside the window."""
        _record()
        _seed_block_times([-59.5, -30.0, -1.0])
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert (
            _decision(_stdin(transcript_path=transcript, stop_hook_active=True))
            is None
        )

    def test_only_the_most_recent_timestamps_are_kept(self, tmp_path):
        """The stored window is bounded; it cannot grow with the session."""
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        for _ in range(3):
            _decision(_stdin(transcript_path=transcript, stop_hook_active=True))
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
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None


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

    def test_ask_user_question_allow_records_nothing(self, tmp_path):
        _record()
        transcript = _transcript(
            tmp_path, [_user_prompt(), _assistant_tool_use("AskUserQuestion")]
        )
        assert _decision(_stdin(transcript_path=transcript)) is None
        assert self._bookkeeping() == (0, [])

    def test_unreadable_transcript_allow_records_nothing(self, tmp_path):
        _record()
        assert (
            _decision(_stdin(transcript_path=str(tmp_path / "absent.jsonl"))) is None
        )
        assert self._bookkeeping() == (0, [])

    def test_verified_completion_allow_records_nothing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)
        evidence = tmp_path / "evidence.json"
        evidence.write_text(
            json.dumps(
                {"criteria": [{"criterion": "tests pass", "command": "pytest", "output": "ok"}]}
            ),
            encoding="utf-8",
        )
        _record(evidence_path=str(evidence))
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None
        assert self._bookkeeping() == (0, [])

    def test_the_valve_opening_records_nothing(self, tmp_path):
        """The stop the valve releases must not extend the window itself.

        A valve that stamped the stop it allowed would keep its own window
        full and latch open for the rest of the session.
        """
        _record()
        _seed_block_times([-3.0, -2.0, -1.0])
        before = self._bookkeeping()
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None
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
        transcript = _transcript(tmp_path, [_user_prompt()])
        _seed_block_times([-3.0, -2.0, -1.0])
        assert _decision(_stdin(transcript_path=transcript)) is None

        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window + 30.0), -(window + 20.0), -(window + 10.0)])
        assert _decision(_stdin(transcript_path=transcript))["decision"] == "block"

    def test_two_blocks_inside_the_window_do_not_open_it(self, tmp_path):
        """The limit is a count, not "any recent block at all"."""
        _record()
        _seed_block_times([-2.0, -1.0])
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript))["decision"] == "block"


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
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript)) is None

    def test_three_blocks_just_outside_the_window_block(self, tmp_path):
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window + 3.0), -(window + 2.0), -(window + 1.0)])
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript))["decision"] == "block"

    def test_the_oldest_of_three_decides_not_the_newest(self, tmp_path):
        """Two blocks moments ago plus one stale block is not thrashing.

        A valve reading the MOST RECENT timestamp instead of the
        ``BLOCK_WINDOW_LIMIT``-th most recent would open here.
        """
        _record()
        window = autonomous.BLOCK_WINDOW_SECONDS
        _seed_block_times([-(window * 10), -2.0, -1.0])
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert _decision(_stdin(transcript_path=transcript))["decision"] == "block"


class TestStopHookActiveIsInert:
    """``stop_hook_active`` must not change ANY row's verdict.

    The reversed row is pinned above for the block case. These pin that the
    flag is not consulted anywhere else either -- a reintroduced guard placed
    on a different row would otherwise be invisible.
    """

    @pytest.mark.parametrize("flag", [False, True])
    def test_the_block_row_is_identical_either_way(self, tmp_path, flag):
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        decision = _decision(
            _stdin(transcript_path=transcript, stop_hook_active=flag)
        )
        assert decision["decision"] == "block"

    @pytest.mark.parametrize("flag", [False, True])
    def test_the_valve_row_is_identical_either_way(self, tmp_path, flag):
        _record()
        _seed_block_times([-3.0, -2.0, -1.0])
        transcript = _transcript(tmp_path, [_user_prompt()])
        assert (
            _decision(_stdin(transcript_path=transcript, stop_hook_active=flag))
            is None
        )

    def test_a_missing_flag_blocks_exactly_as_a_present_one(self, tmp_path):
        _record()
        transcript = _transcript(tmp_path, [_user_prompt()])
        data = _stdin(transcript_path=transcript)
        del data["stop_hook_active"]
        assert _decision(data)["decision"] == "block"
