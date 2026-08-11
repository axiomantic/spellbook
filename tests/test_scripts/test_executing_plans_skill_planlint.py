"""Structural checks on skills/executing-plans/SKILL.md's plan-amendment
re-lint hook (design §3.2.3)."""

from pathlib import Path

SKILL = Path(__file__).parents[2] / "skills" / "executing-plans" / "SKILL.md"


def _text():
    return SKILL.read_text(encoding="utf-8")


def test_plan_amendment_writes_section_exists_between_mode_selection_and_autonomous_mode():
    text = _text()
    assert "## Plan Amendment Writes" in text
    assert text.index("## Mode Selection") < text.index("## Plan Amendment Writes") < text.index("## Autonomous Mode")


def test_plan_amendment_writes_calls_lint_on_write():
    text = _text()
    section = text.split("## Plan Amendment Writes", 1)[1].split("## Autonomous Mode", 1)[0]
    assert "lint_on_write" in section


def test_plan_amendment_writes_states_fail_open_never_revert():
    text = _text()
    section = text.split("## Plan Amendment Writes", 1)[1].split("## Autonomous Mode", 1)[0]
    assert "do NOT revert the write" in section or "do not revert the write" in section.lower()


def test_forbidden_block_names_the_missing_relint_case():
    text = _text()
    forbidden = text.split("<FORBIDDEN>", 1)[1].split("</FORBIDDEN>", 1)[0]
    assert (
        "- Write an amended plan to disk without re-running planlint when it declares Schema: planlint-v1"
        in forbidden
    )


def test_self_check_has_the_planlint_bullet():
    text = _text()
    self_check = text.split("## Self-Check", 1)[1].split("<CRITICAL>", 1)[0]
    assert (
        "- [ ] Every disk write of an amended plan was followed by a planlint run "
        "(or `lint_on_write` returned `None` — the plan doesn't declare a `planlint-v1` schema)"
        in self_check
    )
