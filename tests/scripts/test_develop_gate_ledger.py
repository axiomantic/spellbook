"""Tests for scripts/develop_gate_ledger.py.

The ledger is the persistent state file the develop skill uses to
track ceremony selection, gate completion, and wave-discipline checks.
These tests cover the merge contract, the locked_at lock rule, the
wave-discipline recording, and the CLI surface -- not the develop
skill's usage of the ledger, which is exercised by an actual develop
run, not a Python test.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/develop_gate_ledger.py imports cleanly under any python that
# can run the rest of spellbook's tests; we just make sure the path
# resolves when the module is imported.
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "develop_gate_ledger.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))

import develop_gate_ledger as ledger


@pytest.fixture
def tmp_ledger(tmp_path, monkeypatch):
    """Point the ledger at a temp file so tests do not touch the real one.

    ``ledger_path()`` already honors ``$SPELLBOOK_DEV_DIR``, so setting
    the environment variable is enough -- no attribute patching. The
    same variable also redirects the CLI subprocess tests below, which
    is why they get the real path rather than a private one.
    """
    monkeypatch.setenv("SPELLBOOK_DEV_DIR", str(tmp_path))
    return tmp_path / "develop_gate_ledger.json"


# ---- read / write --------------------------------------------------------


def test_read_missing_returns_empty_dict(tmp_ledger):
    assert ledger.read_ledger() == {}


def test_write_creates_parent_dirs(tmp_ledger, tmp_path):
    nested = tmp_path / "deeply" / "nested" / "develop_gate_ledger.json"
    ledger.write_ledger({"current_phase": "0"}, path=nested)
    assert nested.exists()
    assert json.loads(nested.read_text())["current_phase"] == "0"


def test_write_uses_deep_merge_not_overwrite(tmp_ledger):
    """Existing fields are preserved unless the overlay explicitly sets them.

    This is the skill's CRIT-2 "MERGE-ONLY, NEVER overwrite" requirement.
    A full overwrite from the develop skill would clobber the
    workflow_state fields written by the spellbook hooks.
    """
    ledger.write_ledger({"current_phase": "1", "plan_pointer": "/tmp/p.md"})
    ledger.write_ledger({"current_phase": "2"})
    data = ledger.read_ledger()
    assert data["current_phase"] == "2"
    assert data["plan_pointer"] == "/tmp/p.md"


def test_scalar_replacement_shrinks_lists_of_strings(tmp_ledger):
    """The skill stores newline-joined SCALARs for ``remaining_gates`` so
    they can shrink. A list-append would accumulate forever; verify the
    scalar replacement contract holds.
    """
    ledger.write_ledger({"remaining_gates": "code review\ngreen-mirage"})
    ledger.write_ledger({"remaining_gates": "code review"})
    assert ledger.read_ledger()["remaining_gates"] == "code review"


def test_replacing_an_object_with_a_scalar_warns(tmp_ledger, caplog):
    """Collapsing an object to a scalar discards every field under it at
    once -- including ceremony.locked_at, whose whole purpose is to be
    un-rewritable. The write still proceeds (a genuine shape change must
    not strand the ledger), but it must not be invisible."""
    ledger.write_ledger({"ceremony": {"locked_at": "2026-08-10T14:02Z", "source": "op"}})

    with caplog.at_level(logging.WARNING):
        ledger.write_ledger({"ceremony": "legacy-string"})

    assert "ceremony" in caplog.text
    assert "locked_at" in caplog.text
    assert ledger.read_ledger()["ceremony"] == "legacy-string"


def test_ordinary_scalar_replacement_does_not_warn(tmp_ledger, caplog):
    """Scalar-to-scalar replacement is the documented contract. Warning on it
    would train the reader to ignore the warning that matters."""
    ledger.write_ledger({"current_phase": "1"})

    with caplog.at_level(logging.WARNING):
        ledger.write_ledger({"current_phase": "2"})

    assert caplog.text == ""


def test_nested_object_replacement_names_the_full_path(tmp_ledger, caplog):
    """A warning that says 'something was replaced' without saying where is
    not actionable in a ledger this nested."""
    ledger.record_wave_discipline("3a", status="passed")

    with caplog.at_level(logging.WARNING):
        ledger.write_ledger({"waves": {"3a": {"section_24_6_check": "clobbered"}}})

    assert "waves.3a.section_24_6_check" in caplog.text


def test_corrupt_json_raises(tmp_ledger):
    tmp_ledger.write_text("{not valid json}", encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="not valid JSON"):
        ledger.read_ledger()


def test_non_object_root_raises(tmp_ledger):
    tmp_ledger.write_text(json.dumps(["not", "an", "object"]))
    with pytest.raises(ledger.LedgerError, match="not a JSON object"):
        ledger.read_ledger()


# ---- ceremony lock -------------------------------------------------------


def test_set_ceremony_field_writes_field(tmp_ledger):
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    assert ledger.read_ledger()["ceremony"]["selected"] == (
        "code review\ngreen-mirage"
    )


def test_set_ceremony_locked_at_first_time_succeeds(tmp_ledger):
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    assert ledger.read_ledger()["ceremony"]["locked_at"] == "2026-08-10T14:02Z"


def test_set_ceremony_locked_at_second_time_refused(tmp_ledger):
    """The lock is a floor. The skill is explicit: once locked, never
    rewrite. A second call with a different value must raise.
    """
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to rewrite"):
        ledger.set_ceremony_field("locked_at", "2026-08-11T09:00Z")


def test_set_ceremony_locked_at_same_value_succeeds(tmp_ledger):
    """Idempotent re-set with the same value is OK -- a resumed session
    that re-asserts the lock should not be punished.
    """
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    assert ledger.read_ledger()["ceremony"]["locked_at"] == "2026-08-10T14:02Z"


def test_set_ceremony_rejects_unknown_field(tmp_ledger):
    with pytest.raises(ValueError, match="unknown ceremony field"):
        ledger.set_ceremony_field("bogus_field", "x")


def test_set_ceremony_gate_position_accepts_per_task(tmp_ledger):
    """gate_position is a documented ceremony field; the module must be able
    to write it (capability 1)."""
    ledger.set_ceremony_field("gate_position", "per_task")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_task"


def test_set_ceremony_gate_position_accepts_per_group(tmp_ledger):
    ledger.set_ceremony_field("gate_position", "per_group")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_group"


def test_set_ceremony_gate_position_rejects_invalid_value(tmp_ledger):
    """A field whose value space is closed needs a VALUE guard, not just a
    NAME guard: 'per_wave' is a plausible typo that would otherwise be
    stored and read back as if it meant something."""
    with pytest.raises(ValueError, match="per_task"):
        ledger.set_ceremony_field("gate_position", "per_wave")
    assert "gate_position" not in ledger.read_ledger().get("ceremony", {})


def test_set_ceremony_gate_position_rewrite_after_lock_refused(tmp_ledger):
    """gate_position is locked WITH the rest of ceremony at locked_at.

    The skill's ledger shape says "Locked with the rest of ceremony at
    locked_at; never changed mid-run", and 40-develop-discipline.md says
    changing gate position after the lock requires the same
    ABORT-and-re-invoke path as any other ceremony change. A guard that
    only covers locked_at leaves repositioning as a silent mid-run edit.
    """
    ledger.set_ceremony_field("gate_position", "per_task")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to rewrite"):
        ledger.set_ceremony_field("gate_position", "per_group")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_task"


def test_set_ceremony_gate_position_same_value_after_lock_succeeds(tmp_ledger):
    """Idempotent re-assertion is not a change -- a resumed session
    re-writing the value it already holds must not be punished, matching
    the locked_at guard's own same-value allowance.
    """
    ledger.set_ceremony_field("gate_position", "per_group")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("gate_position", "per_group")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_group"


def test_set_ceremony_gate_position_first_write_after_lock_succeeds(tmp_ledger):
    """The guard refuses a REWRITE, not a first write. A ceremony locked
    without an explicit gate_position defaults to per_task by documentation,
    not by a stored value, so writing the field once afterwards is still the
    original selection being recorded -- not a mid-run reposition.
    """
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("gate_position", "per_group")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_group"


def test_gate_position_writable_again_after_archive_ceremony(tmp_ledger):
    """ABORT-and-re-invoke is the sanctioned path: archiving clears the
    ceremony, so a fresh Phase 0 may select a different gate_position.
    """
    ledger.set_ceremony_field("gate_position", "per_task")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("operator aborted; re-selecting")
    ledger.set_ceremony_field("gate_position", "per_group")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_group"


def test_set_scalar_rejects_dotted_field(tmp_ledger):
    """Use set_ceremony_field for ceremony.* -- set_scalar is for the
    top level only, and a dotted argument is almost certainly a bug.
    """
    with pytest.raises(ValueError, match="top-level fields"):
        ledger.set_scalar("ceremony.selected", "x")


# ---- archive-ceremony ----------------------------------------------------


def test_archive_ceremony_refuses_empty_reason(tmp_ledger):
    """Superseding a lock is the one auditable exception to CRIT-2. An
    archive with no stated reason is exactly the unaudited path the lock
    exists to prevent -- mirrors status=failed requiring open_rows."""
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ValueError, match="reason"):
        ledger.archive_ceremony("   ")
    assert ledger.read_ledger()["ceremony"]["locked_at"] == "2026-08-10T14:02Z"


def test_archive_ceremony_refuses_when_no_ceremony(tmp_ledger):
    with pytest.raises(ledger.LedgerError, match="no ceremony"):
        ledger.archive_ceremony("aborted the run")


def test_archive_ceremony_archives_and_clears(tmp_ledger):
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("selected", "code review")
    ledger.archive_ceremony("operator aborted", timestamp="2026-08-11T09:00Z")

    data = ledger.read_ledger()
    assert data["ceremony"] == {}
    archived = data["ceremony_history"]["2026-08-11T09:00Z"]
    assert archived["reason"] == "operator aborted"
    assert archived["ceremony"]["locked_at"] == "2026-08-10T14:02Z"
    assert archived["ceremony"]["selected"] == "code review"


def test_archive_ceremony_allows_a_fresh_lock(tmp_ledger):
    """This is the whole point: ABORT-and-re-invoke must be mechanically
    possible, and only through this path."""
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("operator aborted", timestamp="2026-08-11T09:00Z")
    ledger.set_ceremony_field("locked_at", "2026-08-11T09:05Z")
    assert ledger.read_ledger()["ceremony"]["locked_at"] == "2026-08-11T09:05Z"


def test_archive_ceremony_still_refuses_ordinary_rewrite(tmp_ledger):
    """Archiving must not LOOSEN the guard. With a lock present, the
    ordinary set path is refused exactly as before."""
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("operator aborted", timestamp="2026-08-11T09:00Z")
    ledger.set_ceremony_field("locked_at", "2026-08-11T09:05Z")
    with pytest.raises(ledger.LedgerError, match="refusing to rewrite"):
        ledger.set_ceremony_field("locked_at", "2026-08-12T10:00Z")


def test_second_archive_does_not_overwrite_the_first(tmp_ledger):
    """ceremony_history is the audit trail C7 depends on. Two archives must
    BOTH survive -- this is why it is a map, not a list (lists are replaced
    wholesale by the merge policy)."""
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("first abort", timestamp="2026-08-11T09:00Z")
    ledger.set_ceremony_field("locked_at", "2026-08-11T09:05Z")
    ledger.archive_ceremony("second abort", timestamp="2026-08-12T10:00Z")

    history = ledger.read_ledger()["ceremony_history"]
    assert len(history) == 2
    assert history["2026-08-11T09:00Z"]["reason"] == "first abort"
    assert history["2026-08-12T10:00Z"]["reason"] == "second abort"
    assert history["2026-08-11T09:00Z"]["ceremony"]["locked_at"] == "2026-08-10T14:02Z"
    assert history["2026-08-12T10:00Z"]["ceremony"]["locked_at"] == "2026-08-11T09:05Z"


def test_archive_ceremony_colliding_timestamps_both_survive(tmp_ledger):
    """A map keyed by timestamp loses an entry if two archives share a
    timestamp. Append-only must hold even then."""
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("first abort", timestamp="2026-08-11T09:00Z")
    ledger.set_ceremony_field("locked_at", "2026-08-11T09:05Z")
    ledger.archive_ceremony("second abort", timestamp="2026-08-11T09:00Z")

    history = ledger.read_ledger()["ceremony_history"]
    assert len(history) == 2
    reasons = {entry["reason"] for entry in history.values()}
    assert reasons == {"first abort", "second abort"}


def test_archive_ceremony_collision_keys_sort_in_insertion_order(tmp_ledger):
    """The history is read as an ordered audit trail, and every reader that
    sorts it gets lexical order. An unpadded ``#10`` sorts before ``#2``, so
    the trail reads out of sequence past nine collisions in one second."""
    stamp = "2026-08-11T09:00Z"
    for i in range(1, 13):
        ledger.set_ceremony_field("locked_at", f"2026-08-10T14:{i:02d}Z")
        ledger.archive_ceremony(f"abort {i:02d}", timestamp=stamp)

    history = ledger.read_ledger()["ceremony_history"]
    assert len(history) == 12
    by_key = [history[k]["reason"] for k in sorted(history)]
    assert by_key == [f"abort {i:02d}" for i in range(1, 13)]


# ---- wave-discipline -----------------------------------------------------


def test_record_wave_discipline_passed(tmp_ledger):
    ledger.record_wave_discipline("3a", status="passed")
    entry = ledger.wave_discipline_status("3a")
    assert entry["status"] == "passed"


def test_record_wave_discipline_failed_requires_open_rows(tmp_ledger):
    with pytest.raises(ValueError, match="requires at least one open row"):
        ledger.record_wave_discipline("3a", status="failed")


def test_record_wave_discipline_failed_with_open_rows(tmp_ledger):
    ledger.record_wave_discipline(
        "3a", status="failed", open_rows=["W3a-2", "W3a-5"]
    )
    entry = ledger.wave_discipline_status("3a")
    assert entry["status"] == "failed"
    assert entry["open_rows"] == ["W3a-2", "W3a-5"]


def test_record_wave_discipline_na(tmp_ledger):
    """Plans without wave structure record ``status: n_a`` so the
    absence of the check is itself visible at review.
    """
    ledger.record_wave_discipline("plan", status="n_a")
    assert ledger.wave_discipline_status("plan")["status"] == "n_a"


def test_record_wave_discipline_na_records_a_reason(tmp_ledger):
    """The develop skill's prose tells the LLM to write this exact shape.
    'n_a' alone says the check does not apply but not why -- and the point
    of recording n_a is that a later reader can tell 'established as not
    applicable' from 'nobody ran it'."""
    ledger.record_wave_discipline(
        "plan", status="n_a", reason="plan has no wave structure"
    )
    entry = ledger.wave_discipline_status("plan")
    assert entry["status"] == "n_a"
    assert entry["reason"] == "plan has no wave structure"


def test_reason_is_optional_and_omitted_when_absent(tmp_ledger):
    ledger.record_wave_discipline("3a", status="passed")
    assert "reason" not in ledger.wave_discipline_status("3a")


def test_blank_reason_is_not_recorded(tmp_ledger):
    """An empty reason is worse than none: it looks answered."""
    ledger.record_wave_discipline("3a", status="n_a", reason="   ")
    assert "reason" not in ledger.wave_discipline_status("3a")


def test_reason_does_not_make_a_failed_entry_claimable(tmp_ledger):
    """Narrative must never substitute for evidence -- open_rows is still
    what a failed entry is judged on."""
    ledger.record_wave_discipline(
        "3a", status="failed", open_rows=["W3a-2"], reason="blocked on review"
    )
    assert ledger.is_wave_done_claimable("3a") is False
    assert ledger.wave_discipline_status("3a")["open_rows"] == ["W3a-2"]


def test_reason_does_not_satisfy_the_failed_open_rows_requirement(tmp_ledger):
    with pytest.raises(ValueError, match="requires at least one open row"):
        ledger.record_wave_discipline("3a", status="failed", reason="because")


def test_record_wave_discipline_rejects_invalid_status(tmp_ledger):
    with pytest.raises(ValueError, match="status must be one of"):
        ledger.record_wave_discipline("3a", status="maybe")


def test_is_wave_done_claimable_requires_passed(tmp_ledger):
    assert ledger.is_wave_done_claimable("3a") is False
    ledger.record_wave_discipline("3a", status="failed", open_rows=["W3a-2"])
    assert ledger.is_wave_done_claimable("3a") is False
    ledger.record_wave_discipline(
        "3a", status="passed", timestamp="2026-08-10T14:02Z"
    )
    assert ledger.is_wave_done_claimable("3a") is True


def test_record_wave_discipline_preserves_other_waves(tmp_ledger):
    """Deep-merge means recording a check on wave 3b does not erase
    wave 3a's previously recorded status.
    """
    ledger.record_wave_discipline("3a", status="passed")
    ledger.record_wave_discipline("3b", status="passed")
    assert ledger.wave_discipline_status("3a")["status"] == "passed"
    assert ledger.wave_discipline_status("3b")["status"] == "passed"


def test_wave_discipline_passed_after_failed_clears_open_rows(tmp_ledger):
    """open_rows must SHRINK as rows close (module docstring).

    Omitting the key on a passing re-record leaves the previous failure's
    rows in place, because _deep_merge has no delete -- producing a ledger
    that reads "passed" while still listing rows as open.
    """
    ledger.record_wave_discipline("3a", status="failed", open_rows=["W3a-2", "W3a-5"])
    ledger.record_wave_discipline("3a", status="passed")
    entry = ledger.wave_discipline_status("3a")
    assert entry["status"] == "passed"
    assert entry["open_rows"] == []


def test_wave_discipline_na_after_failed_clears_open_rows(tmp_ledger):
    ledger.record_wave_discipline("3a", status="failed", open_rows=["W3a-2"])
    ledger.record_wave_discipline("3a", status="n_a", reason="wave dissolved")
    assert ledger.wave_discipline_status("3a")["open_rows"] == []


def test_wave_discipline_failed_guard_still_fires_after_a_prior_record(tmp_ledger):
    """Writing open_rows unconditionally must not weaken the false-pass
    guard: status=failed with no rows is still refused, and the previously
    recorded entry is left untouched by the refusal.
    """
    ledger.record_wave_discipline("3a", status="failed", open_rows=["W3a-2"])
    with pytest.raises(ValueError, match="requires at least one open row"):
        ledger.record_wave_discipline("3a", status="failed")
    assert ledger.wave_discipline_status("3a")["open_rows"] == ["W3a-2"]


# ---- blockers ------------------------------------------------------------


def test_blocker_rejects_invalid_type(tmp_ledger):
    with pytest.raises(ValueError, match="type must be one of"):
        ledger.record_blocker("B1", blocker_type="vibes")
    assert "blockers" not in ledger.read_ledger()


def test_blocker_open_records_type_and_opened_at(tmp_ledger):
    ledger.record_blocker(
        "B1", blocker_type="decision", description="await operator",
        timestamp="2026-08-11T09:00Z",
    )
    entry = ledger.read_ledger()["blockers"]["B1"]
    assert entry["type"] == "decision"
    assert entry["description"] == "await operator"
    assert entry["opened_at"] == "2026-08-11T09:00Z"
    assert "closed_at" not in entry


def test_blocker_description_is_optional(tmp_ledger):
    ledger.record_blocker("B1", blocker_type="work", timestamp="2026-08-11T09:00Z")
    assert "description" not in ledger.read_ledger()["blockers"]["B1"]


def test_blocker_close_sets_closed_at(tmp_ledger):
    """Closure is a FIELD, not an absence: _deep_merge never deletes, so a
    closed blocker must be distinguishable from an open one by content."""
    ledger.record_blocker(
        "B1", blocker_type="external", timestamp="2026-08-11T09:00Z"
    )
    ledger.record_blocker(
        "B1", blocker_type="external", close=True, timestamp="2026-08-12T10:00Z"
    )
    entry = ledger.read_ledger()["blockers"]["B1"]
    assert entry["closed_at"] == "2026-08-12T10:00Z"
    assert entry["opened_at"] == "2026-08-11T09:00Z"
    assert entry["type"] == "external"


def test_blocker_close_nonexistent_fails(tmp_ledger):
    with pytest.raises(ledger.LedgerError, match="no open blocker"):
        ledger.record_blocker("B9", blocker_type="work", close=True)


def test_blocker_close_does_not_require_a_type(tmp_ledger):
    """Closing consumes no type: ``record_blocker`` writes only ``closed_at``.
    Demanding a type to close means the caller must restate a value the call
    ignores -- and a wrong restatement was accepted silently."""
    ledger.record_blocker("B1", blocker_type="work", timestamp="2026-08-11T09:00Z")
    ledger.record_blocker("B1", close=True, timestamp="2026-08-12T10:00Z")
    entry = ledger.read_ledger()["blockers"]["B1"]
    assert entry["closed_at"] == "2026-08-12T10:00Z"
    assert entry["type"] == "work"


def test_blocker_open_without_type_is_refused(tmp_ledger):
    """Opening is the operation that CONSUMES the type, so it still needs one --
    and the refusal must say so rather than defaulting to a kind nobody chose."""
    with pytest.raises(ValueError, match="requires --type"):
        ledger.record_blocker("B1", timestamp="2026-08-11T09:00Z")
    assert "blockers" not in ledger.read_ledger()


def test_blocker_close_with_contradicting_type_is_refused(tmp_ledger):
    """The proven defect: ``--type work --close`` on a blocker opened as
    ``decision`` succeeded and discarded the flag. Either the caller has the
    wrong blocker or the wrong type; both are errors, neither is silent."""
    ledger.record_blocker("B1", blocker_type="decision", timestamp="2026-08-11T09:00Z")
    with pytest.raises(ledger.LedgerError, match="type mismatch"):
        ledger.record_blocker(
            "B1", blocker_type="work", close=True, timestamp="2026-08-12T10:00Z"
        )
    assert "closed_at" not in ledger.read_ledger()["blockers"]["B1"]


def test_blocker_close_without_type_on_nonexistent_id_fails(tmp_ledger):
    with pytest.raises(ledger.LedgerError, match="no open blocker"):
        ledger.record_blocker("B9", close=True)


def test_two_blockers_coexist(tmp_ledger):
    """Deep-merge check: recording B2 must not erase B1."""
    ledger.record_blocker("B1", blocker_type="decision", timestamp="2026-08-11T09:00Z")
    ledger.record_blocker("B2", blocker_type="work", timestamp="2026-08-11T09:30Z")
    blockers = ledger.read_ledger()["blockers"]
    assert blockers["B1"]["type"] == "decision"
    assert blockers["B2"]["type"] == "work"


def test_closing_one_blocker_leaves_the_other_open(tmp_ledger):
    ledger.record_blocker("B1", blocker_type="decision", timestamp="2026-08-11T09:00Z")
    ledger.record_blocker("B2", blocker_type="work", timestamp="2026-08-11T09:30Z")
    ledger.record_blocker(
        "B1", blocker_type="decision", close=True, timestamp="2026-08-12T10:00Z"
    )
    blockers = ledger.read_ledger()["blockers"]
    assert blockers["B1"]["closed_at"] == "2026-08-12T10:00Z"
    assert "closed_at" not in blockers["B2"]


# ---- group-gate ----------------------------------------------------------


def test_group_gate_failed_requires_open_findings(tmp_ledger):
    """Mirrors the wave-discipline false-pass guard: a failed record with
    nothing to fix is indistinguishable from a pass."""
    with pytest.raises(ValueError, match="requires at least one open finding"):
        ledger.record_group_gate("G1", status="failed")
    assert "groups" not in ledger.read_ledger()


def test_group_gate_passed_round_trips(tmp_ledger):
    ledger.record_group_gate(
        "G1", status="passed", gates=["4.4", "4.5"], timestamp="2026-08-11T09:00Z"
    )
    entry = ledger.read_ledger()["groups"]["G1"]["gate_stack"]
    assert entry["status"] == "passed"
    assert entry["gates"] == ["4.4", "4.5"]
    assert entry["timestamp"] == "2026-08-11T09:00Z"
    assert entry["open_findings"] == []


def test_group_gate_failed_with_open_findings(tmp_ledger):
    ledger.record_group_gate("G1", status="failed", open_findings=["F1", "F2"])
    entry = ledger.read_ledger()["groups"]["G1"]["gate_stack"]
    assert entry["status"] == "failed"
    assert entry["open_findings"] == ["F1", "F2"]


def test_group_gate_rejects_invalid_status(tmp_ledger):
    with pytest.raises(ValueError, match="status must be one of"):
        ledger.record_group_gate("G1", status="maybe")


def test_group_gate_na(tmp_ledger):
    ledger.record_group_gate("G1", status="n_a")
    assert ledger.read_ledger()["groups"]["G1"]["gate_stack"]["status"] == "n_a"


def test_group_gate_passed_after_failed_clears_open_findings(tmp_ledger):
    """The per-group counterpart of the open_rows shrink contract.

    Re-recording G1 as passed after a failed run must not leave the
    failure's findings behind: a passed gate that still carries open
    findings is precisely the false-pass this recorder exists to close.
    """
    ledger.record_group_gate("G1", status="failed", open_findings=["F1", "F2"])
    ledger.record_group_gate("G1", status="passed", gates=["4.4", "4.5"])
    entry = ledger.read_ledger()["groups"]["G1"]["gate_stack"]
    assert entry["status"] == "passed"
    assert entry["open_findings"] == []


def test_group_gate_na_after_failed_clears_open_findings(tmp_ledger):
    ledger.record_group_gate("G1", status="failed", open_findings=["F1"])
    ledger.record_group_gate("G1", status="n_a")
    assert ledger.read_ledger()["groups"]["G1"]["gate_stack"]["open_findings"] == []


def test_group_gate_failed_guard_still_fires_after_a_prior_record(tmp_ledger):
    """Writing open_findings unconditionally must not weaken the
    false-pass guard, and a refusal must leave the stored entry intact.
    """
    ledger.record_group_gate("G1", status="failed", open_findings=["F1"])
    with pytest.raises(ValueError, match="requires at least one open finding"):
        ledger.record_group_gate("G1", status="failed")
    entry = ledger.read_ledger()["groups"]["G1"]["gate_stack"]
    assert entry["open_findings"] == ["F1"]


def test_two_groups_coexist(tmp_ledger):
    ledger.record_group_gate("G1", status="passed")
    ledger.record_group_gate("G2", status="passed")
    groups = ledger.read_ledger()["groups"]
    assert groups["G1"]["gate_stack"]["status"] == "passed"
    assert groups["G2"]["gate_stack"]["status"] == "passed"


# ---- CLI -----------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.allow("subprocess")
def test_cli_show_empty(tmp_ledger):
    proc = _run_cli("show")
    assert proc.returncode == 0
    assert proc.stdout.strip() == "{}"


@pytest.mark.allow("subprocess")
def test_cli_set_top_level(tmp_ledger):
    proc = _run_cli("set", "current_phase", "4")
    assert proc.returncode == 0
    assert "set current_phase" in proc.stdout
    data = json.loads(tmp_ledger.read_text())
    assert data["current_phase"] == "4"


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_field(tmp_ledger):
    proc = _run_cli("set", "ceremony.selected", "code review")
    assert proc.returncode == 0
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["selected"] == "code review"


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_unknown_field_errors(tmp_ledger):
    proc = _run_cli("set", "ceremony.bogus_field", "x")
    assert proc.returncode == 2
    assert "unknown ceremony field" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_gate_position(tmp_ledger):
    """The proven-broken invocation from the finding: this exited 2."""
    proc = _run_cli("set", "ceremony.gate_position", "per_group")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["gate_position"] == "per_group"


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_gate_position_invalid_value_errors(tmp_ledger):
    proc = _run_cli("set", "ceremony.gate_position", "per_wave")
    assert proc.returncode != 0
    assert "per_task" in proc.stderr and "per_group" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_gate_position_rewrite_after_lock_refused(tmp_ledger):
    """The CLI must not be a hole through the gate_position lock either."""
    _run_cli("set", "ceremony.gate_position", "per_task")
    _run_cli("set", "ceremony.locked_at", "2026-08-10T14:02Z")
    proc = _run_cli("set", "ceremony.gate_position", "per_group")
    assert proc.returncode == 1
    assert "refusing to rewrite" in proc.stderr
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["gate_position"] == "per_task"


@pytest.mark.allow("subprocess")
def test_cli_group_gate_passed_after_failed_clears_open_findings(tmp_ledger):
    _run_cli("group-gate", "G1", "--status", "failed", "--open-findings", "F1,F2")
    proc = _run_cli("group-gate", "G1", "--status", "passed")
    assert proc.returncode == 0, proc.stderr
    entry = json.loads(tmp_ledger.read_text())["groups"]["G1"]["gate_stack"]
    assert entry["status"] == "passed"
    assert entry["open_findings"] == []


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_locked_at_first_time_succeeds(tmp_ledger):
    proc = _run_cli("set", "ceremony.locked_at", "2026-08-10T14:02Z")
    assert proc.returncode == 0
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["locked_at"] == "2026-08-10T14:02Z"


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_locked_at_rewrite_refused(tmp_ledger):
    """The CLI must not be a hole through the lock.

    ``set ceremony.locked_at`` goes through ``set_ceremony_field``, so
    the same refusal the library enforces applies here -- and the
    on-disk value stays at the original lock.
    """
    _run_cli("set", "ceremony.locked_at", "2026-08-10T14:02Z")
    proc = _run_cli("set", "ceremony.locked_at", "2026-08-11T09:00Z")
    assert proc.returncode == 1
    assert "refusing to rewrite" in proc.stderr
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["locked_at"] == "2026-08-10T14:02Z"


@pytest.mark.allow("subprocess")
def test_cli_archive_ceremony_requires_reason(tmp_ledger):
    _run_cli("set", "ceremony.locked_at", "2026-08-10T14:02Z")
    proc = _run_cli("archive-ceremony", "--reason", "  ")
    assert proc.returncode != 0
    assert "reason" in proc.stderr
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["locked_at"] == "2026-08-10T14:02Z"


@pytest.mark.allow("subprocess")
def test_cli_archive_ceremony_clears_and_allows_relock(tmp_ledger):
    _run_cli("set", "ceremony.locked_at", "2026-08-10T14:02Z")
    proc = _run_cli(
        "archive-ceremony", "--reason", "operator aborted",
        "--timestamp", "2026-08-11T09:00Z",
    )
    assert proc.returncode == 0, proc.stderr

    relock = _run_cli("set", "ceremony.locked_at", "2026-08-11T09:05Z")
    assert relock.returncode == 0, relock.stderr
    data = json.loads(tmp_ledger.read_text())
    assert data["ceremony"]["locked_at"] == "2026-08-11T09:05Z"
    assert (
        data["ceremony_history"]["2026-08-11T09:00Z"]["ceremony"]["locked_at"]
        == "2026-08-10T14:02Z"
    )


@pytest.mark.allow("subprocess")
def test_cli_wave_discipline_passed_claimable(tmp_ledger):
    proc = _run_cli("wave-discipline", "3a", "--status", "passed")
    assert proc.returncode == 0
    assert "ALLOWED" in proc.stdout


@pytest.mark.allow("subprocess")
def test_cli_wave_discipline_failed_refused(tmp_ledger):
    proc = _run_cli(
        "wave-discipline", "3a", "--status", "failed", "--open-rows", "W3a-2"
    )
    assert proc.returncode == 0
    assert "REFUSED" in proc.stdout


@pytest.mark.allow("subprocess")
def test_cli_wave_discipline_na_with_reason(tmp_ledger):
    """The documented invocation from skills/develop/SKILL.md must actually
    work from the CLI -- prose describing a flag that does not exist is the
    defect this finding raised."""
    proc = _run_cli(
        "wave-discipline", "plan",
        "--status", "n_a",
        "--reason", "plan has no wave structure",
    )
    assert proc.returncode == 0
    entry = json.loads(tmp_ledger.read_text())["waves"]["plan"]["section_24_6_check"]
    assert entry == {
        "status": "n_a",
        "reason": "plan has no wave structure",
        "open_rows": [],
    }


@pytest.mark.allow("subprocess")
def test_cli_wave_discipline_failed_without_open_rows_errors(tmp_ledger):
    proc = _run_cli("wave-discipline", "3a", "--status", "failed")
    assert proc.returncode == 2
    assert "requires at least one open row" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_blocker_open_then_close(tmp_ledger):
    proc = _run_cli(
        "blocker", "B1", "--type", "decision",
        "--description", "await operator", "--timestamp", "2026-08-11T09:00Z",
    )
    assert proc.returncode == 0, proc.stderr

    proc = _run_cli(
        "blocker", "B1", "--type", "decision", "--close",
        "--timestamp", "2026-08-12T10:00Z",
    )
    assert proc.returncode == 0, proc.stderr
    entry = json.loads(tmp_ledger.read_text())["blockers"]["B1"]
    assert entry["opened_at"] == "2026-08-11T09:00Z"
    assert entry["closed_at"] == "2026-08-12T10:00Z"


@pytest.mark.allow("subprocess")
def test_cli_blocker_close_without_type(tmp_ledger):
    """The documented invocation in commands/feature-implement-execute.md:
    ``blocker <id> --close``. It exited 2 on argparse before this fix."""
    proc = _run_cli(
        "blocker", "B1", "--type", "decision", "--timestamp", "2026-08-11T09:00Z"
    )
    assert proc.returncode == 0, proc.stderr

    proc = _run_cli("blocker", "B1", "--close", "--timestamp", "2026-08-12T10:00Z")
    assert proc.returncode == 0, proc.stderr
    entry = json.loads(tmp_ledger.read_text())["blockers"]["B1"]
    assert entry["closed_at"] == "2026-08-12T10:00Z"
    assert entry["type"] == "decision"


@pytest.mark.allow("subprocess")
def test_cli_blocker_open_without_type_errors(tmp_ledger):
    proc = _run_cli("blocker", "B1", "--description", "await operator")
    assert proc.returncode == 2
    assert "requires --type" in proc.stderr
    assert not tmp_ledger.exists()


@pytest.mark.allow("subprocess")
def test_cli_blocker_close_with_contradicting_type_errors(tmp_ledger):
    _run_cli("blocker", "B1", "--type", "decision", "--timestamp", "2026-08-11T09:00Z")
    proc = _run_cli("blocker", "B1", "--type", "work", "--close")
    assert proc.returncode == 2
    assert "type mismatch" in proc.stderr
    assert "closed_at" not in json.loads(tmp_ledger.read_text())["blockers"]["B1"]


@pytest.mark.allow("subprocess")
def test_cli_blocker_rejects_invalid_type(tmp_ledger):
    proc = _run_cli("blocker", "B1", "--type", "vibes")
    assert proc.returncode != 0
    assert "decision" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_blocker_close_nonexistent_errors(tmp_ledger):
    proc = _run_cli("blocker", "B9", "--type", "work", "--close")
    assert proc.returncode == 2
    assert "no open blocker" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_group_gate_passed(tmp_ledger):
    proc = _run_cli(
        "group-gate", "G1", "--status", "passed",
        "--gates", "4.4,4.5,4.5.1", "--timestamp", "2026-08-11T09:00Z",
    )
    assert proc.returncode == 0, proc.stderr
    entry = json.loads(tmp_ledger.read_text())["groups"]["G1"]["gate_stack"]
    assert entry["status"] == "passed"
    assert entry["gates"] == ["4.4", "4.5", "4.5.1"]


@pytest.mark.allow("subprocess")
def test_cli_group_gate_failed_without_open_findings_errors(tmp_ledger):
    proc = _run_cli("group-gate", "G1", "--status", "failed")
    assert proc.returncode == 2
    assert "requires at least one open finding" in proc.stderr


# ---- standalone invocation (no `spellbook` package importable) -----------


@pytest.mark.allow("subprocess")
def test_cli_runs_standalone_without_spellbook_package(tmp_path):
    """The module docstring and every doc say invoke this directly:
    ``python3 scripts/develop_gate_ledger.py <cmd>``. That must work even
    when the ``spellbook`` package is not importable -- a clean shell
    without the venv or PYTHONPATH set, which is exactly how the docs
    describe running it.

    Reproduces by scrubbing PYTHONPATH from the subprocess env and running
    from a cwd outside the repo, so neither an inherited PYTHONPATH nor
    implicit ``sys.path[0]`` (script directory on the module search path)
    can rescue an accidental `spellbook` import.
    """
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()

    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SPELLBOOK_DEV_DIR": str(dev_dir)}

    # -S disables site-packages processing, which is what makes
    # `spellbook` importable from ``sys.executable`` even outside the
    # repo (the venv's editable install registers a .pth file that adds
    # the repo root to sys.path unconditionally). Combined with a cwd
    # outside the repo (so `sys.path[0]` cannot rescue the import
    # implicitly) and no PYTHONPATH, this reproduces "a clean shell
    # without the venv or PYTHONPATH" from the documented invocation.
    proc = subprocess.run(
        [sys.executable, "-S", str(SCRIPT_PATH), "show"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(outside_cwd),
        env=env,
    )
    assert proc.returncode == 0, (
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert proc.stdout.strip() == "{}"


def test_fallback_encode_cwd_matches_real_implementation():
    """Anti-drift guard: the fallback ``encode_cwd`` (used when the
    ``spellbook`` package is not importable, see the module-level
    try/except import) must byte-match ``spellbook.core.path_utils.encode_cwd``
    for every path this script could receive. Without this test the
    fallback is free to rot out of sync with the real implementation.
    """
    from spellbook.core.path_utils import encode_cwd as real_encode_cwd

    fallback_encode_cwd = ledger._fallback_encode_cwd

    paths = [
        "/Users/alice/Development/spellbook",
        "/Users/alice/Development/spellbook/",
        "/",
        "/a",
        "a/b/c",
        "C:\\Users\\alice\\project",
        "/Users/alice/Development//spellbook",
        "",
    ]
    for path in paths:
        expected = real_encode_cwd(path, resolve_git_root=False)
        actual = fallback_encode_cwd(path, resolve_git_root=False)
        assert actual == expected, f"path={path!r}: real={expected!r} fallback={actual!r}"


def _init_temp_repo(root: Path) -> None:
    """Create a self-contained git repo at ``root`` with one commit.

    Self-contained on purpose: a worktree of the spellbook checkout would
    register itself in the operator's own repo. This repo is created and
    discarded inside tmp_path.
    """
    root.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(root),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    (root / "f.txt").write_text("x", encoding="utf-8")
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "f.txt"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=root, env=env, check=True, capture_output=True, timeout=30)


@pytest.mark.allow("subprocess")
def test_fallback_encode_cwd_matches_real_implementation_with_git_root(tmp_path):
    """The anti-drift guard on the branch that PRODUCTION actually takes.

    ``default_ledger_path()`` calls ``encode_cwd(os.getcwd())`` -- the
    DEFAULT ``resolve_git_root=True``. That path is ~35 lines of duplicated
    ``git worktree list --porcelain`` parsing plus a ``--show-toplevel``
    fallback, and it carries all of the drift risk. Checking only
    ``resolve_git_root=False`` leaves it uncovered: a corrupted git-root
    branch left the False-only guard green.
    """
    from spellbook.core.path_utils import encode_cwd as real_encode_cwd

    fallback_encode_cwd = ledger._fallback_encode_cwd

    repo_root = Path(__file__).resolve().parents[2]

    temp_repo = tmp_path / "repo"
    _init_temp_repo(temp_repo)
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "side", str(worktree)],
        cwd=temp_repo,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": str(temp_repo),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
        check=True,
        capture_output=True,
        timeout=30,
    )

    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    paths = [
        str(repo_root),                      # the real repo root
        str(repo_root / "scripts"),          # a subdirectory of it
        str(temp_repo),                      # a freshly created repo
        str(worktree),                       # a real linked worktree
        str(not_a_repo),                     # not a git repo at all
    ]
    for path in paths:
        expected = real_encode_cwd(path)
        actual = fallback_encode_cwd(path)
        assert actual == expected, f"path={path!r}: real={expected!r} fallback={actual!r}"

    # Independent of agreement: the git-root branch must actually RESOLVE.
    # Two implementations that drifted the same way would agree above and
    # still be wrong; these assert the resolution happened at all.
    assert fallback_encode_cwd(str(repo_root / "scripts")) == fallback_encode_cwd(
        str(repo_root)
    ), "a subdirectory must resolve to the repo root"
    assert fallback_encode_cwd(str(worktree)) == fallback_encode_cwd(
        str(temp_repo)
    ), "a linked worktree must resolve to the main worktree"
    assert fallback_encode_cwd(str(not_a_repo)) == fallback_encode_cwd(
        str(not_a_repo), resolve_git_root=False
    ), "a non-repo path must pass through unchanged"
