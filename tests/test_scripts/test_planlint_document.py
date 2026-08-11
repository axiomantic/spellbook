"""Parser contract tests for spellbook.planlint.document.

Real markdown fixture files under tests/test_scripts/fixtures/planlint/, no
mocking. Mirrors the field-reading and fence-scanning contract of
nmg2-tools/planlint/document.py, adapted to spellbook's own
Schema:/Files:/Depends:/Check: field set.
"""

from pathlib import Path

import pytest

from spellbook.planlint.document import (
    NONE_WORDS,
    PlanDocument,
    backticked,
    fenced_line_indexes,
    inline_code_spans,
)

FIXTURES = Path(__file__).parent / "fixtures" / "planlint"


def test_parses_task_headers_and_names():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    assert [t.ident for t in doc.tasks] == ["Task 1", "Task 2"]
    assert doc.task("Task 1").name == "First component"
    assert doc.task("Task 2").name == "Second component"


def test_plan_level_schema_text_is_read():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    assert doc.schema_text == "planlint-v1"
    assert doc.declares_planlint_schema is True


def test_legacy_plan_has_no_schema_text():
    doc = PlanDocument.from_path(FIXTURES / "legacy_plan.md")
    assert doc.schema_text == ""
    assert doc.declares_planlint_schema is False


def test_opted_out_plan_schema_text_is_legacy():
    doc = PlanDocument.from_path(FIXTURES / "opted_out_plan.md")
    assert doc.schema_text == "legacy"
    assert doc.declares_planlint_schema is False


def test_files_field_is_block_scoped_bullet_list():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    task1 = doc.task("Task 1")
    entries = task1.files_entries
    assert [(e.verb, e.path) for e in entries] == [
        ("Create", "spellbook/sample/first.py"),
        ("Test", "tests/test_scripts/test_sample_first.py"),
    ]


def test_files_entry_line_points_at_its_own_bullet_not_the_files_label():
    """Every rule that reports a Files: defect reports AT this line, and every
    one of them names a path. A line pointing at `**Files:**` sends the reader
    to a line that does not mention the path in the message, and does it
    identically for every bullet in the task."""
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    task1 = doc.task("Task 1")
    # clean_plan.md: `**Files:**` is fixture line 9; its two bullets are
    # fixture lines 10 and 11. A regression to the label would give [9, 9].
    assert task1.files_line == 9
    assert [e.line for e in task1.files_entries] == [10, 11]


def test_files_entry_line_survives_a_blank_line_inside_the_block():
    """The bullet block is collected CONTIGUOUSLY. Dropping blank lines while
    collecting and then indexing positionally shifts every bullet below the
    blank by one — an off-by-N that grows with the number of blanks and that a
    single-bullet fixture cannot see."""
    text = (
        "**Schema:** planlint-v1\n"      # line 1
        "\n"                              # line 2
        "### Task 1: X\n"                 # line 3
        "\n"                              # line 4
        "**Files:**\n"                    # line 5
        "- Create: `a.py`\n"              # line 6
        "\n"                              # line 7
        "- Modify: `b.py`\n"              # line 8
        "\n"
        "**Depends:** none\n"
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    entries = doc.task("Task 1").files_entries
    assert [(e.verb, e.line) for e in entries] == [("Create", 6), ("Modify", 8)]


def test_files_entry_with_line_range_suffix():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n"
        "- Modify: `spellbook/x.py:12-30`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    entry = doc.task("Task 1").files_entries[0]
    assert entry.path == "spellbook/x.py"
    assert entry.raw == "spellbook/x.py:12-30"
    assert entry.line_start == 12
    assert entry.line_end == 30


def test_check_command_is_the_single_inline_span():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    assert doc.task("Task 1").check_command == "pytest tests/test_scripts/test_sample_first.py -v"


def test_check_command_is_empty_when_not_a_single_span():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Check:** run `pytest -q` after the migration\n"
    )
    doc = PlanDocument.from_text(text)
    assert doc.task("Task 1").check_command == ""


def test_declared_dependencies_reads_depends_field():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    assert doc.task("Task 1").declared_dependencies == ()
    assert doc.task("Task 2").declared_dependencies == ("Task 1",)


def test_task_block_ends_at_next_task_header():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    task1_body = doc.task("Task 1").body_text
    assert "Second component" not in task1_body


def test_task_block_ends_at_any_heading_level():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "## A section heading\n"
        "more text\n"
    )
    doc = PlanDocument.from_text(text)
    assert "A section heading" not in doc.task("Task 1").body_text


def test_section_at_line_returns_the_nearest_enclosing_heading():
    doc = PlanDocument.from_path(FIXTURES / "clean_plan.md")
    # fixture line 8 sits under `### Task 1: First component` (fixture line 7)
    assert doc.section_at_line(8) == "Task 1: First component"


def test_section_at_line_returns_empty_string_before_the_first_heading():
    doc = PlanDocument.from_text("no heading yet\n\n# Title\n")
    assert doc.section_at_line(1) == ""


def test_none_words_recognizes_common_none_spellings():
    assert NONE_WORDS == {"none", "nothing", "n/a", "na", "-", "—"}


def test_fenced_line_indexes_covers_open_and_close_markers():
    lines = ["a", "```", "b", "```", "c"]
    assert fenced_line_indexes(lines) == {1, 2, 3}


def test_fenced_line_indexes_drops_unclosed_fence():
    lines = ["a", "```", "b", "c"]
    assert fenced_line_indexes(lines) == set()


def test_inline_code_spans_never_crosses_a_line_break():
    text = "one `two\nthree` four"
    spans, unmatched = inline_code_spans(text)
    assert spans == []
    assert len(unmatched) == 2


def test_backticked_skips_fenced_regions():
    text = "before `real` middle\n```\n`fake`\n```\nafter"
    assert backticked(text) == ["real"]


def test_declares_schema_reads_task_level_schema_when_no_plan_level_value():
    text = (
        "### Task 1: X\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Schema:** planlint-v1\n"
    )
    doc = PlanDocument.from_text(text)
    assert doc.declares_planlint_schema is True


def test_from_path_raises_filenotfounderror_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        PlanDocument.from_path(tmp_path / "does_not_exist.md")
