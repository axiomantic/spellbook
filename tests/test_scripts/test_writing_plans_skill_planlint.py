"""Structural checks on skills/writing-plans/SKILL.md's planlint integration
(design §3.2.1). Grep-based, matching the mechanized-claim style of
test_planlint_vocabulary.py — full 9.8/9.9 checks land in Task 22 once all
three SKILL.md edits exist; this file's own tests are the per-skill
correctness gate for THIS edit alone.
"""

from pathlib import Path

SKILL = Path(__file__).parents[2] / "skills" / "writing-plans" / "SKILL.md"


def _text():
    return SKILL.read_text(encoding="utf-8")


def _template_block():
    """The FENCED template inside `## Task Structure` — deliberately not the
    whole section.

    Slicing `## Task Structure` → `## Mode Behavior` swallows the
    `## Field Definitions` section that Edit B inserts between the two, and
    that section's table names `**Depends:**`, `**Check:**` and
    `**Schema:** planlint-v1` itself. A field assertion over that wider range
    therefore passes when Edit B alone lands and Edit A — the actual template
    change this task exists to make — is never applied. Narrowing to the
    fenced block is what makes these assertions decide Edit A."""
    section = _text().split("## Task Structure", 1)[1].split("## Field Definitions", 1)[0]
    return section.split("```markdown\n", 1)[1].split("\n```", 1)[0]


def test_task_structure_template_carries_all_four_required_fields():
    block = _template_block()
    for field in ("**Files:**", "**Depends:**", "**Check:**", "**Schema:** planlint-v1"):
        assert field in block, f"missing {field} in the Task Structure template block"


def test_field_definitions_is_not_what_satisfies_the_template_assertion():
    """The guard on the guard: the template block must not accidentally be
    sliced wide enough to include the Field Definitions table."""
    assert "## Field Definitions" not in _template_block()
    assert "| Field | Meaning |" not in _template_block()


def test_step_4_run_line_is_the_same_command_as_check():
    block = _template_block()
    assert "**Check:** `pytest tests/path/test.py::test_name -v`" in block
    assert "Run: `pytest tests/path/test.py::test_name -v`" in block


def test_field_definitions_section_exists_after_task_structure():
    text = _text()
    assert "## Field Definitions" in text
    assert text.index("## Task Structure") < text.index("## Field Definitions") < text.index("## Mode Behavior")


def test_field_definitions_documents_depends_check_and_schema():
    text = _text()
    section = text.split("## Field Definitions", 1)[1].split("## Mode Behavior", 1)[0]
    field_rows = [
        line.split("|")[1].strip().strip("`")
        for line in section.splitlines()
        if line.strip().startswith("| `**")
    ]
    assert field_rows == [
        "**Depends:**",
        "**Check:**",
        "**Schema:** planlint-v1",
        "**Subject:**",
    ]


def test_plan_lint_self_check_section_exists_before_final_emphasis():
    text = _text()
    assert "## Plan Lint Self-Check" in text
    assert text.index("## Self-Check") < text.index("## Plan Lint Self-Check") < text.index("<FINAL_EMPHASIS>")


def test_plan_lint_self_check_calls_lint_for_authoring():
    text = _text()
    section = text.split("## Plan Lint Self-Check", 1)[1].split("<FINAL_EMPHASIS>", 1)[0]
    assert "lint_for_authoring" in section


def test_self_check_list_has_the_planlint_bullet():
    text = _text()
    self_check = text.split("## Self-Check", 1)[1].split("## Plan Lint Self-Check", 1)[0]
    assert "- [ ] planlint reports zero ERROR findings (see Plan Lint Self-Check)" in self_check
