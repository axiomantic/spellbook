"""Mutation tests: one deliberately-broken fixture per rule ID.

Each test asserts THREE things: the expected rule ID appears, Finding.line is
the exact line of the defect, and the CLEAN fixture produces zero findings
for that rule ID. The third assertion is what stops a rule that always fires
from passing its own test.
"""

import enum
from pathlib import Path

from spellbook.planlint import registry
from spellbook.planlint.document import PlanDocument
from spellbook.planlint.finding import ERROR, Finding
from spellbook.planlint.rules import structure

FIXTURES = Path(__file__).parent / "fixtures" / "planlint"


class _Phase(enum.Enum):
    """The same test-only stand-in `test_planlint_registry.py` defines, and
    for the same reason: `api.Phase` is Task 12, later in build order than
    every rule module. Module scope, not function scope, so a test can name a
    specific phase (`rules/files.py` branches on `phase.value`).

    Every test below calls `rule_module.run(ctx)` DIRECTLY, never through
    `registry.run_rules()`. That is load-bearing: `run_rules()` filters on
    `ctx.phase not in rule.phases`, and a stand-in member matches no real
    `frozenset(Phase)`, so routing these tests through `run_rules()` would
    select ZERO rules and report green. Do not "simplify" the harness that
    way."""

    AUTHORING = "authoring"
    REVIEW = "review"
    EXECUTION = "execution"


def _ctx(fixture_name, phase=None, repo_root=None):
    doc = PlanDocument.from_path(FIXTURES / fixture_name)
    return registry.RuleContext(
        doc=doc, phase=phase or _Phase.REVIEW, repo_root=repo_root
    )


def _findings_for(rule_module, fixture_name, **kwargs):
    ctx = _ctx(fixture_name, **kwargs)
    return rule_module.run(ctx).findings


# --------------------------------------------------------------- structure

def test_unmatched_backtick_fires_on_the_defect_line():
    findings = _findings_for(structure, "neg_unmatched_backtick.md")
    hits = [f for f in findings if f.rule == "unmatched-backtick"]
    assert len(hits) == 1
    # fixture line 10 is the `**Check:**` line, which carries 3 backticks —
    # one pair plus one unmatched opener. See the fixture's line table. Full
    # Finding equality, not just `.line`: a mutation test proved a wrong
    # `task=` value leaves a `len(hits) == 1` + `.line` assertion green.
    assert hits[0] == Finding(
        rule="unmatched-backtick",
        message=(
            "a task body carries a backtick with no partner on its own "
            "line; a reader and the linter read two different documents"
        ),
        task="Task 1",
        section="Task 1: Broken backticks",
        line=10,
        evidence=(
            "line 10 carries 1 backtick with no partner: "
            "`**Check:** `pytest -q` and also `make lint`"
        ),
        severity=ERROR,
    )


def test_unmatched_backtick_is_absent_on_the_clean_fixture():
    findings = _findings_for(structure, "clean_plan.md")
    assert [f for f in findings if f.rule == "unmatched-backtick"] == []


def test_unclosed_fence_fires_at_the_opening_line():
    findings = _findings_for(structure, "neg_unclosed_fence.md")
    hits = [f for f in findings if f.rule == "unclosed-fence"]
    assert len(hits) == 1
    # fixture line 13 is the opening fence with no partner. See the line
    # table. Full Finding equality, not just `.line` -- see the sibling
    # unmatched-backtick test above for why.
    assert hits[0] == Finding(
        rule="unclosed-fence",
        message=(
            "a fenced block is opened and never closed; every fenced-block "
            "boundary below this line is the wrong one"
        ),
        task="",
        section="Task 1: Has an unclosed fence",
        line=13,
        evidence="line 13 opens a fenced block and no line below it closes it",
        severity=ERROR,
    )


def test_unclosed_fence_does_not_hide_tasks_below_it():
    """The second assertion that would have caught source defect L-5: the
    plan must still parse Task 2 and Task 3 below the broken fence.

    The fixture also carries a SEPARATE, well-formed fence pair further down
    (after Task 3), followed by Task 4. This is the regression coverage for
    the fence-region bug fixed alongside this task: a naive open/close
    toggle would misattribute the broken fence's phantom "close" to the
    well-formed pair's own opening marker, hiding Task 4 as well and (in the
    `unclosed-fence` rule) blaming the well-formed pair's real closing tick
    for the defect instead of the true broken opener at line 13."""
    doc = PlanDocument.from_path(FIXTURES / "neg_unclosed_fence.md")
    assert doc.has_task("Task 2")
    assert doc.has_task("Task 3")
    assert doc.has_task("Task 4")
    assert [t.ident for t in doc.tasks] == ["Task 1", "Task 2", "Task 3", "Task 4"]

    # The defect is still correctly attributed to the true broken opener
    # (line 13), never to the well-formed later fence's closing tick.
    findings = _findings_for(structure, "neg_unclosed_fence.md")
    hits = [f for f in findings if f.rule == "unclosed-fence"]
    assert len(hits) == 1
    assert hits[0].line == 13


def test_unclosed_fence_is_absent_on_the_clean_fixture():
    findings = _findings_for(structure, "clean_plan.md")
    assert [f for f in findings if f.rule == "unclosed-fence"] == []


def test_unclosed_fence_reports_the_generic_ambiguous_message_for_a_3plus_marker_segment():
    """Closes the MEDIUM-severity test-coverage gap flagged in `7fd94a6e`'s
    review: no prior test drove `unclosed_fence_line`'s AMBIGUOUS branch
    (`ambiguous_lines is not None`, the `elif opened:` arm in `run()`) with
    a full `Finding`-equality assertion. A segment with 3+ fence markers
    cannot say which single marker is unclosed -- see
    `document._pair_fence_markers`'s docstring -- so `run()` must emit the
    generic "N markers, cannot determine which is unclosed" Finding instead
    of naming one line."""
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Three fence markers, genuinely ambiguous\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "```\n"                              # line 8 -- marker 1
        "one\n"
        "```\n"                              # line 10 -- marker 2
        "```\n"                              # line 11 -- marker 3, unclosed
        "**Depends:** none\n\n"
        "**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    findings = structure.run(ctx).findings
    hits = [f for f in findings if f.rule == "unclosed-fence"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="unclosed-fence",
        message=(
            "a section has an odd, ambiguous number of fence markers; "
            "marker position alone cannot say which one is unclosed, so "
            "none of them are treated as a matched pair"
        ),
        section="Task 1: Three fence markers, genuinely ambiguous",
        line=8,
        evidence="3 fence markers in this section (lines 8, 10, 11); cannot determine which is unclosed",
        severity=ERROR,
    )


# --------------------------------------------------------------- depends

def test_dependency_cycle_names_all_three_tasks():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "neg_depends_cycle.md")
    hits = [f for f in findings if f.rule == "dependency-cycle"]
    assert len(hits) == 1
    # fixture: Task 1 -> Task 2 -> Task 3 -> Task 1, a 3-cycle. Full Finding
    # equality, not just a membership check on the evidence string -- see the
    # structure-rule tests above for why: a membership check alone leaves a
    # wrong `task=`/`section=`/`line=` value invisible.
    assert hits[0] == Finding(
        rule="dependency-cycle",
        message="these tasks wait on each other and none of them can start",
        task="Task 1",
        section="Task 1: A",
        line=3,
        evidence="strongly connected component: Task 1, Task 2, Task 3",
        severity=ERROR,
    )


def test_dependency_cycle_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "clean_plan.md")
    assert [f for f in findings if f.rule == "dependency-cycle"] == []


def test_unknown_dependency_fires_on_undefined_task():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "neg_depends_unknown.md")
    hits = [f for f in findings if f.rule == "unknown-dependency"]
    assert len(hits) == 1
    # fixture line 26: Task 3's `Depends:` names Task 9, which no task block
    # defines.
    assert hits[0] == Finding(
        rule="unknown-dependency",
        message=(
            "a `Depends:` line names an identifier this plan defines in no "
            "task block"
        ),
        task="Task 3",
        section="Task 3: C",
        line=26,
        evidence="Depends: Task 9 → Task 9",
        severity=ERROR,
    )


def test_unknown_dependency_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "clean_plan.md")
    assert [f for f in findings if f.rule == "unknown-dependency"] == []


def test_self_dependency_fires_when_a_task_names_itself():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "neg_depends_self.md")
    hits = [f for f in findings if f.rule == "self-dependency"]
    assert len(hits) == 1
    # fixture line 17: Task 2's `Depends:` names itself.
    assert hits[0] == Finding(
        rule="self-dependency",
        message="a task names itself on its `Depends:` line",
        task="Task 2",
        section="Task 2: B",
        line=17,
        evidence="Depends: Task 2",
        severity=ERROR,
    )


def test_self_dependency_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "clean_plan.md")
    assert [f for f in findings if f.rule == "self-dependency"] == []


def test_depends_prose_fires_and_edge_set_excludes_the_prose_task():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "neg_depends_prose.md")
    hits = [f for f in findings if f.rule == "depends-prose"]
    assert len(hits) == 1
    # fixture line 17: Task 2's `Depends:` reads "Task 1, and Task 2 once the
    # fixtures land." -- the second comma-item is prose carrying a stray
    # `Task 2` reference, not a bare identifier, so it yields a depends-prose
    # finding and no edge. The graph.py/depends.py split under test here: the
    # Finding is CONSTRUCTED by graph.parse_depends (Task 3) and merely
    # returned by depends.run() (Task 6) -- see this rule module's own
    # docstring.
    assert hits[0] == Finding(
        rule="depends-prose",
        message=(
            "an identifier sits in prose on the `Depends:` line, so it is "
            "not read as an edge; state it as an item or move the note off "
            "the line"
        ),
        task="Task 2",
        section="Task 2: B",
        line=17,
        evidence="and Task 2 once the fixtures land → Task 2",
        severity=ERROR,
    )
    doc = PlanDocument.from_path(FIXTURES / "neg_depends_prose.md")
    assert doc.task("Task 2").declared_dependencies == ("Task 1",)


def test_depends_prose_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import depends

    findings = _findings_for(depends, "clean_plan.md")
    assert [f for f in findings if f.rule == "depends-prose"] == []


# ---------------------------------------------------------------- checks

def test_check_empty_fires_when_check_field_is_blank():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "neg_check_empty.md")
    hits = [f for f in findings if f.rule == "check-empty"]
    assert len(hits) == 1
    # fixture line 10: the `**Check:**` label carries no value at all. Full
    # Finding equality -- see the structure-rule tests above for why a
    # membership check alone leaves a wrong `task=`/`section=`/`line=` value
    # invisible.
    assert hits[0] == Finding(
        rule="check-empty",
        message=(
            "the `Check:` field is absent or empty; a task with no proving "
            "command has no definition of done"
        ),
        task="Task 1",
        section="Task 1: Empty check",
        line=10,
        evidence="",
        severity=ERROR,
    )


def test_check_empty_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "clean_plan.md")
    assert [f for f in findings if f.rule == "check-empty"] == []


def test_check_not_a_command_fires_and_check_command_is_empty_string():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "neg_check_not_a_command.md")
    hits = [f for f in findings if f.rule == "check-not-a-command"]
    assert len(hits) == 1
    # fixture line 10: the `Check:` value has one code span but prose text
    # surrounds it, so the span does not cover the whole value.
    assert hits[0] == Finding(
        rule="check-not-a-command",
        message=(
            "the `Check:` value is not EXACTLY one inline code span "
            "covering the whole value"
        ),
        task="Task 1",
        section="Task 1: Prose check",
        line=10,
        evidence="Check: run `pytest -q` after the migration",
        severity=ERROR,
    )
    doc = PlanDocument.from_path(FIXTURES / "neg_check_not_a_command.md")
    assert doc.task("Task 1").check_command == ""


def test_check_not_a_command_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "clean_plan.md")
    assert [f for f in findings if f.rule == "check-not-a-command"] == []


def test_check_placeholder_fires_on_unsubstituted_template_text():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "neg_check_placeholder.md")
    hits = [f for f in findings if f.rule == "check-placeholder"]
    assert len(hits) == 1
    # fixture line 10: the command still carries `exact/path/` and
    # `test_name`, both unsubstituted template placeholders.
    assert hits[0] == Finding(
        rule="check-placeholder",
        message=(
            "the `Check:` command still carries template placeholder text, "
            "so the task has no command that can prove its work"
        ),
        task="Task 1",
        section="Task 1: Unfilled template",
        line=10,
        evidence="Check: `pytest tests/exact/path/to/test.py::test_name -v`",
        severity=ERROR,
    )


def test_check_placeholder_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "clean_plan.md")
    assert [f for f in findings if f.rule == "check-placeholder"] == []


def test_check_placeholder_does_not_fire_on_a_pytest_parametrize_id():
    """A false positive from source review `7fd94a6e`: the old bare
    `\\[[^\\]]+\\]` pattern treated ANY bracketed content as a placeholder,
    so a real pytest parametrize ID (`[case1]`) tripped `check-placeholder`
    on a perfectly runnable command. `[case1]` is not drawn from the
    placeholder-word vocabulary, so the narrowed pattern must leave it
    alone."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Parametrized test\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest tests/test_foo.py::test_bar[case1]`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = tuple(f for f in checks.run(ctx).findings if f.rule == "check-placeholder")
    assert hits == ()


def test_check_placeholder_does_not_fire_on_real_angle_bracket_shell_content():
    """A false positive from source review `7fd94a6e`: the old bare
    `<[^>]+>` pattern treated ANY angle-bracketed content as a placeholder,
    so a real `grep` command matching HTML tag text (`<div>`) tripped
    `check-placeholder`. `div` is not drawn from the placeholder-word
    vocabulary, so the narrowed pattern must leave it alone."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Grep for a tag\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `grep -c '<div>' file.html`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = tuple(f for f in checks.run(ctx).findings if f.rule == "check-placeholder")
    assert hits == ()


def test_check_placeholder_does_not_fire_on_a_real_test_named_test_name():
    """A false positive from source review `7fd94a6e`: the old literal
    `\\btest_name\\b` pattern fired on the SUBSTRING, not on placeholder
    intent, so a real test function that happens to be named `test_name`
    tripped `check-placeholder` even though the command is fully
    substituted and runnable. The true-positive fixture
    (`neg_check_placeholder.md`) keeps firing without this pattern, because
    its command also carries the unsubstituted `exact/path/` literal."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Real test named test_name\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest tests/test_models.py::test_name`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = tuple(f for f in checks.run(ctx).findings if f.rule == "check-placeholder")
    assert hits == ()


def test_check_placeholder_fires_on_a_curly_brace_placeholder():
    """Closes a MEDIUM-severity false negative from `7fd94a6e`: a
    `{test_path}`-style curly-brace placeholder is unsubstituted template
    text just as much as `[test path]` or `<test path>`, and must fire the
    same way."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Curly brace placeholder\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest {test_path} -v`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = [f for f in checks.run(ctx).findings if f.rule == "check-placeholder"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="check-placeholder",
        message=(
            "the `Check:` command still carries template placeholder text, "
            "so the task has no command that can prove its work"
        ),
        task="Task 1",
        section="Task 1: Curly brace placeholder",
        line=10,
        evidence="Check: `pytest {test_path} -v`",
        severity=ERROR,
    )


def test_check_placeholder_fires_on_a_prose_placeholder_filename():
    """Closes a MEDIUM-severity false negative from `7fd94a6e`: a
    `your_test_file.py`-style prose placeholder (English words standing in
    for a real filename) is unsubstituted template text and must fire the
    same way as the other placeholder shapes."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Prose placeholder filename\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest your_test_file.py -v`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = [f for f in checks.run(ctx).findings if f.rule == "check-placeholder"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="check-placeholder",
        message=(
            "the `Check:` command still carries template placeholder text, "
            "so the task has no command that can prove its work"
        ),
        task="Task 1",
        section="Task 1: Prose placeholder filename",
        line=10,
        evidence="Check: `pytest your_test_file.py -v`",
        severity=ERROR,
    )


def test_check_placeholder_does_not_fire_on_a_hyphen_joined_key_value_pair():
    """MEDIUM finding: the old `[\\s_-]+`-joined multi-word combination
    pattern treated ANY pairing of vocabulary words as a placeholder, so
    real bracket content describing a key-value pair (`[key-value]`) tripped
    `check-placeholder` even though it is plausible real command syntax, not
    unsubstituted template text. Hyphen-joined pairs of vocabulary words no
    longer match; only a single vocabulary word, or an underscore-joined
    pair (the Python-identifier placeholder convention, e.g. `test_path`),
    fires."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Real key-value bracket content\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `jq '.[key-value]' file.json`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = tuple(f for f in checks.run(ctx).findings if f.rule == "check-placeholder")
    assert hits == ()


def test_check_placeholder_fires_case_insensitively_on_lowercase_todo():
    """Closes a MEDIUM-severity false negative from `7fd94a6e`: the
    placeholder markers `TODO`/`TBD`/`FIXME` are conventionally
    case-insensitive in prose (`todo:`, `Todo`, `ToDo`), and the old
    patterns only matched the all-caps spelling."""
    from spellbook.planlint.rules import checks

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Lowercase todo marker\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest tests/todo-fill-this-in.py -v`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = [f for f in checks.run(ctx).findings if f.rule == "check-placeholder"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="check-placeholder",
        message=(
            "the `Check:` command still carries template placeholder text, "
            "so the task has no command that can prove its work"
        ),
        task="Task 1",
        section="Task 1: Lowercase todo marker",
        line=10,
        evidence="Check: `pytest tests/todo-fill-this-in.py -v`",
        severity=ERROR,
    )


def test_check_not_runnable_fires_as_a_warning_on_a_prose_opener():
    from spellbook.planlint.finding import WARNING
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "neg_check_not_runnable.md")
    hits = [f for f in findings if f.rule == "check-not-runnable"]
    assert len(hits) == 1
    # fixture line 10: the command opens with "manually", a closed-list
    # prose opener, so this fires as a WARNING (a heuristic), not an ERROR.
    assert hits[0] == Finding(
        rule="check-not-runnable",
        message=(
            "the `Check:` command opens with a word from a closed "
            "prose-opener list and is likely a description, not a "
            "runnable command"
        ),
        task="Task 1",
        section="Task 1: Prose disguised as a command",
        line=10,
        evidence="Check: `manually confirm the daemon restarts`",
        severity=WARNING,
    )


def test_check_not_runnable_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import checks

    findings = _findings_for(checks, "clean_plan.md")
    assert [f for f in findings if f.rule == "check-not-runnable"] == []


# ------------------------------------------------------------ consistency

def test_check_verify_pass_consistency_fires_at_the_run_line_not_check_line():
    from spellbook.planlint.rules import consistency

    findings = _findings_for(consistency, "neg_check_verify_drift.md")
    hits = [f for f in findings if f.rule == "check-verify-pass-consistency"]
    assert len(hits) == 1
    doc = PlanDocument.from_path(FIXTURES / "neg_check_verify_drift.md")
    step4 = next(s for s in doc.task("Task 1").steps if s.number == 4)
    # Full Finding equality, not piecemeal fields: a mutation test proved a
    # wrong `task=`/`section=`/`message=` value leaves a `len(hits) == 1` +
    # `.line` assertion green. The evidence format is exactly
    #   f"Check: {command}  |  Step {n} Run: {run_command}"
    # — no backticks, no newline. Both halves must be named, because the
    # whole value of this finding is showing the reader the two commands
    # side by side.
    assert hits[0] == Finding(
        rule="check-verify-pass-consistency",
        message=(
            "the `Check:` field and the `Verify pass` step name "
            "different commands; `Check:` is the single source of "
            "truth and the step's `Run:` line must repeat it "
            "verbatim"
        ),
        task="Task 1",
        section="Task 1: Drifted verify step",
        line=step4.run_line,
        evidence=(
            "Check: pytest tests/x.py::test_a -v  |  "
            "Step 4 Run: pytest tests/x.py::test_a"
        ),
        severity=ERROR,
    )


def test_check_verify_pass_consistency_is_silent_when_the_two_match():
    from spellbook.planlint.rules import consistency

    findings = _findings_for(consistency, "neg_check_verify_drift.md")
    hits = [f for f in findings if f.rule == "check-verify-pass-consistency" and f.task == "Task 2"]
    assert hits == []


def test_check_verify_pass_consistency_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import consistency

    findings = _findings_for(consistency, "clean_plan.md")
    assert [f for f in findings if f.rule == "check-verify-pass-consistency"] == []


def test_check_verify_pass_consistency_reports_a_malformed_run_line_accurately():
    """Closes a review finding: `run_command` is empty in TWO source shapes
    (no `Run:` line under the step at all, OR a `Run:` line present but not
    a single well-formed backtick-wrapped command — e.g. missing backticks).
    The evidence text must not claim "has no Run: line" when a `Run:` line
    is right there in the source; it must be worded true of BOTH shapes.
    This test exercises the second shape, which the other three tests in
    this section never reach."""
    from spellbook.planlint.rules import consistency

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Malformed verify Run line\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest tests/x.py::test_a -v`\n\n"
        "**Step 4: Verify pass**\n"
        "Run: pytest tests/x.py::test_a -v\n"
        "Expected: PASS\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    hits = [
        f for f in consistency.run(ctx).findings
        if f.rule == "check-verify-pass-consistency"
    ]
    assert len(hits) == 1
    step4 = next(s for s in doc.task("Task 1").steps if s.number == 4)
    assert step4.run_command == ""  # the malformed shape under test: no backticks
    assert hits[0] == Finding(
        rule="check-verify-pass-consistency",
        message=(
            "the `Check:` field and the `Verify pass` step name "
            "different commands; `Check:` is the single source of "
            "truth and the step's `Run:` line must repeat it "
            "verbatim"
        ),
        task="Task 1",
        section="Task 1: Malformed verify Run line",
        line=step4.run_line,
        evidence=(
            "Check: pytest tests/x.py::test_a -v  |  "
            "Step 4 'Verify pass' has no valid Run: command line"
        ),
        severity=ERROR,
    )
