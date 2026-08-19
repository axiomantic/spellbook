"""Tests for scripts/develop_gate_ledger.py.

The ledger is the persistent state file the develop skill uses to
track ceremony selection, gate completion, and wave-discipline checks.
These tests cover the merge contract, the locked_at lock rule, the
wave-discipline recording, and the CLI surface -- not the develop
skill's usage of the ledger, which is exercised by an actual develop
run, not a Python test.
"""

import argparse
import ast
import json
import logging
import os
import re
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


# ---- de-escalation guards ------------------------------------------------
#
# The lock is a FLOOR: escalation stays legal at any time, de-escalation is
# refused. Guarding locked_at and gate_position alone left the three fields
# that actually carry the gate set unguarded, so the <CRITICAL> "a mid-run
# request to drop a gate is REFUSED" was prose with no mechanism behind it.


def test_set_ceremony_selected_shrink_after_lock_refused(tmp_ledger):
    """Dropping a gate from the locked set is the de-escalation the skill
    forbids outright. archive-ceremony is the only route to a smaller set.
    """
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage\ntdd-first")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to narrow"):
        ledger.set_ceremony_field("selected", "code review")
    assert ledger.read_ledger()["ceremony"]["selected"] == (
        "code review\ngreen-mirage\ntdd-first"
    )


def test_set_ceremony_selected_growth_after_lock_allowed(tmp_ledger):
    """Escalation must stay legal -- the lock is a floor, not a ceiling."""
    ledger.set_ceremony_field("selected", "code review")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    assert ledger.read_ledger()["ceremony"]["selected"] == (
        "code review\ngreen-mirage"
    )


def test_set_ceremony_selected_same_value_after_lock_succeeds(tmp_ledger):
    """Idempotent re-assertion drops nothing, so it is not a narrowing --
    mirrors the gate_position guard's same-value allowance.
    """
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    assert ledger.read_ledger()["ceremony"]["selected"] == (
        "code review\ngreen-mirage"
    )


def test_set_ceremony_selected_reorder_after_lock_succeeds(tmp_ledger):
    """The comparison is over the SET of gates. Order carries no meaning in
    this field, so a reordering drops nothing and must not be refused.
    """
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("selected", "green-mirage\ncode review")
    assert ledger.read_ledger()["ceremony"]["selected"] == (
        "green-mirage\ncode review"
    )


def test_set_ceremony_selected_blank_lines_ignored_after_lock(tmp_ledger):
    """An element is one non-blank stripped line. Whitespace churn is not a
    gate being dropped.
    """
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("selected", "  code review  \n\n green-mirage \n")
    assert "green-mirage" in ledger.read_ledger()["ceremony"]["selected"]


def test_set_ceremony_selected_first_write_after_lock_succeeds(tmp_ledger):
    """The guard refuses a NARROWING, not a first write. With no prior value
    there is nothing to drop, and this is the original selection being
    recorded -- the shape the archive test at set-then-lock order relies on.
    """
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("selected", "code review")
    assert ledger.read_ledger()["ceremony"]["selected"] == "code review"


def test_selected_narrowable_again_after_archive_ceremony(tmp_ledger):
    """archive-ceremony clears the lock, so a fresh Phase 0 may legitimately
    select a SMALLER set. This is the sanctioned de-escalation route the
    refusal message points at, and it must actually work.
    """
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("operator aborted; re-selecting")
    ledger.set_ceremony_field("selected", "code review")
    assert ledger.read_ledger()["ceremony"]["selected"] == "code review"


def test_set_ceremony_selected_shrink_before_lock_allowed(tmp_ledger):
    """Before the lock, Phase 0 is still choosing. The guard is conditioned
    on locked_at, not on the field having a prior value.
    """
    ledger.set_ceremony_field("selected", "code review\ngreen-mirage")
    ledger.set_ceremony_field("selected", "code review")
    assert ledger.read_ledger()["ceremony"]["selected"] == "code review"


def test_set_ceremony_core_shrink_after_lock_refused(tmp_ledger):
    """`core` records what was never on the menu. Dropping from it is a
    stronger de-escalation than dropping from `selected`: it retroactively
    claims a non-negotiable gate was optional all along.
    """
    ledger.set_ceremony_field("core", "code review\niron law\ngreen-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to narrow"):
        ledger.set_ceremony_field("core", "code review")
    assert ledger.read_ledger()["ceremony"]["core"] == (
        "code review\niron law\ngreen-mirage"
    )


def test_set_ceremony_core_growth_after_lock_allowed(tmp_ledger):
    ledger.set_ceremony_field("core", "code review")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("core", "code review\niron law")
    assert ledger.read_ledger()["ceremony"]["core"] == "code review\niron law"


def test_set_ceremony_core_same_value_after_lock_succeeds(tmp_ledger):
    ledger.set_ceremony_field("core", "code review\niron law")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("core", "code review\niron law")
    assert ledger.read_ledger()["ceremony"]["core"] == "code review\niron law"


def test_set_ceremony_core_reorder_after_lock_succeeds(tmp_ledger):
    ledger.set_ceremony_field("core", "code review\niron law")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("core", "iron law\ncode review")
    assert ledger.read_ledger()["ceremony"]["core"] == "iron law\ncode review"


def test_set_ceremony_core_first_write_after_lock_succeeds(tmp_ledger):
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("core", "code review")
    assert ledger.read_ledger()["ceremony"]["core"] == "code review"


def test_core_narrowable_again_after_archive_ceremony(tmp_ledger):
    ledger.set_ceremony_field("core", "code review\niron law")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("operator aborted; re-selecting")
    ledger.set_ceremony_field("core", "code review")
    assert ledger.read_ledger()["ceremony"]["core"] == "code review"


def test_set_ceremony_declined_growth_after_lock_refused(tmp_ledger):
    """`declined` runs the OTHER way. Adding to it after the lock removes a
    gate from the run by the back door -- the same de-escalation as dropping
    from `selected`, dressed as a record of a decision already made.
    """
    ledger.set_ceremony_field("declined", "green-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to widen"):
        ledger.set_ceremony_field("declined", "green-mirage\ncode review")
    assert ledger.read_ledger()["ceremony"]["declined"] == "green-mirage"


def test_set_ceremony_declined_shrink_after_lock_allowed(tmp_ledger):
    """Promotion (declined -> selected) is an escalation and is legal at any
    time, so `declined` losing an element must stay permitted.
    """
    ledger.set_ceremony_field("declined", "green-mirage\ntdd-first")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("declined", "green-mirage")
    assert ledger.read_ledger()["ceremony"]["declined"] == "green-mirage"


def test_set_ceremony_declined_same_value_after_lock_succeeds(tmp_ledger):
    ledger.set_ceremony_field("declined", "green-mirage\ntdd-first")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("declined", "green-mirage\ntdd-first")
    assert ledger.read_ledger()["ceremony"]["declined"] == (
        "green-mirage\ntdd-first"
    )


def test_set_ceremony_declined_reorder_after_lock_succeeds(tmp_ledger):
    ledger.set_ceremony_field("declined", "green-mirage\ntdd-first")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.set_ceremony_field("declined", "tdd-first\ngreen-mirage")
    assert ledger.read_ledger()["ceremony"]["declined"] == (
        "tdd-first\ngreen-mirage"
    )


def test_set_ceremony_declined_first_write_after_lock_refused(tmp_ledger):
    """The first-write allowance is correct for the GROW fields and wrong for
    the SHRINK field. A ceremony that locks with nothing declined is the
    DEFAULT path (`source = "default_full"`), so a first write of `declined`
    after the lock is not a Phase-0 record catching up -- it is a gate being
    dropped from a running ceremony, which is exactly what the guard exists
    to refuse.
    """
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to widen"):
        ledger.set_ceremony_field("declined", "green-mirage")
    assert "declined" not in ledger.read_ledger()["ceremony"]


def test_set_ceremony_declined_growth_from_empty_string_after_lock_refused(
    tmp_ledger,
):
    """An explicitly-empty `declined` is the default path written out in full.
    It must refuse growth exactly as an absent one does; otherwise the bypass
    survives for every ceremony that records its empty decline set honestly.
    """
    ledger.set_ceremony_field("declined", "")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    with pytest.raises(ledger.LedgerError, match="refusing to widen"):
        ledger.set_ceremony_field("declined", "green-mirage")
    assert ledger.read_ledger()["ceremony"]["declined"] == ""


def test_declined_growable_again_after_archive_ceremony(tmp_ledger):
    ledger.set_ceremony_field("declined", "green-mirage")
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.archive_ceremony("operator aborted; re-selecting")
    ledger.set_ceremony_field("declined", "green-mirage\ncode review")
    assert ledger.read_ledger()["ceremony"]["declined"] == (
        "green-mirage\ncode review"
    )


# ---- a blank locked_at is still a lock -----------------------------------
#
# The module's contract is "its presence IS the lock", but every guard tested
# the value for TRUTHINESS. A ledger holding `locked_at: ""` therefore read as
# unlocked to all four guards at once -- one write became a master key. The
# value space is reachable by hand-edit (this module documents itself as
# directly readable) and, before the write-time guard below, through the CLI.


def _plant_ceremony(path, ceremony):
    """Write a ceremony object straight to disk, bypassing every guard.

    A hand-edited ledger is the state these guards must survive, so the
    fixture has to be able to produce shapes the writers now refuse.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ceremony": ceremony}), encoding="utf-8")


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_blank_locked_at_still_refuses_narrowing_selected(tmp_ledger, blank):
    _plant_ceremony(tmp_ledger, {"locked_at": blank, "selected": "a\nb"})
    with pytest.raises(ledger.LedgerError, match="refusing to narrow"):
        ledger.set_ceremony_field("selected", "a")
    assert ledger.read_ledger()["ceremony"]["selected"] == "a\nb"


def test_blank_locked_at_still_refuses_narrowing_core(tmp_ledger):
    _plant_ceremony(tmp_ledger, {"locked_at": "", "core": "a\nb"})
    with pytest.raises(ledger.LedgerError, match="refusing to narrow"):
        ledger.set_ceremony_field("core", "a")


def test_blank_locked_at_still_refuses_widening_declined(tmp_ledger):
    _plant_ceremony(tmp_ledger, {"locked_at": "", "declined": ""})
    with pytest.raises(ledger.LedgerError, match="refusing to widen"):
        ledger.set_ceremony_field("declined", "green-mirage")


def test_blank_locked_at_still_refuses_gate_position_rewrite(tmp_ledger):
    _plant_ceremony(tmp_ledger, {"locked_at": "", "gate_position": "per_task"})
    with pytest.raises(ledger.LedgerError, match="refusing to rewrite"):
        ledger.set_ceremony_field("gate_position", "per_group")
    assert ledger.read_ledger()["ceremony"]["gate_position"] == "per_task"


def test_blank_locked_at_still_refuses_a_locked_at_rewrite(tmp_ledger):
    """Otherwise the master key also overwrites the lock stamp itself,
    leaving a ledger that looks properly locked at a time of the writer's
    choosing.
    """
    _plant_ceremony(tmp_ledger, {"locked_at": ""})
    with pytest.raises(ledger.LedgerError, match="refusing to rewrite"):
        ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")


def test_null_locked_at_is_not_a_lock(tmp_ledger):
    """``null`` is JSON's absent value, not a stamp. It must read as UNLOCKED,
    the same as a missing key -- otherwise a ledger that never reached Phase 0
    would refuse the writes Phase 0 exists to make.
    """
    _plant_ceremony(tmp_ledger, {"locked_at": None, "selected": "a\nb"})
    ledger.set_ceremony_field("selected", "a")
    assert ledger.read_ledger()["ceremony"]["selected"] == "a"


@pytest.mark.parametrize("nonstring", [0, False])
def test_nonstring_locked_at_is_still_a_lock(tmp_ledger, nonstring):
    """Present but falsy. Only a hand-edit produces these, and the honest
    reading of a malformed stamp is "locked, and in a shape to repair via
    archive-ceremony" -- not "open season".
    """
    _plant_ceremony(tmp_ledger, {"locked_at": nonstring, "selected": "a\nb"})
    with pytest.raises(ledger.LedgerError, match="refusing to narrow"):
        ledger.set_ceremony_field("selected", "a")


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_set_ceremony_locked_at_rejects_a_blank_stamp(tmp_ledger, blank):
    """A lock whose value is meaningless is a lock in name only. ValueError,
    not LedgerError: the stored state is fine, the CALLER asked for a value
    the ledger does not accept -- the same split as the gate_position and
    unknown-field guards above.
    """
    with pytest.raises(ValueError, match="non-blank"):
        ledger.set_ceremony_field("locked_at", blank)
    assert "locked_at" not in ledger.read_ledger().get("ceremony", {})


def test_set_scalar_rejects_dotted_field(tmp_ledger):
    """Use set_ceremony_field for ceremony.* -- set_scalar is for the
    top level only, and a dotted argument is almost certainly a bug.
    """
    with pytest.raises(ValueError, match="top-level fields"):
        ledger.set_scalar("ceremony.selected", "x")


# ---- structured-field bare-write refusal ---------------------------------
#
# The lock guards in set_ceremony_field are only worth what the narrowest
# route to the same bytes enforces. A bare `set ceremony <value>` replaces
# the whole object -- locked_at included -- without ever reaching those
# guards. The same shape exists for every top-level field a dedicated
# recorder owns, so these tests pin the refusal for all of them.


def _seed_every_structured_field():
    """Populate each guarded top-level field through its legitimate route."""
    ledger.set_ceremony_field("locked_at", "2026-08-10T14:02Z")
    ledger.record_blocker("B1", blocker_type="decision", description="seed")
    ledger.record_wave_discipline("3a", status="passed")
    ledger.record_group_gate("G1", status="passed", gates=["4.4"])
    ledger.record_dispatch(subagent_type="impl")


@pytest.mark.parametrize(
    "field",
    ["ceremony", "ceremony_history", "blockers", "waves", "groups", "dispatches"],
)
def test_set_scalar_refuses_structured_field(tmp_ledger, field):
    """A warning is not a refusal. Replacing one of these objects with a
    scalar is never a legitimate operation: it discards an audit trail that
    exists precisely to prove a gate ran."""
    _seed_every_structured_field()
    ledger.archive_ceremony("seed the history")
    ledger.set_ceremony_field("locked_at", "2026-08-12T09:00Z")
    before = ledger.read_ledger()[field]

    with pytest.raises(ValueError, match="dedicated recorder"):
        ledger.set_scalar(field, "obliterated")

    assert ledger.read_ledger()[field] == before


@pytest.mark.parametrize(
    "field",
    ["ceremony", "ceremony_history", "blockers", "waves", "groups", "dispatches"],
)
def test_set_scalar_refuses_structured_field_even_when_absent(tmp_ledger, field):
    """The refusal is about the ROUTE, not about what happens to be stored.
    Seeding the scalar first and letting a recorder trip over it later would
    just move the failure somewhere less legible."""
    with pytest.raises(ValueError, match="dedicated recorder"):
        ledger.set_scalar(field, "obliterated")
    assert field not in ledger.read_ledger()


def test_set_scalar_refuses_ceremony_without_a_lock(tmp_ledger):
    """Not conditioned on locked_at: collapsing the ceremony object to a
    scalar is never legitimate, and a guard that only fires after the lock
    leaves Phase 0 itself unprotected."""
    ledger.set_ceremony_field("selected", "code review")
    assert "locked_at" not in ledger.read_ledger()["ceremony"]

    with pytest.raises(ValueError, match="dedicated recorder"):
        ledger.set_scalar("ceremony", "obliterated")

    assert ledger.read_ledger()["ceremony"]["selected"] == "code review"


def test_set_scalar_still_writes_plain_scalar_fields(tmp_ledger):
    """The refusal must not swallow the fields `set` exists to write."""
    for field, value in (
        ("current_phase", "4"),
        ("plan_pointer", "/tmp/plan.md"),
        ("remaining_gates", "code review\ngreen-mirage"),
    ):
        ledger.set_scalar(field, value)
    data = ledger.read_ledger()
    assert data["current_phase"] == "4"
    assert data["plan_pointer"] == "/tmp/plan.md"
    assert data["remaining_gates"] == "code review\ngreen-mirage"


def test_set_scalar_allows_need_flags(tmp_ledger):
    """`need_flags` is an object in the documented shape but has NO dedicated
    recorder. Refusing it would strand the field with no route at all, so it
    stays writable -- the refusal covers fields that have somewhere else to go."""
    ledger.set_scalar("need_flags", {"needs_research": True})
    assert ledger.read_ledger()["need_flags"] == {"needs_research": True}


def test_structured_routes_still_work_after_the_guard(tmp_ledger):
    """Each guarded field must remain writable through its own recorder."""
    _seed_every_structured_field()
    data = ledger.read_ledger()
    assert data["ceremony"]["locked_at"] == "2026-08-10T14:02Z"
    assert data["blockers"]["B1"]["type"] == "decision"
    assert data["waves"]["3a"]["section_24_6_check"]["status"] == "passed"
    assert data["groups"]["G1"]["gate_stack"]["status"] == "passed"
    assert len(data["dispatches"]) == 1
    ledger.archive_ceremony("operator aborted")
    assert len(ledger.read_ledger()["ceremony_history"]) == 1


# ---- _STRUCTURED_FIELD_ROUTES drift ---------------------------------------
#
# The guard above is only as good as its membership list, and that list is
# hand-maintained. A seventh recorder that forgets to add itself reopens the
# bare-`set` bypass with no error and no symptom -- the same silent shape the
# guard itself was written to close, one level up. So the list is not trusted:
# it is DERIVED from the module's own writes and compared.
#
# Two writer shapes exist, and the derivation reads both:
#
# * ``write_ledger({"<key>": {...}})`` -- the dedicated recorders. A key is
#   STRUCTURED when its value in the literal is itself a dict, i.e. the
#   recorder accumulates entries under it. ``set_scalar``'s
#   ``write_ledger({field: value})`` has a Name key, not a constant, so it
#   contributes nothing -- which is right: it is the guarded route, not a
#   recorder.
# * ``_write_exact(target, updated)`` -- ``archive_ceremony``, which builds a
#   whole replacement dict rather than a ``{key: ...}`` literal. Its keys
#   arrive as ``updated["<key>"] = ...`` subscript assignments, so the
#   derivation follows the Name passed to ``_write_exact`` back to those
#   assignments in the same function. This is what lets ``ceremony_history``
#   be derived rather than allowlisted; an allowlist here would be one more
#   hand-maintained list with exactly the drift problem being fixed.

# Both branches follow a Name first/second argument back to its binding in the
# same function, so a hoisted ``payload = {...}; write_ledger(payload)`` is
# covered as well as the inline literal.
#
# What is still INVISIBLE, stated so the next author knows the boundary rather
# than assuming coverage: a payload built by a dict COMPREHENSION or by
# ``dict(...)``, one assembled across ``update()``/``|=`` calls, one whose key
# is a name or an f-string instead of a string constant, one bound outside the
# calling function, and any helper that wraps ``write_ledger`` under a name not
# in ``_LEDGER_WRITERS``. This derivation encodes the shapes that exist; a new
# shape needs a new branch here, and the equality assertion below is what makes
# its absence loud.

_LEDGER_WRITERS = frozenset({"write_ledger", "_write_exact"})

# Measured from the module when this test was written. The floor exists
# because two empty sets compare equal: a derivation that stopped matching
# anything would make the equality assertion below pass over nothing at all.
_STRUCTURED_FIELD_FLOOR = 6


def _is_dict_valued(node, bindings):
    """Whether ``node`` evaluates to a dict, following one level of binding."""
    if isinstance(node, ast.Dict):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dict"
    ):
        return True
    if isinstance(node, ast.Name) and node.id in bindings:
        return _is_dict_valued(bindings[node.id], {})
    return False


def _dict_literal_keys(node):
    """Constant string keys of a dict literal whose values are themselves dicts."""
    if not isinstance(node, ast.Dict):
        return set()
    return {
        key.value
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant)
        and isinstance(key.value, str)
        and isinstance(value, ast.Dict)
    }


def _resolve_dict_literal(node, bindings):
    """Follow one level of Name binding to the dict literal behind ``node``.

    Both writer branches need this. A recorder written as
    ``payload = {...}; write_ledger(payload)`` is the same recorder as the
    inline form, and a derivation that saw only the inline form would let a
    hoisted payload add an unguarded structured field in total silence --
    the floor below only catches a DECREASE, never an underivable addition.
    """
    if isinstance(node, ast.Name):
        node = bindings.get(node.id)
    return node


def _derive_structured_fields(source=None):
    """Derive the structured top-level ledger keys from the module's source.

    Returns ``(fields, writer_call_count)``. One writer call is one ``Call``
    node naming ``write_ledger`` or ``_write_exact`` inside a function body;
    the count is returned so the caller can assert the walk saw the module at
    all rather than an empty tree.

    ``source`` defaults to the real module and exists so a test can feed the
    derivation a planted recorder shape without editing the module itself.
    """
    if source is None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fields = set()
    writer_calls = 0
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        bindings = {
            assign.targets[0].id: assign.value
            for assign in ast.walk(func)
            if isinstance(assign, ast.Assign)
            and len(assign.targets) == 1
            and isinstance(assign.targets[0], ast.Name)
        }
        for call in ast.walk(func):
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id in _LEDGER_WRITERS
            ):
                continue
            writer_calls += 1
            if call.func.id == "write_ledger":
                if call.args:
                    fields |= _dict_literal_keys(
                        _resolve_dict_literal(call.args[0], bindings)
                    )
                continue
            # _write_exact(target, data): the payload is the SECOND argument.
            if len(call.args) < 2:
                continue
            data = call.args[1]
            fields |= _dict_literal_keys(_resolve_dict_literal(data, bindings))
            if not isinstance(data, ast.Name):
                continue
            for assign in ast.walk(func):
                target = (
                    assign.targets[0]
                    if isinstance(assign, ast.Assign) and len(assign.targets) == 1
                    else None
                )
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == data.id
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                    and _is_dict_valued(assign.value, bindings)
                ):
                    fields.add(target.slice.value)
    return fields, writer_calls


_HOISTED_RECORDER_SOURCE = """
def record_something(entry_id):
    payload = {"somethings": {entry_id: {"status": "open"}}}
    return write_ledger(payload)
"""


def test_derivation_sees_a_hoisted_write_ledger_payload():
    """A recorder that binds its payload to a name first is the same recorder.

    Planted here rather than in the module: the derivation must cover the
    shape BEFORE somebody writes it, and the equality assertion below would
    otherwise be the thing that discovers it -- by failing in a way that reads
    as "the guard map is stale" rather than "the derivation is blind".
    """
    fields, writer_calls = _derive_structured_fields(_HOISTED_RECORDER_SOURCE)
    assert writer_calls == 1
    assert fields == {"somethings"}


def test_derivation_still_sees_an_inline_write_ledger_payload():
    """The Name-following must not be traded for the literal form."""
    inline = """
def record_something(entry_id):
    return write_ledger({"somethings": {entry_id: {"status": "open"}}})
"""
    fields, _ = _derive_structured_fields(inline)
    assert fields == {"somethings"}


def test_structured_field_derivation_is_not_a_no_op():
    """A derivation that matched nothing would make the drift test vacuous."""
    fields, writer_calls = _derive_structured_fields()
    assert writer_calls >= 9, (
        f"Walked {writer_calls} ledger writer calls, below the 9 measured when "
        f"this test was written. The module's write shape changed and this "
        f"derivation is no longer reading it."
    )
    assert len(fields) >= _STRUCTURED_FIELD_FLOOR, (
        f"Derived {len(fields)} structured fields ({sorted(fields)}) from "
        f"{SCRIPT_PATH.name}, below the floor of {_STRUCTURED_FIELD_FLOOR}. "
        f"The recorder write shape changed and this test silently stopped "
        f"checking anything."
    )


def test_structured_field_routes_matches_the_recorders():
    """The guard list is hand-maintained; only this makes its drift loud.

    Asserted as set EQUALITY, not containment, because drift runs both ways:
    a new recorder missing from the map reopens the bare-`set` bypass, and a
    stale entry left behind after a recorder is removed refuses a write with
    a message pointing at a route that no longer exists.
    """
    derived, _ = _derive_structured_fields()
    assert derived == set(ledger._STRUCTURED_FIELD_ROUTES), (
        f"_STRUCTURED_FIELD_ROUTES has drifted from the recorders in "
        f"{SCRIPT_PATH.name}.\n"
        f"  written by a recorder but NOT guarded: "
        f"{sorted(derived - set(ledger._STRUCTURED_FIELD_ROUTES))}\n"
        f"  guarded but written by NO recorder: "
        f"{sorted(set(ledger._STRUCTURED_FIELD_ROUTES) - derived)}\n"
        f"An unguarded structured field is writable by a bare `set`, which "
        f"replaces the whole object and discards the audit trail under it."
    )


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


def test_group_gate_re_record_without_gates_shrinks_the_gate_list(tmp_ledger):
    """``gates`` gets the same SHRINK treatment as the other two list fields.

    ``_deep_merge`` replaces lists but never deletes keys, so a ``gates``
    written only ``if gate_list`` is retained forever: a re-record that
    asserted no gates at all would still read as covering 4.4/4.5, and the
    ledger would claim coverage the re-record never asserted.
    """
    ledger.record_group_gate("G1", status="passed", gates=["4.4", "4.5"])
    ledger.record_group_gate("G1", status="passed")
    entry = ledger.read_ledger()["groups"]["G1"]["gate_stack"]
    assert entry["gates"] == []


def test_group_gate_re_record_with_fewer_gates_shrinks(tmp_ledger):
    ledger.record_group_gate("G1", status="passed", gates=["4.4", "4.5", "4.5.1"])
    ledger.record_group_gate("G1", status="passed", gates=["4.4"])
    assert ledger.read_ledger()["groups"]["G1"]["gate_stack"]["gates"] == ["4.4"]


def test_group_gate_records_gates_key_even_when_never_supplied(tmp_ledger):
    """One shrink rule across all three sibling fields: ``gates`` is
    present on every record, empty included, exactly like ``open_findings``.
    """
    ledger.record_group_gate("G1", status="passed")
    entry = ledger.read_ledger()["groups"]["G1"]["gate_stack"]
    assert entry["gates"] == []
    assert entry["open_findings"] == []


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
@pytest.mark.parametrize(
    "field,route",
    [
        ("ceremony", "set ceremony."),
        ("ceremony_history", "archive-ceremony"),
        ("blockers", "blocker"),
        ("waves", "wave-discipline"),
        ("groups", "group-gate"),
        ("dispatches", "record-dispatch"),
    ],
)
def test_cli_set_structured_field_refused(tmp_ledger, field, route):
    """The CLI is the route the bypass was demonstrated through: `set
    ceremony.selected` was refused while a bare `set ceremony` warned and
    then wrote. Exit 2 matches the unknown-ceremony-field path -- the caller
    asked for something the ledger does not accept."""
    _run_cli("set", "ceremony.locked_at", "2026-08-10T14:02Z")
    _run_cli("blocker", "B1", "--type", "decision")
    _run_cli("wave-discipline", "3a", "--status", "passed")
    _run_cli("group-gate", "G1", "--status", "passed")
    _run_cli("record-dispatch", "--subagent-type", "impl")
    _run_cli("archive-ceremony", "--reason", "seed the history")
    _run_cli("set", "ceremony.locked_at", "2026-08-12T09:00Z")
    before = json.loads(tmp_ledger.read_text())[field]

    proc = _run_cli("set", field, "obliterated")

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "dedicated recorder" in proc.stderr
    assert route in proc.stderr
    assert json.loads(tmp_ledger.read_text())[field] == before


@pytest.mark.allow("subprocess")
def test_cli_set_dotted_non_ceremony_field_refused(tmp_ledger):
    """The same `else` branch bypassed set_scalar's dotted-field guard too,
    writing a top-level key literally named "need_flags.needs_research"."""
    proc = _run_cli("set", "need_flags.needs_research", "true")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "top-level fields" in proc.stderr
    assert not tmp_ledger.exists() or "need_flags.needs_research" not in json.loads(
        tmp_ledger.read_text()
    )


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
def test_cli_set_ceremony_locked_at_blank_refused(tmp_ledger):
    """The CLI is the reachable route to a blank stamp: ``locked_at`` had no
    value validation, so ``set ceremony.locked_at ""`` wrote a lock that every
    guard then read as absent.
    """
    proc = _run_cli("set", "ceremony.locked_at", "")
    # 2, not 1: the CLI already splits "you passed a bad value" (ValueError,
    # exit 2) from "the stored state refuses this" (LedgerError, exit 1), and
    # a blank stamp is the former.
    assert proc.returncode == 2
    assert "non-blank" in proc.stderr
    assert not tmp_ledger.exists()


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
    """The documented invocation from skills/develop/references/ledger-cli.md
    must actually work from the CLI -- prose describing a flag that does not
    exist is the defect this finding raised."""
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
    # 1, not 2: the stored blocker's type is what the operation cannot use.
    assert proc.returncode == 1
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
    # 1, not 2: the id is well-formed; the ledger holds no blocker under it.
    assert proc.returncode == 1
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


_NO_HOME_DRIVER = '''
"""Run a script with ``Path.home()`` guaranteed to raise RuntimeError.

That is the state of a Windows CI runner with no USERPROFILE/HOMEDRIVE/
HOMEPATH. POSIX hosts recover a home from the ``pwd`` database even with
the environment cleared, and Windows has no ``pwd`` module at all, so
blocking the import is what makes this reproduce identically on both.
"""

import os
import runpy
import sys

for var in ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
    os.environ.pop(var, None)


class _BlockPwd:
    def find_spec(self, name, path=None, target=None):
        if name == "pwd":
            raise ImportError("no pwd module (simulating Windows)")
        return None


sys.modules.pop("pwd", None)
sys.meta_path.insert(0, _BlockPwd())

from pathlib import Path

try:
    Path.home()
except RuntimeError:
    pass
else:
    sys.exit(99)

script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
'''


def test_cli_starts_when_home_directory_is_unresolvable(tmp_path):
    """A host where ``Path.home()`` raises must still run the CLI.

    Windows CI has no resolvable home directory, and the state directory
    used to be computed at module scope -- so the CLI died during import,
    before ``main`` could read ``$SPELLBOOK_DEV_DIR``. Exercised through
    the documented subprocess entry point rather than by patching
    ``default_state_dir``, because the defect was in WHEN the value was
    computed, not in what it computed: any test that imports the module
    normally has already passed the line that raised.
    """
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    driver = tmp_path / "no_home_driver.py"
    driver.write_text(_NO_HOME_DRIVER, encoding="utf-8")

    env = dict(os.environ)
    env["SPELLBOOK_DEV_DIR"] = str(dev_dir)

    proc = subprocess.run(
        [sys.executable, str(driver), str(SCRIPT_PATH), "show"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(tmp_path),
        env=env,
    )
    assert proc.returncode != 99, "precondition failed: Path.home() still resolved"
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert proc.stdout.strip() == "{}"


def test_cli_with_explicit_path_works_without_a_home(tmp_path):
    """``--path`` never consults the default, so no home is needed.

    The sibling of the ``$SPELLBOOK_DEV_DIR`` case above: the refusal must
    fire only for invocations that actually NEED the default directory.
    """
    driver = tmp_path / "no_home_driver.py"
    driver.write_text(_NO_HOME_DRIVER, encoding="utf-8")
    explicit = tmp_path / "explicit.json"

    env = dict(os.environ)
    env.pop("SPELLBOOK_DEV_DIR", None)

    proc = subprocess.run(
        [sys.executable, str(driver), str(SCRIPT_PATH), "--path", str(explicit), "show"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(tmp_path),
        env=env,
    )
    assert proc.returncode != 99, "precondition failed: Path.home() still resolved"
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert proc.stdout.strip() == "{}"


def test_cli_refuses_with_a_remedy_when_the_default_is_needed_without_a_home(tmp_path):
    """No home and no override: REFUSE, naming the remedy.

    Writing the ledger into whatever directory the CLI happened to run
    from is the silent-but-wrong shape: the run "succeeds" while the
    ledger it consults is not the project's ledger. A user-facing
    configuration error is reported like every other refusal in this
    module -- ``error: ...`` on stderr, non-zero exit, no traceback.
    """
    driver = tmp_path / "no_home_driver.py"
    driver.write_text(_NO_HOME_DRIVER, encoding="utf-8")

    env = dict(os.environ)
    env.pop("SPELLBOOK_DEV_DIR", None)

    proc = subprocess.run(
        [sys.executable, str(driver), str(SCRIPT_PATH), "show"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(tmp_path),
        env=env,
    )
    assert proc.returncode != 99, "precondition failed: Path.home() still resolved"
    assert proc.returncode != 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.stderr.startswith("error: "), proc.stderr
    assert "SPELLBOOK_DEV_DIR" in proc.stderr
    assert "--path" in proc.stderr
    # The refusal must not have written a ledger beside the cwd.
    assert not (tmp_path / ".spellbook").exists()


def test_default_state_dir_is_unchanged_when_home_resolves(monkeypatch):
    """The refusal must not move the ledger for real users."""
    monkeypatch.setattr(ledger.Path, "home", classmethod(lambda cls: cls("/home/someone")))
    assert ledger.default_state_dir() == Path("/home/someone/.local/spellbook")


def test_default_state_dir_refuses_without_a_home(monkeypatch, tmp_path):
    def _raise(cls):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(ledger.Path, "home", classmethod(_raise))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ledger.LedgerError) as excinfo:
        ledger.default_state_dir()
    message = str(excinfo.value)
    assert "SPELLBOOK_DEV_DIR" in message
    assert "--path" in message


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

    Since ``spellbook.core.path_utils.resolve_repo_root`` grew a
    filesystem walk that answers the common layouts without spawning git,
    this test also serves as the standing differential between that walk
    and a pure ``git``-subprocess implementation: the fallback below is
    unchanged and still shells out, so any divergence in the mapping shows
    up here as disagreement rather than as an orphaned state file.
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

    worktree_subdir = worktree / "nested"
    worktree_subdir.mkdir()

    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    paths = [
        str(repo_root),                      # the real repo root
        str(repo_root / "scripts"),          # a subdirectory of it
        str(temp_repo),                      # a freshly created repo
        str(worktree),                       # a real linked worktree
        str(worktree_subdir),                # a subdirectory of a worktree
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


# ---- dispatch records ----------------------------------------------------


def test_dispatch_vocabulary_names_real_skills():
    """A renamed skill must fail loudly here, not silently stop matching.

    ``DISPATCH_SKILLS`` is a fixed tuple rather than a glob of ``skills/``
    (see its comment). The cost of fixing it is drift, and drift in THIS
    direction is invisible: a stale name simply never matches, so every
    lookup returns "no dispatch recorded" -- a false negative shaped exactly
    like a real one. This test is the mechanism that reads the constant.
    """
    skills_dir = SCRIPT_PATH.parents[1] / "skills"
    missing = [n for n in ledger.DISPATCH_SKILLS if not (skills_dir / n / "SKILL.md").is_file()]
    assert missing == []


def test_extract_skills_finds_names_in_a_dispatch_prompt():
    found = ledger.extract_skills(
        "Invoke $SPELLBOOK_DIR/skills/reviewing-impl-plans/SKILL.md, then the "
        "test-driven-development skill."
    )
    assert found == ["reviewing-impl-plans", "test-driven-development"]


def test_extract_skills_on_empty_input():
    assert ledger.extract_skills(None) == []
    assert ledger.extract_skills("") == []
    assert ledger.extract_skills("nothing recognizable here") == []


def test_record_dispatch_accumulates_rather_than_replacing(tmp_ledger):
    ledger.record_dispatch(skills=["dehallucination"], timestamp="2026-01-01T00:00:00Z")
    ledger.record_dispatch(skills=["devils-advocate"], timestamp="2026-01-01T00:00:00Z")
    data = json.loads(tmp_ledger.read_text())
    assert sorted(data["dispatches"]) == [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z#002",
    ]


def test_record_dispatch_does_not_clobber_siblings(tmp_ledger):
    ledger.set_scalar("current_phase", "4")
    ledger.record_dispatch(skills=["test-driven-development"])
    data = json.loads(tmp_ledger.read_text())
    assert data["current_phase"] == "4"
    assert len(data["dispatches"]) == 1


def test_record_dispatch_with_nothing_known_still_proves_a_dispatch(tmp_ledger):
    ledger.record_dispatch(timestamp="2026-01-01T00:00:00Z")
    entry = json.loads(tmp_ledger.read_text())["dispatches"]["2026-01-01T00:00:00Z"]
    assert entry == {"recorded_at": "2026-01-01T00:00:00Z", "skills": []}


def test_record_dispatch_truncates_description(tmp_ledger):
    ledger.record_dispatch(description="x" * 5000, timestamp="2026-01-01T00:00:00Z")
    entry = json.loads(tmp_ledger.read_text())["dispatches"]["2026-01-01T00:00:00Z"]
    assert len(entry["description"]) == ledger.DESCRIPTION_MAX


def test_find_dispatches_filters_by_skill(tmp_ledger):
    ledger.record_dispatch(skills=["dehallucination"], timestamp="2026-01-01T00:00:00Z")
    ledger.record_dispatch(skills=["devils-advocate"], timestamp="2026-01-01T00:00:01Z")
    found = ledger.find_dispatches(skill="devils-advocate")
    assert [e["recorded_at"] for e in found] == ["2026-01-01T00:00:01Z"]


def test_find_dispatches_since_excludes_an_earlier_task(tmp_ledger):
    """Without --since, task 1's dispatch would satisfy every later task."""
    ledger.record_dispatch(skills=["test-driven-development"], timestamp="2026-01-01T00:00:00Z")
    assert ledger.find_dispatches(skill="test-driven-development") != []
    assert ledger.find_dispatches(
        skill="test-driven-development", since="2026-01-02T00:00:00Z"
    ) == []


def test_find_dispatches_on_a_fresh_ledger(tmp_ledger):
    assert ledger.find_dispatches() == []


def test_dispatches_cli_exits_1_when_nothing_matches(tmp_ledger, capsys):
    ledger.record_dispatch(skills=["dehallucination"])
    assert ledger.main(["dispatches", "--skill", "dehallucination"]) == 0
    assert ledger.main(["dispatches", "--skill", "fact-checking"]) == 1


def test_record_dispatch_cli_extracts_skills_without_storing_the_prompt(tmp_ledger):
    rc = ledger.main([
        "record-dispatch",
        "--prompt", "invoke fact-checking; secret=hunter2",
    ])
    assert rc == 0
    raw = tmp_ledger.read_text()
    assert "fact-checking" in raw
    assert "hunter2" not in raw


# ---- malformed stored ceremony shape -------------------------------------
#
# A ledger whose `ceremony` is a scalar is not hypothetical: before the bare-
# `set` refusal landed on this branch, `set ceremony <value>` collapsed the
# whole object to a string and exited 0, so a ledger written by that shipped
# code already carries the shape on disk. The module docstring also invites a
# developer to edit the file directly. These are the RECOVERY path -- the tool
# must say what is wrong and where to go, not traceback at the person trying
# to repair it.


def _write_raw_ledger(tmp_ledger, payload: str) -> None:
    tmp_ledger.write_text(payload, encoding="utf-8")


def test_set_ceremony_field_refuses_a_scalar_ceremony(tmp_ledger):
    _write_raw_ledger(tmp_ledger, '{"ceremony": "heavy"}')
    with pytest.raises(ledger.LedgerError) as exc:
        ledger.set_ceremony_field("selected", "gate-a")
    message = str(exc.value)
    assert "archive-ceremony" in message
    assert "str" in message


def test_set_ceremony_field_refuses_a_list_valued_monotonic_field(tmp_ledger):
    _write_raw_ledger(
        tmp_ledger,
        '{"ceremony": {"locked_at": "2026-01-01T00:00:00Z",'
        ' "selected": ["gate-a", "gate-b"]}}',
    )
    with pytest.raises(ledger.LedgerError) as exc:
        ledger.set_ceremony_field("selected", "gate-a")
    message = str(exc.value)
    assert "ceremony.selected" in message
    assert "archive-ceremony" in message


def test_ceremony_elements_refuses_a_non_string(tmp_ledger):
    with pytest.raises(ledger.LedgerError):
        ledger._ceremony_elements(["gate-a"], source="ceremony.selected")


def test_set_ceremony_field_still_reads_a_well_formed_ceremony(tmp_ledger):
    """The guards must not disturb the normal path they wrap."""
    ledger.set_ceremony_field("selected", "gate-a")
    ledger.set_ceremony_field("locked_at", "2026-01-01T00:00:00Z")
    result = ledger.set_ceremony_field("selected", "gate-a\ngate-b")
    assert ledger._ceremony_elements(
        result["ceremony"]["selected"], source="ceremony.selected"
    ) == {"gate-a", "gate-b"}


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_on_a_scalar_ceremony_refuses_without_a_traceback(
    tmp_ledger,
):
    _write_raw_ledger(tmp_ledger, '{"ceremony": "heavy"}')
    proc = _run_cli("set", "ceremony.selected", "gate-a")
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    assert "AttributeError" not in proc.stderr
    assert "archive-ceremony" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_set_ceremony_on_a_list_valued_field_refuses_without_a_traceback(
    tmp_ledger,
):
    _write_raw_ledger(
        tmp_ledger,
        '{"ceremony": {"locked_at": "2026-01-01T00:00:00Z",'
        ' "selected": ["gate-a", "gate-b"]}}',
    )
    proc = _run_cli("set", "ceremony.selected", "gate-a")
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    assert "AttributeError" not in proc.stderr
    assert "archive-ceremony" in proc.stderr


@pytest.mark.allow("subprocess")
def test_cli_archive_ceremony_still_repairs_a_scalar_ceremony(tmp_ledger):
    """The remedy the refusal names must actually work on the broken shape."""
    _write_raw_ledger(tmp_ledger, '{"ceremony": "heavy"}')
    proc = _run_cli("archive-ceremony", "--reason", "repairing a collapsed ceremony")
    assert proc.returncode == 0
    assert ledger.read_ledger()["ceremony"] == {}


# The refusal in `_require_ceremony_dict` admits ANY non-dict, so the remedy
# it names has to hold across that whole space -- not at one representative
# point in it. The truthy case above passed while every falsy shape was a dead
# end: the field write refused, and the archive that refusal named refused too,
# leaving hand-editing the JSON as the only way out. `""` was reachable through
# the bare `set ceremony ""` bypass that shipped before it was closed.
_FALSY_MALFORMED_CEREMONIES = [
    pytest.param('""', "", id="empty-string"),
    pytest.param("0", 0, id="zero"),
    pytest.param("false", False, id="false"),
    pytest.param("[]", [], id="empty-list"),
]


@pytest.mark.parametrize(("raw", "expected"), _FALSY_MALFORMED_CEREMONIES)
def test_archive_ceremony_repairs_a_falsy_malformed_ceremony(
    tmp_ledger, raw, expected
):
    """A PRESENT-but-falsy ceremony is malformed state to repair, not the
    absent case. The archive preserves it under ceremony_history rather than
    discarding the evidence of what the ledger held."""
    _write_raw_ledger(tmp_ledger, f'{{"ceremony": {raw}}}')

    with pytest.raises(ledger.LedgerError, match="archive-ceremony"):
        ledger.set_ceremony_field("selected", "gate-a")

    ledger.archive_ceremony("repairing it", timestamp="2026-01-02T00:00:00Z")

    data = ledger.read_ledger()
    assert data["ceremony"] == {}
    archived = data["ceremony_history"]["2026-01-02T00:00:00Z"]
    assert archived["ceremony"] == expected
    assert archived["reason"] == "repairing it"


@pytest.mark.parametrize(("raw", "expected"), _FALSY_MALFORMED_CEREMONIES)
def test_falsy_malformed_ceremony_recovers_to_a_fresh_phase_0(
    tmp_ledger, raw, expected
):
    """End of the recovery path: after the archive a fresh Phase 0 lock lands."""
    _write_raw_ledger(tmp_ledger, f'{{"ceremony": {raw}}}')
    ledger.archive_ceremony("repairing a collapsed ceremony")

    ledger.set_ceremony_field("locked_at", "2026-01-03T00:00:00Z")
    assert ledger.read_ledger()["ceremony"]["locked_at"] == "2026-01-03T00:00:00Z"


@pytest.mark.parametrize("raw", ["null", "{}"])
def test_archive_ceremony_still_refuses_a_genuinely_empty_ceremony(tmp_ledger, raw):
    """The repair above must not swallow the absent case. `null` and `{}` are
    the documented shape carrying no selection, and they are NOT dead ends --
    the ordinary set path accepts them -- so archiving them stays refused."""
    _write_raw_ledger(tmp_ledger, f'{{"ceremony": {raw}}}')
    with pytest.raises(ledger.LedgerError, match="no ceremony"):
        ledger.archive_ceremony("aborted the run")


def _cli_subcommands() -> set[str]:
    """Every subcommand `main` accepts, read off the parser itself."""
    action = next(
        a
        for a in ledger.build_parser()._actions
        if isinstance(a, argparse._SubParsersAction)
    )
    return set(action.choices)


LEDGER_DOC_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "develop"
    / "references"
    / "ledger-cli.md"
)

# A backticked span is treated as an invocation only through its FIRST
# whitespace-separated token, and only when that token has the shape of a
# hyphenated subcommand: lowercase alphanumeric words joined by hyphens. That
# rule is what separates a remedy from the rest of the backticked text in these
# files. It excludes flags (`--open-rows` starts with a dash), paths
# (`scripts/develop_gate_ledger.py` contains a slash), dotted and underscored
# field names (`ceremony.locked_at`, `ceremony_history`, `open_rows`), literal
# values (`per_group` is underscored, `passed` has no hyphen), and exception
# class names (`LedgerError` is not lowercase). It also excludes the
# non-hyphenated subcommands, which cannot be told apart from field names by
# shape alone -- `blocker` the command and `blockers` the field differ by one
# letter. Those are covered by the "Use instead" table check below, which knows
# from position that a cell holds a remedy.
_COMMAND_TOKEN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+")


def _hyphenated_command_tokens(text: str) -> set[str]:
    tokens = set()
    for span in re.findall(r"`+([^`\n]+)`+", text):
        parts = span.split()
        if parts and _COMMAND_TOKEN.fullmatch(parts[0]):
            tokens.add(parts[0])
    return tokens


def test_hyphenated_command_token_extractor_is_not_vacuous():
    """The floor for the extractor itself. An extractor that matched nothing
    would let every check below pass by finding no work to do."""
    assert _hyphenated_command_tokens("run `wave-discipline 3a --status passed`") == {
        "wave-discipline"
    }
    # The exclusions are asserted, not assumed: each of these is a real span
    # from the files under test that must NOT be read as a remedy.
    assert _hyphenated_command_tokens(
        "`--open-rows` `scripts/develop_gate_ledger.py` `ceremony.locked_at` "
        "`ceremony_history` `open_rows` `per_group` `passed` `LedgerError` "
        "`blockers`"
    ) == set()


def test_every_named_remedy_resolves_to_a_real_subcommand():
    """A refusal that names a command argparse rejects tells the reader to run
    something that cannot run -- the refusal becomes a dead end at exactly the
    moment the caller is stuck. The remedies are prose inside error strings and
    inside the reference doc, so nothing but this test ties them to the parser
    they name.

    Both sources are scanned. The module's messages and the doc's prose restate
    the same vocabulary INDEPENDENTLY, so pinning only the Python side leaves a
    remedy spelled wrong in the doc passing CI -- the hand-written list that
    drifts, wearing a different hat.

    The vocabulary is derived from the parser and from the text itself, never
    from a list written beside them: a second copy of the remedy set would
    drift from the messages exactly as silently as the messages drift from the
    parser.
    """
    commands = _cli_subcommands()
    hyphenated = {c for c in commands if "-" in c}
    assert hyphenated, "the parser declares no hyphenated subcommand -- floor gone"

    sources = {
        "module source": Path(ledger.__file__).read_text(encoding="utf-8"),
        "reference doc": LEDGER_DOC_PATH.read_text(encoding="utf-8"),
    }
    for label, text in sources.items():
        named = _hyphenated_command_tokens(text)
        for route in ledger._STRUCTURED_FIELD_ROUTES.values():
            named |= _hyphenated_command_tokens(route)
        # Anti-no-op floor, derived from the parser rather than counted by
        # hand: both files route to every hyphenated recorder, so an extractor
        # that goes stale drops below this and fails instead of passing empty.
        assert named >= hyphenated, (
            f"{label} names only {sorted(named)}; the parser declares "
            f"{sorted(hyphenated)}. The extractor has gone stale, or the "
            f"file stopped naming a recorder it must route to."
        )
        unknown = sorted(n for n in named if n not in commands)
        assert not unknown, (
            f"{label} names commands the CLI does not accept: {unknown!r}; "
            f"accepted subcommands are {sorted(commands)}"
        )


def _doc_use_instead_rows() -> list[tuple[str, str]]:
    """The (field, remedy) rows of the doc's `set` refusal table.

    Read by POSITION, not by shape: the second cell of a row under the
    `Use instead` header is a remedy by construction, which is how the
    non-hyphenated `blocker` gets covered at all.
    """
    lines = LEDGER_DOC_PATH.read_text(encoding="utf-8").splitlines()
    rows: list[tuple[str, str]] = []
    for i, line in enumerate(lines):
        if not re.match(r"\s*\|\s*Field\s*\|\s*Use instead\s*\|", line):
            continue
        for row in lines[i + 2:]:
            if not row.lstrip().startswith("|"):
                break
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) == 2:
                rows.append((cells[0].strip("`"), cells[1]))
    return rows


def test_doc_use_instead_table_covers_every_structured_field():
    """The floor for the table reader. A reader that found no rows -- renamed
    header, reformatted table -- would let the check below pass vacuously, and
    the row set is fixed by `_STRUCTURED_FIELD_ROUTES`, not by a count here."""
    fields = {field for field, _ in _doc_use_instead_rows()}
    assert fields == set(ledger._STRUCTURED_FIELD_ROUTES), (
        f"the doc's `Use instead` table covers {sorted(fields)}; the refusals "
        f"cover {sorted(ledger._STRUCTURED_FIELD_ROUTES)}"
    )


def test_every_doc_use_instead_remedy_names_a_real_subcommand():
    """The doc's table is a second, independent copy of the routes. `blocker`
    and `set` are not hyphenated, so only reading the cell by position catches
    a misspelling of them."""
    commands = _cli_subcommands()
    rows = _doc_use_instead_rows()
    assert rows, "no `Use instead` rows found -- the table reader went stale"
    for field, remedy in rows:
        tokens = {
            span.split()[0]
            for span in re.findall(r"`+([^`\n]+)`+", remedy)
            if span.split()
        }
        assert tokens & commands, (
            f"the doc routes {field!r} to {remedy!r}, which names no "
            f"subcommand the CLI accepts; accepted are {sorted(commands)}"
        )


def test_every_structured_field_route_names_a_real_subcommand():
    """Each `set` refusal routes to a recorder. If that recorder is spelled
    wrong, the refusal is a dead end for the one operation it exists to
    redirect."""
    commands = _cli_subcommands()
    for field, route in ledger._STRUCTURED_FIELD_ROUTES.items():
        tokens = set(re.findall(r"`([a-z][a-z0-9-]*)", route))
        assert tokens & commands, (
            f"route for {field!r} names no accepted subcommand: {route!r}"
        )


# ---- the documented exit-code split, on every subcommand ------------------
#
# `references/ledger-cli.md` states the contract: 1 means the STORED ledger is
# not what the operation needs, 2 means the CALLER asked for something the
# ledger does not accept. A caller can only branch on that split if it holds
# everywhere. Five recorders collapsed both exceptions into a single exit 2, so
# a corrupt ledger reached through `blocker` told the caller "fix the command"
# while the ledger needed repair -- the wrong half of the split, and the half
# that sends the reader looking at correct input.


CORRUPT_LEDGER = "{not json at all"


@pytest.mark.allow("subprocess")
@pytest.mark.parametrize(
    ("name", "argv"),
    [
        ("archive-ceremony", ("archive-ceremony", "--reason", "re-select")),
        ("wave-discipline", ("wave-discipline", "W1", "--status", "passed")),
        ("blocker", ("blocker", "B1", "--type", "work")),
        ("group-gate", ("group-gate", "G1", "--status", "passed")),
        (
            "record-dispatch",
            ("record-dispatch", "--subagent-type", "impl", "--description", "d"),
        ),
    ],
)
def test_cli_exits_1_when_the_stored_ledger_is_corrupt(tmp_ledger, name, argv):
    """A corrupt ledger is a stored-state failure on every route into it."""
    _write_raw_ledger(tmp_ledger, CORRUPT_LEDGER)
    proc = _run_cli(*argv)
    assert proc.returncode == 1, (
        f"{name!r} exited {proc.returncode} on a corrupt ledger; the documented "
        f"contract reserves 1 for a stored-ledger failure. stderr: "
        f"{proc.stderr.strip()}"
    )
    assert "not valid JSON" in proc.stderr
    assert "Traceback" not in proc.stderr


@pytest.mark.allow("subprocess")
@pytest.mark.parametrize(
    ("name", "argv", "expected_message"),
    [
        (
            "archive-ceremony",
            ("archive-ceremony", "--reason", "   "),
            "non-blank reason",
        ),
        (
            "wave-discipline",
            ("wave-discipline", "W1", "--status", "failed"),
            "at least one open row",
        ),
        ("blocker", ("blocker", "B1",), "requires --type"),
        (
            "group-gate",
            ("group-gate", "G1", "--status", "failed"),
            "at least one open finding",
        ),
    ],
)
def test_cli_exits_2_when_the_caller_asked_for_something_invalid(
    tmp_ledger, name, argv, expected_message
):
    """The other half of the split: a well-formed ledger, a bad argument."""
    proc = _run_cli(*argv)
    assert proc.returncode == 2, (
        f"{name!r} exited {proc.returncode} on a caller error; the documented "
        f"contract reserves 2 for that. stderr: {proc.stderr.strip()}"
    )
    assert expected_message in proc.stderr
