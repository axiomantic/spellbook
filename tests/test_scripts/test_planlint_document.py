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
    FilesEntry,
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
    expected = (
        FilesEntry(
            verb="Create",
            path="spellbook/sample/first.py",
            raw="spellbook/sample/first.py",
            line=10,
        ),
        FilesEntry(
            verb="Test",
            path="tests/test_scripts/test_sample_first.py",
            raw="tests/test_scripts/test_sample_first.py",
            line=11,
        ),
    )
    assert entries == expected


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
    entries = task1.files_entries
    assert [e.line for e in entries] == [10, 11]
    assert entries[0] == FilesEntry(
        verb="Create",
        path="spellbook/sample/first.py",
        raw="spellbook/sample/first.py",
        line=10,
    )


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
    expected = (
        FilesEntry(verb="Create", path="a.py", raw="a.py", line=6),
        FilesEntry(verb="Modify", path="b.py", raw="b.py", line=8),
    )
    assert entries == expected


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
    assert entry == FilesEntry(
        verb="Modify",
        path="spellbook/x.py",
        raw="spellbook/x.py:12-30",
        line_start=12,
        line_end=30,
        line=6,
    )


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


def test_resolved_schema_skips_to_first_task_with_a_non_empty_schema_value():
    """When no plan-level Schema: exists, _resolve_plan_schema falls back to
    the FIRST TASK WITH A NON-EMPTY Schema: value, not literally the first
    task in the list. Task 1 here declares no Schema:, so doc.schema_text
    must come from Task 2."""
    text = (
        "### Task 1: X\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "### Task 2: Y\n\n"
        "**Files:**\n- Create: `y.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "**Schema:** planlint-v1\n"
    )
    doc = PlanDocument.from_text(text)
    assert doc.schema_text == "planlint-v1"


def test_from_path_raises_filenotfounderror_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        PlanDocument.from_path(tmp_path / "does_not_exist.md")


def test_step_run_command_is_parsed_from_its_run_line():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "**Step 1: Do it**\n"
        "Run: `pytest -q`\n"
        "Expected: PASS\n"
    )
    doc = PlanDocument.from_text(text)
    step = doc.task("Task 1").steps[0]
    assert step.number == 1
    assert step.title == "Do it"
    assert step.run_command == "pytest -q"
    assert step.run_line == 13


def test_step_run_command_is_empty_when_not_a_single_span():
    """Regression test for the run_command/check_command asymmetry: `Run:`
    must require the SAME whole-span-coverage check `check_command` already
    applies, or a trailing annotation after the backtick span is silently
    dropped instead of rejecting the whole value."""
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "**Step 1: Do it**\n"
        "Run: `pytest -q` (expect fail)\n"
    )
    doc = PlanDocument.from_text(text)
    step = doc.task("Task 1").steps[0]
    assert step.run_command == ""


def test_files_entry_owner_annotation_is_parsed():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n"
        "- Modify: `shared.py` (owner: Task 2)\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    entry = doc.task("Task 1").files_entries[0]
    assert entry == FilesEntry(
        verb="Modify",
        path="shared.py",
        raw="shared.py",
        owner="Task 2",
        line=6,
    )


def test_unpaired_fence_does_not_corrupt_a_later_paired_fence():
    """Regression for the fence-region bug found in Task 5's review of
    structure.py: a naive open/close TOGGLE across the whole document pairs
    an unclosed fence with whatever marker happens to come next, instead of
    recognizing it as unpaired. That phantom pairing swallows everything
    between the broken opener and the next real marker -- including a task
    header, which then silently vanishes from `doc.tasks`.

    This fixture has THREE fence markers: one broken opener (never legitimately
    closed), then, after a task header, a separate well-formed pair. Under the
    naive toggle: marker 1 (broken open) pairs with marker 2 (which is really
    the WELL-FORMED pair's opener), marking the task header between them as
    "inside a fence" and dropping Task 2 from `doc.tasks` entirely. Marker 3
    (the well-formed pair's real close) is left dangling, unclosed, at EOF.

    The fix must recognize marker 1 as genuinely unpaired (so the task header
    after it stays visible) and marker 2/marker 3 as the real pair.
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Has an unclosed fence\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "```\n"                              # broken opener, never paired
        "this fence never closes\n\n"
        "### Task 2: Comes after the broken fence\n\n"
        "**Files:**\n- Create: `y.py`\n\n"
        "**Depends:** Task 1\n\n"
        "**Check:** `pytest -q -k y`\n\n"
        "Some prose, then a genuinely well-formed fence:\n\n"
        "```\n"                              # real open
        "real fence content\n"
        "```\n\n"                             # real close
        "### Task 3: Comes after the well-formed fence\n\n"
        "**Files:**\n- Create: `z.py`\n\n"
        "**Depends:** Task 2\n\n"
        "**Check:** `pytest -q -k z`\n"
    )
    doc = PlanDocument.from_text(text)

    # Task 2 sits between the broken opener and the well-formed pair's
    # opener. Under the old toggle it is misparsed as "inside a fence" and
    # vanishes; it must survive.
    assert doc.has_task("Task 2")
    assert doc.has_task("Task 3")
    assert [t.ident for t in doc.tasks] == ["Task 1", "Task 2", "Task 3"]

    # Only the genuinely well-formed pair (the second and third markers)
    # should be a recorded, closed fence. The broken opener must not have
    # consumed the well-formed pair's opener as its own phantom close.
    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 3
    _broken_open, real_open, real_close = fence_indexes
    assert fenced_line_indexes(lines) == set(range(real_open, real_close + 1))


def test_unpaired_fence_does_not_corrupt_a_later_paired_fence_same_task_body():
    """Regression for the fence-region bug found in code review of the
    task-header special case: an unclosed fence marker followed LATER IN THE
    SAME TASK BODY (no intervening task header) by a separate, well-formed
    fence pair. A naive forward toggle would silently absorb the well-formed
    pair's OPENING marker as the broken opener's own phantom close,
    corrupting `depends_text`/`check_text` and everything in between, and
    misattributing which line is actually broken (the well-formed pair's
    real closer gets blamed instead of the true broken opener).

    This fixture has THREE fence markers, all inside ONE task body: a broken
    opener (never legitimately closed), then, later in the SAME body, a
    well-formed pair, then real `Depends:`/`Check:` field content after the
    well-formed pair's close.

    With 3 markers and genuine positional ambiguity, the fix does not guess
    which marker is "the" broken one -- see `_pair_fence_markers`'s
    docstring. It leaves the whole segment unfenced, which is what keeps
    the real `Depends:`/`Check:` content from ever being swallowed: nothing
    in this segment is treated as "inside a fence" at all, well-formed pair
    included, so ordinary field-scanning reads the real text correctly.
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Has an unclosed fence, then a well-formed one\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "```\n"                              # broken opener, never paired
        "this fence never closes\n\n"
        "Some prose, then a genuinely well-formed fence:\n\n"
        "```\n"                              # real open
        "real fence content\n"
        "```\n\n"                             # real close
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)

    # The real Depends:/Check: fields, which sit AFTER the well-formed
    # pair's close, must be parsed normally -- they must not have been
    # swallowed by a phantom fence spanning from the broken opener to the
    # well-formed pair's opener.
    task = doc.task("Task 1")
    assert task.depends_text == "none"
    assert task.check_text == "`pytest -q`"
    assert task.check_command == "pytest -q"

    # With genuine 3-marker ambiguity, nothing in the segment is treated as
    # a paired fence -- not even the two markers that look like an
    # obviously well-formed pair. This is the fail-safe trade: precision on
    # this one ambiguous segment, for correctness everywhere else.
    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 3
    assert fenced_line_indexes(lines) == set()


def test_ambiguous_odd_fence_segment_does_not_swallow_later_field_text():
    """Mirror-case regression (the shape `d808059f`'s leftover-first fix got
    wrong): a well-formed fence pair FIRST, then a separate broken/unclosed
    marker LATER, in the SAME task body, followed by real `Depends:`/
    `Check:` field content.

    This fixture has THREE fence markers, all inside ONE task body: a
    well-formed pair, then, later in the SAME body, a broken trailing
    marker that is never closed, then real `Depends:`/`Check:` content
    between the well-formed pair's close and the broken marker.

    Under leftover-first (the immediately preceding fix), the FIRST marker
    (the well-formed pair's own opener) is set aside as the leftover, and
    the remaining two markers -- the well-formed pair's closer and the
    broken trailing marker -- are paired consecutively as a phantom fence.
    That phantom fence spans exactly the real `Depends:`/`Check:` content,
    so it gets swallowed and the resulting `depends_text`/`check_text` come
    back empty, with no error raised anywhere.

    The correct behavior: with 3 markers and genuine ambiguity, NEITHER
    guess is taken. `fenced_line_indexes` reports no fenced lines at all
    for this segment, so the real `Depends:`/`Check:` lines are read as
    ordinary text and come back correct.
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Well-formed pair, then a later broken trailing marker\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "Some prose, then a genuinely well-formed fence:\n\n"
        "```\n"                              # real open
        "real fence content\n"
        "```\n\n"                             # real close
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "```\n"                              # broken trailing marker, never paired
        "this fence never closes\n"
    )
    doc = PlanDocument.from_text(text)

    # The real Depends:/Check: fields, which sit BETWEEN the well-formed
    # pair's close and the later broken marker, must be parsed normally --
    # they must not have been swallowed by a phantom fence spanning from
    # the well-formed pair's closer to the broken trailing marker.
    task = doc.task("Task 1")
    assert task.depends_text == "none"
    assert task.check_text == "`pytest -q`"
    assert task.check_command == "pytest -q"

    # With genuine 3-marker ambiguity, nothing in the segment is treated as
    # a paired fence -- not even the two markers that look like an
    # obviously well-formed pair.
    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 3
    assert fenced_line_indexes(lines) == set()


def test_files_block_does_not_absorb_a_fenced_example_bullet():
    """A fenced code block later in the same task body may illustrate the
    Files: syntax for readers; a line inside it that happens to match
    FILES_ENTRY must not be picked up as a real bullet.

    A fence delimiter line is neither blank nor a FILES_ENTRY bullet, so the
    block-collection loop halts there incidentally -- this is NOT fence-aware
    parsing, just a side effect of the two-condition halt rule. If
    FILES_ENTRY's pattern ever loosened to match a fence marker, this would
    break silently."""
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n"
        "**Files:**\n"
        "- Create: `real.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n\n"
        "Example of the Files: syntax:\n"
        "```\n"
        "- Create: `fenced_example.py`\n"
        "```\n"
    )
    doc = PlanDocument.from_text(text)
    entries = doc.task("Task 1").files_entries
    assert [e.path for e in entries] == ["real.py"]
