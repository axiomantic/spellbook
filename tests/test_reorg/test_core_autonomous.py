"""Tests for spellbook.core.autonomous.

This module backs the Stop hook, so its central contract is that every
failure mode degrades to "not autonomous" instead of raising -- a hook that
raises takes out the operator's turn. Each degradation path below asserts
that outcome explicitly rather than an exception.
"""

import json
import os

import pytest

from spellbook.core import autonomous
from spellbook.core.paths import get_data_dir


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect the data dir so tests never touch the real state file.

    ``LOCALAPPDATA`` is the one that matters on Windows: ``get_data_dir()``
    reads it directly, so leaving it unset redirected nothing there. Every
    test in this file then shared the developer's REAL records directory --
    which both leaks state between tests and writes to a directory the suite
    does not own. The redirection is asserted rather than assumed, because a
    variable that stops being read is invisible: the tests would go on
    passing against the real directory on the platform that still resolves
    through ``HOME``.
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


SID = "abc-123_def.456"


def _write_record(**overrides):
    fields = dict(
        session_id=SID,
        mode="fully",
        philosophy="build-right",
        goal="ship the feature",
        set_at="2026-08-24T00:00:00Z",
    )
    fields.update(overrides)
    session_id = fields.pop("session_id")
    return autonomous.write_autonomous_record(session_id, **fields)


# ---- happy path -----------------------------------------------------------


class TestHappyPath:
    def test_write_then_read_round_trips(self):
        assert _write_record() is True
        record = autonomous.read_autonomous_record(SID)
        assert record["mode"] == "fully"
        assert record["philosophy"] == "build-right"
        assert record["goal"] == "ship the feature"
        assert record["blocked_stops"] == 0

    def test_record_lives_under_autonomous_subdir_of_state_dir(self):
        _write_record()
        expected = get_data_dir() / "autonomous" / f"{SID}.json"
        assert expected.is_file()
        on_disk = json.loads(expected.read_text(encoding="utf-8"))
        assert on_disk["mode"] == "fully"

    def test_mostly_mode_is_valid(self):
        assert _write_record(mode="mostly") is True
        assert autonomous.read_autonomous_record(SID)["mode"] == "mostly"

    def test_clear_removes_record(self):
        _write_record()
        autonomous.clear_autonomous_record(SID)
        assert autonomous.read_autonomous_record(SID) is None

    def test_clear_on_missing_record_is_a_silent_no_op(self):
        autonomous.clear_autonomous_record(SID)  # must not raise
        assert autonomous.read_autonomous_record(SID) is None


# ---- degradation: invalid session id ---------------------------------------


class TestInvalidSessionId:
    @pytest.mark.parametrize(
        "bad_sid",
        [
            "",
            None,
            "../../etc/passwd",
            "has spaces",
            "has/slash",
            "a" * 200,
        ],
    )
    def test_read_returns_none(self, bad_sid):
        assert autonomous.read_autonomous_record(bad_sid) is None

    def test_write_returns_false_and_creates_nothing(self, tmp_path):
        ok = autonomous.write_autonomous_record(
            "../escape",
            mode="fully",
            philosophy="build-right",
            goal="x",
            set_at="2026-08-24T00:00:00Z",
        )
        assert ok is False
        assert not (get_data_dir() / "autonomous").exists()

    def test_clear_does_not_raise(self):
        autonomous.clear_autonomous_record("../../escape")

    def test_record_blocked_stop_returns_none(self):
        assert autonomous.record_blocked_stop("bad id!", now=1000.0) is None


# ---- degradation: missing / malformed / unreadable file --------------------


class TestMalformedRecord:
    def test_missing_file_reads_as_none(self):
        assert autonomous.read_autonomous_record(SID) is None

    def test_invalid_json_reads_as_none(self):
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text("{not json", encoding="utf-8")
        assert autonomous.read_autonomous_record(SID) is None

    def test_json_array_instead_of_object_reads_as_none(self):
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text("[1, 2, 3]", encoding="utf-8")
        assert autonomous.read_autonomous_record(SID) is None

    def test_wrong_mode_value_reads_as_none(self):
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text(
            json.dumps(
                {
                    "mode": "sorta",
                    "philosophy": "build-right",
                    "goal": "x",
                    "set_at": "now",
                    "blocked_stops": 0,
                    "decisions": [],
                }
            ),
            encoding="utf-8",
        )
        assert autonomous.read_autonomous_record(SID) is None

    def test_wrong_field_types_read_as_none(self):
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text(
            json.dumps(
                {
                    "mode": "fully",
                    "philosophy": "build-right",
                    "goal": 7,
                    "set_at": "now",
                    "blocked_stops": 0,
                    "decisions": [],
                }
            ),
            encoding="utf-8",
        )
        assert autonomous.read_autonomous_record(SID) is None

    def test_partial_record_missing_field_reads_as_none(self):
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text(
            json.dumps({"mode": "fully", "philosophy": "build-right"}),
            encoding="utf-8",
        )
        assert autonomous.read_autonomous_record(SID) is None

    def test_blocked_stops_as_bool_is_rejected(self):
        """bool is an int subclass in Python; the validator must not accept it."""

        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text(
            json.dumps(
                {
                    "mode": "fully",
                    "philosophy": "build-right",
                    "goal": "x",
                    "set_at": "now",
                    "blocked_stops": True,
                    "decisions": [],
                }
            ),
            encoding="utf-8",
        )
        assert autonomous.read_autonomous_record(SID) is None

    def test_unreadable_file_reads_as_none(self):
        """The ``except OSError`` branch on the read, actually reached.

        The record written here is otherwise VALID, so an allow can only
        come from the unreadable file. A payload that failed validation for
        an unrelated missing field would pass this test with the branch
        never entered.
        """
        _skip_unless_permission_bits_enforced()
        assert _write_record() is True
        target = get_data_dir() / "autonomous" / f"{SID}.json"
        assert autonomous.read_autonomous_record(SID) is not None
        target.chmod(0o000)
        try:
            assert autonomous.read_autonomous_record(SID) is None
        finally:
            target.chmod(0o644)

    def test_a_non_utf8_record_reads_as_none(self):
        """``read_text(encoding="utf-8")`` raises ``UnicodeDecodeError``.

        That is a ``ValueError``, not an ``OSError``. Only the hook's
        blanket catch stood between it and the operator's turn, and the
        autonomous-mode skill calls this module directly with no such catch.
        """
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_bytes(b"\xff\xfe\x00not utf-8 at all")
        assert autonomous.read_autonomous_record(SID) is None


# ---- write validation -------------------------------------------------


class TestWriteValidation:
    def test_write_rejects_bad_mode(self):
        ok = autonomous.write_autonomous_record(
            SID,
            mode="turbo",
            philosophy="build-right",
            goal="x",
            set_at="now",
        )
        assert ok is False
        assert autonomous.read_autonomous_record(SID) is None

    def test_write_defaults_decisions_to_empty_list(self):
        _write_record()
        assert autonomous.read_autonomous_record(SID)["decisions"] == []


# ---- append_decision --------------------------------------------------


class TestAppendDecision:
    def test_append_to_existing_record(self):
        _write_record()
        ok = autonomous.append_decision(
            SID,
            at="2026-08-24T00:01:00Z",
            philosophy="build-right",
            decision="used sqlite over postgres",
            alternatives="postgres",
        )
        assert ok is True
        decisions = autonomous.read_autonomous_record(SID)["decisions"]
        assert len(decisions) == 1
        assert decisions[0] == {
            "at": "2026-08-24T00:01:00Z",
            "philosophy": "build-right",
            "decision": "used sqlite over postgres",
            "alternatives": "postgres",
        }

    def test_two_appends_preserve_order_and_both_survive(self):
        _write_record()
        autonomous.append_decision(
            SID,
            at="t1",
            philosophy="build-right",
            decision="first decision",
            alternatives="alt1",
        )
        autonomous.append_decision(
            SID,
            at="t2",
            philosophy="ship-fast",
            decision="second decision",
            alternatives="alt2",
        )
        decisions = autonomous.read_autonomous_record(SID)["decisions"]
        assert len(decisions) == 2
        assert decisions[0]["decision"] == "first decision"
        assert decisions[0]["philosophy"] == "build-right"
        assert decisions[1]["decision"] == "second decision"
        assert decisions[1]["philosophy"] == "ship-fast"

    def test_append_copies_philosophy_at_call_time_not_from_record(self):
        """The record's own philosophy field must not be read back; the
        caller-supplied philosophy is what gets stored, since it can differ
        from whatever is active in the record by the time of the append."""
        _write_record(philosophy="build-right")
        autonomous.append_decision(
            SID,
            at="t1",
            philosophy="minimal-diff",
            decision="chose the smaller patch",
            alternatives="full rewrite",
        )
        record = autonomous.read_autonomous_record(SID)
        assert record["philosophy"] == "build-right"
        assert record["decisions"][0]["philosophy"] == "minimal-diff"

    def test_append_to_absent_record_is_silent_no_op(self):
        ok = autonomous.append_decision(
            SID,
            at="t1",
            philosophy="build-right",
            decision="x",
            alternatives="y",
        )
        assert ok is False
        assert autonomous.read_autonomous_record(SID) is None

    def test_append_to_malformed_record_is_silent_no_op(self):
        d = get_data_dir() / "autonomous"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{SID}.json").write_text("{not json", encoding="utf-8")

        ok = autonomous.append_decision(
            SID,
            at="t1",
            philosophy="build-right",
            decision="x",
            alternatives="y",
        )
        assert ok is False

    def test_append_with_invalid_session_id_is_silent_no_op(self):
        ok = autonomous.append_decision(
            "../escape",
            at="t1",
            philosophy="build-right",
            decision="x",
            alternatives="y",
        )
        assert ok is False


# ---- filesystem-fault propagation contract --------------------------------
#
# write_autonomous_record is operator-initiated and must propagate a genuine
# filesystem error. record_blocked_stop and append_decision are
# Stop-hook-initiated and must swallow the same fault into their documented
# "not autonomous" return value. These tests plant a REAL fault (a read-only
# data-dir root that blocks mkdir/mkstemp underneath it) rather than patching
# an internal, so the two contracts are proven apart, not merely asserted.


@pytest.fixture
def readonly_data_root(tmp_path):
    """Make the autonomous-records directory's parent unwritable.

    ``get_data_dir()`` resolves to ``<HOME>/.local/spellbook``; locking down
    ``<HOME>/.local`` means the module's own ``path.parent.mkdir(...)`` call
    hits a real ``PermissionError`` (an ``OSError`` subclass) the first time
    it tries to create ``.../spellbook/autonomous``. Root tests are skipped:
    root ignores POSIX permission bits, so the fault would never fire.
    """
    if os.name != "posix":
        pytest.skip("POSIX permission bits only")
    if os.geteuid() == 0:
        pytest.skip("root ignores permission bits; fault would not fire")
    local_dir = tmp_path / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)
    local_dir.chmod(0o500)  # r-x, no write: mkdir underneath fails
    try:
        yield local_dir
    finally:
        local_dir.chmod(0o700)


def _skip_unless_permission_bits_enforced():
    if os.name != "posix":
        pytest.skip("POSIX permission bits only")
    if os.geteuid() == 0:
        pytest.skip("root ignores permission bits; fault would not fire")


class TestFilesystemFaultPropagation:
    def test_write_autonomous_record_raises_on_real_fs_fault(
        self, readonly_data_root
    ):
        with pytest.raises(OSError):
            autonomous.write_autonomous_record(
                SID,
                mode="fully",
                philosophy="build-right",
                goal="x",
                    set_at="now",
            )

    def test_record_blocked_stop_returns_none_on_real_fs_fault(
        self, isolated_state
    ):
        _skip_unless_permission_bits_enforced()

        # Write the record while the directory is still writable, so the
        # READ side of record_blocked_stop succeeds and only the
        # subsequent write (mkstemp inside the existing "autonomous" dir)
        # hits the real fault.
        _write_record()
        autonomous_dir = get_data_dir() / "autonomous"
        autonomous_dir.chmod(0o500)  # r-x, no write: mkstemp fails inside it
        try:
            assert autonomous.record_blocked_stop(SID, now=1000.0) is None
        finally:
            autonomous_dir.chmod(0o700)

    def test_append_decision_returns_false_on_real_fs_fault(self, isolated_state):
        _skip_unless_permission_bits_enforced()

        _write_record()
        autonomous_dir = get_data_dir() / "autonomous"
        autonomous_dir.chmod(0o500)
        try:
            ok = autonomous.append_decision(
                SID,
                at="t1",
                philosophy="build-right",
                decision="x",
                alternatives="y",
            )
        finally:
            autonomous_dir.chmod(0o700)
        assert ok is False


# ---- the philosophy enum --------------------------------------------------


class TestPhilosophyEnum:
    """The philosophy id is what the Stop hook names in its block message, so
    an id nothing can interpret must fail closed. These assert through the
    public read/write API rather than inspecting the enum's membership."""

    @pytest.mark.parametrize("philosophy", sorted(autonomous.PHILOSOPHIES))
    def test_every_enum_id_is_accepted(self, philosophy):
        assert _write_record(philosophy=philosophy) is True
        record = autonomous.read_autonomous_record(SID)
        assert record is not None
        assert record["philosophy"] == philosophy

    def test_default_philosophy_is_an_accepted_id(self):
        assert _write_record(philosophy=autonomous.DEFAULT_PHILOSOPHY) is True
        record = autonomous.read_autonomous_record(SID)
        assert record["philosophy"] == autonomous.DEFAULT_PHILOSOPHY

    def test_write_refuses_an_unknown_philosophy(self):
        assert _write_record(philosophy="vibes") is False

    def test_record_with_an_unknown_philosophy_reads_as_not_autonomous(self):
        """Written past the API by hand, as a stale or hand-edited record
        would be: the read side must refuse it too, not just the write side."""
        _write_record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["philosophy"] = "vibes"
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert autonomous.read_autonomous_record(SID) is None

    def test_record_with_an_empty_philosophy_reads_as_not_autonomous(self):
        _write_record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["philosophy"] = ""
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert autonomous.read_autonomous_record(SID) is None

    def test_a_decisions_entry_keeps_an_unknown_philosophy(self):
        """A decisions entry records what was active HISTORICALLY. If the enum
        ever drops or renames an id, strict validation there would make every
        session carrying it read as not autonomous -- silently disabling
        enforcement over an entry nothing acts on."""
        _write_record()
        assert (
            autonomous.append_decision(
                SID,
                at="2026-08-24T01:00:00Z",
                philosophy="retired-id",
                decision="d",
                alternatives="a",
            )
            is True
        )
        record = autonomous.read_autonomous_record(SID)
        assert record is not None
        assert record["decisions"][0]["philosophy"] == "retired-id"

    def test_a_decisions_entry_with_a_non_string_philosophy_is_still_refused(self):
        """Loosening the enum check there does not loosen the type check."""
        _write_record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["decisions"] = [
            {"at": "t", "philosophy": 7, "decision": "d", "alternatives": "a"}
        ]
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert autonomous.read_autonomous_record(SID) is None


# ---- the rolling-window valve ---------------------------------------------
#
# Every test here passes ``now`` explicitly instead of sleeping. The window is
# sixty seconds wide, so a sleeping test would have to burn a real minute to
# cross it, and a loaded machine would make the boundary cases flaky. An
# injected clock makes the boundary exact.


class TestThrashValve:
    def test_no_timestamps_keeps_the_valve_shut(self):
        _write_record()
        record = autonomous.read_autonomous_record(SID)
        assert autonomous.thrash_valve_open(record, now=1000.0) is False

    def test_one_short_of_the_limit_keeps_the_valve_shut(self):
        record = {"block_times": [1000.0] * (autonomous.BLOCK_WINDOW_LIMIT - 1)}
        assert autonomous.thrash_valve_open(record, now=1000.0) is False

    def test_limit_reached_inside_the_window_opens_the_valve(self):
        record = {"block_times": [1000.0, 1010.0, 1020.0]}
        assert autonomous.thrash_valve_open(record, now=1030.0) is True

    def test_exactly_at_the_window_edge_opens_the_valve(self):
        record = {"block_times": [1000.0, 1010.0, 1020.0]}
        assert (
            autonomous.thrash_valve_open(
                record, now=1000.0 + autonomous.BLOCK_WINDOW_SECONDS
            )
            is True
        )

    def test_one_second_past_the_window_keeps_the_valve_shut(self):
        record = {"block_times": [1000.0, 1010.0, 1020.0]}
        assert (
            autonomous.thrash_valve_open(
                record, now=1001.0 + autonomous.BLOCK_WINDOW_SECONDS
            )
            is False
        )

    def test_old_blocks_do_not_help_a_recent_pair(self):
        """Three total blocks, but only two of them are recent."""
        record = {"block_times": [0.0, 1010.0, 1020.0]}
        assert autonomous.thrash_valve_open(record, now=1030.0) is False

    def test_a_backward_clock_step_opens_the_valve_rather_than_trapping(self):
        """The unsafe direction must not exist: a bad clock releases.

        A wall clock can step backward. The resulting negative elapsed time
        reads as "inside the window", which ALLOWS a stop. The reverse -- a
        clock fault that holds the session -- is what must be impossible.
        """
        record = {"block_times": [5000.0, 5010.0, 5020.0]}
        assert autonomous.thrash_valve_open(record, now=1000.0) is True

    def test_malformed_and_missing_records_never_raise(self):
        for record in (None, "nope", {}, {"block_times": None},
                       {"block_times": "three"}, {"block_times": [None, "x"]}):
            assert autonomous.thrash_valve_open(record, now=1000.0) is False


class TestRecordBlockedStop:
    def test_it_bumps_the_counter_and_stamps_the_window(self):
        _write_record()
        assert autonomous.record_blocked_stop(SID, now=1000.0) == 1
        record = autonomous.read_autonomous_record(SID)
        assert record["blocked_stops"] == 1
        assert record["block_times"] == [1000.0]

    def test_stored_timestamps_are_bounded_to_the_window_limit(self):
        _write_record()
        for tick in range(20):
            autonomous.record_blocked_stop(SID, now=float(tick))
        record = autonomous.read_autonomous_record(SID)
        assert record["blocked_stops"] == 20
        assert record["block_times"] == [17.0, 18.0, 19.0]
        assert len(record["block_times"]) == autonomous.BLOCK_WINDOW_LIMIT

    def test_it_preserves_the_rest_of_the_record(self):
        """A blocked stop is a read-modify-write; it must modify one thing.

        The fields checked here are the ones a lost write would cost most:
        the decisions log the operator reviews afterwards, the goal the block
        message quotes back, and the philosophy that message names.
        """
        _write_record(philosophy="minimal-diff")
        autonomous.append_decision(
            SID, at="t", philosophy="minimal-diff", decision="d", alternatives="a"
        )
        autonomous.record_blocked_stop(SID, now=1000.0)
        record = autonomous.read_autonomous_record(SID)
        assert len(record["decisions"]) == 1
        assert record["decisions"][0]["decision"] == "d"
        assert record["goal"] == "ship the feature"
        assert record["philosophy"] == "minimal-diff"

    def test_no_record_degrades_to_none(self):
        assert autonomous.record_blocked_stop(SID, now=1000.0) is None

    def test_a_degraded_call_does_not_create_a_record(self):
        autonomous.record_blocked_stop(SID, now=1000.0)
        assert autonomous.read_autonomous_record(SID) is None

    def test_invalid_session_id_degrades_to_none(self):
        assert autonomous.record_blocked_stop("../etc/passwd", now=1.0) is None

    def test_append_decision_preserves_the_window(self):
        _write_record()
        autonomous.record_blocked_stop(SID, now=1000.0)
        autonomous.append_decision(
            SID, at="t", philosophy="build-right", decision="d", alternatives="a"
        )
        assert autonomous.read_autonomous_record(SID)["block_times"] == [1000.0]


class TestBlockTimesValidation:
    def _corrupt(self, value):
        _write_record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["block_times"] = value
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_a_non_list_makes_the_record_read_as_not_autonomous(self):
        self._corrupt("later")
        assert autonomous.read_autonomous_record(SID) is None

    def test_a_non_numeric_entry_makes_the_record_read_as_not_autonomous(self):
        self._corrupt([1000.0, "later"])
        assert autonomous.read_autonomous_record(SID) is None

    def test_a_boolean_entry_makes_the_record_read_as_not_autonomous(self):
        self._corrupt([True])
        assert autonomous.read_autonomous_record(SID) is None

    def test_absent_block_times_still_reads_as_a_valid_record(self):
        """Records written before the valve existed must keep working."""
        _write_record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["block_times"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        record = autonomous.read_autonomous_record(SID)
        assert record is not None
        assert autonomous.recent_block_times(record) == []


# ---- the clear reports the artifact, not the call --------------------------


class TestClearReportsWhetherTheRecordIsGone:
    """``clear_autonomous_record`` backs the operator's only escape hatch.

    Its caller prints a confirmation, so a return value that says "the call
    was made" rather than "the record is gone" makes the confirmation a
    claim nothing checked.
    """

    def test_a_real_clear_reports_true(self):
        _write_record()
        assert autonomous.clear_autonomous_record(SID) is True
        assert autonomous._record_path(SID).exists() is False

    def test_an_absent_record_reports_true(self):
        """Idempotent: the record is gone, which is what the caller asked."""
        assert autonomous.clear_autonomous_record(SID) is True

    def test_an_invalid_session_id_reports_false(self):
        assert autonomous.clear_autonomous_record("../../etc/passwd") is False

    def test_a_real_filesystem_fault_reports_false(self):
        """A read-only directory: the unlink fails and the record survives."""
        _skip_unless_permission_bits_enforced()
        _write_record()
        autonomous_dir = get_data_dir() / "autonomous"
        autonomous_dir.chmod(0o500)
        try:
            assert autonomous.clear_autonomous_record(SID) is False
            assert autonomous._record_path(SID).exists() is True
        finally:
            autonomous_dir.chmod(0o700)


# ---- stamps that cannot become floats -------------------------------------


class TestUnusableTimestamps:
    """An int carries no infinity to test for, so a NaN/inf check passes
    ``10**400`` and the ``OverflowError`` then lands inside
    ``record_blocked_stop``, which documents that it never raises.
    """

    def _write_stamp(self, stamp):
        _write_record()
        path = autonomous._record_path(SID)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["block_times"] = [stamp]
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_an_int_too_large_for_a_float_reads_as_not_autonomous(self):
        self._write_stamp(10**400)
        assert autonomous.read_autonomous_record(SID) is None

    def test_record_blocked_stop_degrades_instead_of_raising(self):
        self._write_stamp(10**400)
        assert autonomous.record_blocked_stop(SID, now=1000.0) is None

    def test_recent_block_times_drops_it_instead_of_raising(self):
        """``recent_block_times`` takes ``Any``; a caller may hand it an
        unvalidated dict, and its docstring promises it never raises."""
        assert autonomous.recent_block_times({"block_times": [10**400, 5.0]}) == [5.0]

    def test_the_valve_does_not_raise_on_one(self):
        assert (
            autonomous.thrash_valve_open(
                {"block_times": [10**400, 1.0, 2.0, 3.0]}, now=3.0
            )
            is True
        )


# ---- the read-modify-write lock -------------------------------------------


class TestConcurrentUpdateLock:
    """Hook events are separate processes, so these are genuinely concurrent.

    A dropped valve timestamp degrades the only bound on the block loop, so
    the lock is taken. It must never be able to BLOCK the update: failing to
    take it leaves exactly the unlocked behaviour it replaced.
    """

    def test_the_update_still_lands_when_the_lock_cannot_be_taken(self):
        _skip_unless_permission_bits_enforced()
        _write_record()
        # A lock file that exists but cannot be opened for writing: the
        # acquire raises PermissionError, and the update must proceed.
        lock_path = get_data_dir() / "autonomous" / f"{SID}.lock"
        lock_path.write_text("", encoding="utf-8")
        lock_path.chmod(0o000)
        try:
            assert autonomous.record_blocked_stop(SID, now=1000.0) == 1
        finally:
            lock_path.chmod(0o600)
        assert autonomous.read_autonomous_record(SID)["blocked_stops"] == 1

    def test_the_lock_is_released_so_a_second_update_succeeds(self):
        """A lock left held would deadlock the next hook event on this session."""
        _write_record()
        assert autonomous.record_blocked_stop(SID, now=1000.0) == 1
        assert autonomous.record_blocked_stop(SID, now=1001.0) == 2
        assert (
            autonomous.append_decision(
                SID, at="t", philosophy="build-right", decision="d", alternatives="a"
            )
            is True
        )

    def test_a_serialized_pair_of_updates_keeps_both(self):
        """The lost update the lock exists to prevent, driven in one process."""
        _write_record()
        autonomous.record_blocked_stop(SID, now=1000.0)
        autonomous.append_decision(
            SID, at="t", philosophy="build-right", decision="d", alternatives="a"
        )
        record = autonomous.read_autonomous_record(SID)
        assert record["blocked_stops"] == 1
        assert autonomous.recent_block_times(record) == [1000.0]
        assert len(record["decisions"]) == 1
