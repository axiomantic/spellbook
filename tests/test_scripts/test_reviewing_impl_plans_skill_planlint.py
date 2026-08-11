"""Structural checks on skills/reviewing-impl-plans/SKILL.md's Phase 0
mechanized pre-pass (design §3.2.2)."""

import re
from pathlib import Path

SKILL = Path(__file__).parents[2] / "skills" / "reviewing-impl-plans" / "SKILL.md"


def _text():
    return SKILL.read_text(encoding="utf-8")


def test_phase_0_section_exists_before_phase_1():
    text = _text()
    assert "## Phase 0: Mechanized Pre-Pass" in text
    assert text.index("## Phase 0: Mechanized Pre-Pass") < text.index("## Phase 1: Context and Inventory")


def test_phase_0_calls_lint_for_review_and_declares_schema():
    text = _text()
    section = text.split("## Phase 0: Mechanized Pre-Pass", 1)[1].split("## Phase 1", 1)[0]
    assert "declares_schema" in section
    assert "lint_for_review" in section
    assert "decided_claims" in section


def test_phase_0_imports_declares_schema_not_just_mentions_it():
    """`declares_schema` must be IMPORTED, not merely used. A bare mention
    (e.g. only inside the Gate's function-call text) without an import line
    naming it means the snippet raises NameError when executed."""
    text = _text()
    section = text.split("## Phase 0: Mechanized Pre-Pass", 1)[1].split("## Phase 1", 1)[0]
    import_lines = [
        line
        for line in section.splitlines()
        if re.match(r"\s*from spellbook\.planlint import\b", line) and "declares_schema" in line
    ]
    assert import_lines, "expected a 'from spellbook.planlint import ...' line naming declares_schema"


def test_phase_0_states_the_crash_policy():
    """Design §5.3's row for this call site: fail CLOSED on the claims,
    OPEN on the review. The Report Assembly template already offers
    `UNAVAILABLE` as a value; without this prose nothing says when to write it
    or what it obliges, and a value with no rule behind it gets used at
    random."""
    text = _text()
    section = text.split("## Phase 0: Mechanized Pre-Pass", 1)[1].split("## Phase 1", 1)[0]
    assert "internal_errors" in section
    assert "UNAVAILABLE" in section
    assert "UNDECIDED" in section


def test_phase_0_gate_names_legacy_plans_not_applicable():
    text = _text()
    section = text.split("## Phase 0: Mechanized Pre-Pass", 1)[1].split("## Phase 1", 1)[0]
    assert "NOT APPLICABLE" in section


def test_report_assembly_carries_phase_0_block():
    text = _text()
    section = text.split("## Report Assembly", 1)[1]
    assert "Phase 0: Mechanized Pre-Pass" in section
    assert "Claims decided" in section
    assert "Claims NOT decided" in section


def test_reflection_list_leads_with_the_phase_0_check():
    text = _text()
    reflection = text.split("<reflection>", 1)[1].split("</reflection>", 1)[0]
    first_item = [line for line in reflection.splitlines() if line.strip().startswith("[ ]")][0]
    assert "Phase 0" in first_item


def test_phase_0_states_the_not_linted_policy():
    """`report.linted is False` with no crash and no findings is a third,
    distinct state from RAN and CRASH: the linter declined to lint at all.
    Without this prose, a reviewer has no fitting bucket for the Linter: line
    and would wrongly record RAN with an empty 'Claims NOT decided'."""
    text = _text()
    section = text.split("## Phase 0: Mechanized Pre-Pass", 1)[1].split("## Phase 1", 1)[0]
    assert "linted" in section or "report.linted" in section
    assert "UNAVAILABLE (not linted: <report.skip_reason>)" in text
