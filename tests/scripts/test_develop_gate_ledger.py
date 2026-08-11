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


def test_set_scalar_rejects_dotted_field(tmp_ledger):
    """Use set_ceremony_field for ceremony.* -- set_scalar is for the
    top level only, and a dotted argument is almost certainly a bug.
    """
    with pytest.raises(ValueError, match="top-level fields"):
        ledger.set_scalar("ceremony.selected", "x")


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
    assert entry == {"status": "n_a", "reason": "plan has no wave structure"}


@pytest.mark.allow("subprocess")
def test_cli_wave_discipline_failed_without_open_rows_errors(tmp_ledger):
    proc = _run_cli("wave-discipline", "3a", "--status", "failed")
    assert proc.returncode == 2
    assert "requires at least one open row" in proc.stderr
