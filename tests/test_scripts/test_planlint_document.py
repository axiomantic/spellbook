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

    With 3 markers and genuine positional ambiguity, `unclosed_fence_index`
    (diagnostic reporting) does not guess which marker is "the" broken one
    -- see `_pair_fence_markers`'s docstring. Content-scanning protection
    (`fenced_line_indexes`) is separate: for an odd (3+) marker count it
    protects the ENTIRE `[first, last]` marker span as one block (see
    `_protective_fence_ranges`'s docstring), so all three markers here --
    the broken opener through the well-formed pair's real closer -- fall
    inside one protected block. That is safe here: the real
    `Depends:`/`Check:` fields sit AFTER marker 3, outside the protected
    range either way, so they are never swallowed.
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

    # Content-scanning protection treats the whole odd (3-marker) segment as
    # one protected block, spanning from the broken opener through the
    # well-formed pair's real closer, independent of the diagnostic-
    # reporting ambiguity.
    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 3
    broken_open, _well_formed_open, well_formed_close = fence_indexes
    assert fenced_line_indexes(lines) == set(
        range(broken_open, well_formed_close + 1)
    )


def test_ambiguous_odd_fence_segment_does_not_swallow_later_field_text():
    """Mirror-case regression (the shape `d808059f`'s leftover-first fix got
    wrong): a well-formed fence pair FIRST, then a separate broken/unclosed
    marker LATER, in the SAME task body, with real `Depends:`/`Check:`
    field content in between.

    This fixture has THREE fence markers, all inside ONE task body: a
    well-formed pair, then, later in the SAME body, a broken trailing
    marker that is never closed, with real `Depends:`/`Check:` content
    sitting BETWEEN the well-formed pair's close and the broken marker.

    This is now a DOCUMENTED DROP case, not a leak case: the FINAL
    algorithm treats every odd (3+) marker segment as ambiguous and
    protects the ENTIRE `[first, last]` marker span as one undifferentiated
    block (see `_protective_fence_ranges`'s docstring for the full
    leak-safety proof). Here that means markers 1 through 3 -- from the
    well-formed pair's real opener through the later broken trailing
    marker -- are ALL treated as one protected block, which necessarily
    also covers the real `Depends:`/`Check:` lines sandwiched in between.
    Those fields therefore come back EMPTY, not corrupted or substituted --
    this is the accepted DROP tradeoff, safe because no wrong value is ever
    fabricated. It is a deliberate improvement over the earlier
    leftover-first fix, which produced the same empty result but via a
    guessed sub-pairing that could ALSO leak in other shapes; the
    full-span rule reaches the same drop here without ever guessing.
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
    # pair's close and the later broken marker, fall inside the full-span
    # protected block and are DROPPED (empty), not corrupted or
    # substituted with a wrong value -- the accepted tradeoff.
    task = doc.task("Task 1")
    assert task.depends_text == ""
    assert task.check_text == ""
    assert task.check_command == ""

    # Content-scanning protection protects the ENTIRE odd (3-marker) span
    # as one block: marker 1 (well-formed opener) through marker 3 (the
    # later broken trailing marker).
    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 3
    well_formed_open, _well_formed_close, broken_trailing = fence_indexes
    assert fenced_line_indexes(lines) == set(
        range(well_formed_open, broken_trailing + 1)
    )


def test_ambiguous_segment_still_protects_a_well_formed_pairs_illustrative_content():
    """Regression for the leak/substitution bug found in review of the
    fail-safe fix (`7fd94a6e`): when a well-formed fence pair shares its
    segment with one unrelated broken trailing marker (3 markers total,
    ambiguous for `unclosed_fence_index`'s DIAGNOSTIC-reporting purposes),
    `7fd94a6e` withheld protection from the ENTIRE segment, including the
    well-formed pair. That let an illustrative field-like line INSIDE the
    well-formed fence (e.g. `**Depends:** Task 99` in a code example) leak
    into ordinary field-scanning and SILENTLY SUBSTITUTE a wrong value for
    the real field -- not merely drop it, actively replace it, with no
    error raised anywhere.

    Fixture: the REAL `**Depends:** Task 2` field comes FIRST. Then a
    well-formed fence containing an illustrative `**Depends:** Task 99`
    line (which, if it leaks, OVERWRITES the real value since `_fill_fields`
    keeps the last match). Then a separate, unrelated broken trailing
    marker that never closes.

    Under `7fd94a6e`'s (RED, pre-fix) behavior, `fenced_line_indexes`
    reports the empty set for this 3-marker ambiguous segment, so the
    illustrative line inside the fence is read as an ordinary field line
    and overwrites `depends_text` to `"Task 99"`.

    Under the FINAL fix (GREEN), content-scanning protection treats the
    whole odd (3-marker) segment as one protected block spanning the
    well-formed opener through the later broken trailing marker -- which
    still fully covers the well-formed fence's own content -- so the
    illustrative line stays hidden from field-scanning and `depends_text`
    keeps its real value. (The `**Check:**` field, which sits inside that
    same full-span block, is a DROP case here -- not asserted by this
    test, which is only about the LEAK failure mode.)
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Real field, then an illustrative fence, then a broken marker\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** Task 2\n\n"          # the REAL field
        "Example of a Depends: line inside a fence:\n\n"
        "```\n"                             # well-formed open
        "**Depends:** Task 99\n"            # illustrative, must NOT leak
        "```\n\n"                            # well-formed close
        "**Check:** `pytest -q`\n\n"
        "```\n"                              # unrelated broken trailing marker
        "this fence never closes\n"
    )
    doc = PlanDocument.from_text(text)
    task = doc.task("Task 1")

    # The empirically-observed RED value (pre-fix) was "Task 99" -- the
    # illustrative fenced line leaking through and silently overwriting the
    # real field. GREEN recovers the real value.
    assert task.depends_text == "Task 2"


def test_broken_first_marker_does_not_leak_a_well_formed_pairs_content():
    """The exact leak shape iterations 4 and 5 could not close: the STRAY
    marker comes FIRST in the segment, then a well-formed pair whose
    fenced content includes an illustrative field-like line.

    Under a front-consecutive (iteration-4) pairing rule, marker 1 (the
    stray opener) pairs with marker 2 (the well-formed pair's own opener)
    as a phantom span, so the well-formed pair's REAL closer (marker 3) is
    left unpaired and protects nothing -- the well-formed fence's own
    content, including the illustrative line inside it, is then read as
    ordinary text and leaks into field-scanning.

    Under the FINAL full-span rule, this 3-marker odd segment is protected
    as ONE block from marker 1 through marker 3 -- which necessarily
    contains the well-formed pair's own `[open, close]` range -- so the
    illustrative line inside the well-formed fence never leaks.
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Broken opener first, then a well-formed illustrative fence\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "```\n"                              # broken opener, never paired
        "this fence never closes\n\n"
        "Some prose, then a well-formed fence with illustrative content:\n\n"
        "```\n"                              # well-formed open
        "**Depends:** Task 99\n"            # illustrative, must NOT leak
        "```\n\n"                             # well-formed close
        "**Depends:** Task 2\n\n"           # the REAL field, after the fence
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    task = doc.task("Task 1")

    # The real Depends: field, which comes AFTER the well-formed fence, must
    # keep its real value -- the illustrative line inside the fence must not
    # have leaked in and been overwritten (or overwritten it, since
    # `_fill_fields` keeps the LAST match: if the illustrative line leaked,
    # it would actually be overwritten BY the real field here, so the
    # sharper assertion is that the illustrative value never appears at
    # all -- confirmed directly on the protected-range check below).
    assert task.depends_text == "Task 2"
    assert task.check_text == "`pytest -q`"
    assert task.check_command == "pytest -q"

    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 3
    broken_open, _well_formed_open, well_formed_close = fence_indexes
    # The illustrative line never becomes visible to field-scanning: its
    # document index sits inside the protected full span.
    illustrative_index = lines.index("**Depends:** Task 99")
    protected = fenced_line_indexes(lines)
    assert illustrative_index in protected
    assert protected == set(range(broken_open, well_formed_close + 1))


def test_broken_middle_marker_protects_both_surrounding_well_formed_pairs():
    """A segment with 5 markers: a well-formed pair, a stray/broken marker,
    then a second well-formed pair -- both real pairs must stay fully
    protected regardless of where in the segment the stray marker sits.
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Two well-formed pairs around a broken middle marker\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "```\n"                              # pair 1 open
        "**Depends:** Task 99\n"            # illustrative, must NOT leak
        "```\n\n"                             # pair 1 close
        "```\n"                              # broken/stray marker, never paired
        "this fence never closes\n\n"
        "```\n"                              # pair 2 open
        "**Check:** bogus illustrative check\n"  # illustrative, must NOT leak
        "```\n"                              # pair 2 close
    )
    doc = PlanDocument.from_text(text)
    task = doc.task("Task 1")

    lines = text.split("\n")
    fence_indexes = [i for i, line in enumerate(lines) if line == "```"]
    assert len(fence_indexes) == 5
    first_marker, *_middle, last_marker = fence_indexes
    protected = fenced_line_indexes(lines)
    assert protected == set(range(first_marker, last_marker + 1))

    # Neither illustrative line inside either well-formed pair leaked into
    # the real fields (both fields are empty here since no real
    # Depends:/Check: line exists outside the protected span).
    assert task.depends_text == ""
    assert task.check_text == ""


def test_ambiguous_segment_drops_real_field_content_inside_the_full_span():
    """DOCUMENTED, ACCEPTED tradeoff (DROP over LEAK): real, non-fenced
    field content that happens to sit between the stray marker and a
    well-formed pair -- genuinely NOT inside any real fence -- is still
    inside the odd segment's full `[first, last]` protected span, so it is
    read as absent (empty/missing), never as a wrong or corrupted value.
    This is the accepted cost of the leak-safe full-span rule: it is a
    documented DROP, not a bug.
    """
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: A real field genuinely outside any fence, but inside the span\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "```\n"                              # broken opener, never paired
        "this fence never closes\n\n"
        "**Depends:** Task 2\n\n"           # genuinely NOT inside a fence
        "```\n"                              # well-formed open
        "real fence content\n"
        "```\n\n"                             # well-formed close
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    task = doc.task("Task 1")

    # The Depends: line sits between the broken marker and the well-formed
    # pair, genuinely outside any real fence -- but it is still inside the
    # full-span protected block, so it is DROPPED (empty), not corrupted.
    assert task.depends_text == ""
    # The Check: field, after the whole segment closes, is unaffected.
    assert task.check_text == "`pytest -q`"


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
