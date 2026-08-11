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
from spellbook.planlint.finding import ERROR, Finding, LintResult
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


def test_check_verify_pass_consistency_selects_the_first_verify_pass_step():
    """Coverage gap: a task with TWO steps whose titles both match the
    `Verify pass` pattern. `run()` uses `next()` to pick the first match —
    a deliberate, documented policy (see the comment above the `next()` call
    in `consistency.py`). This fixture makes the FIRST step's `Run:` command
    match `Check:` exactly and the SECOND step's `Run:` command differ, so
    the test only stays green if the rule really compares against the first
    occurrence: last-match (or any other) selection would flag the second
    step's drift and this assertion would fail."""
    from spellbook.planlint.rules import consistency

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: Two verify-pass steps\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest tests/x.py::test_a -v`\n\n"
        "**Step 3: Verify pass**\n"
        "Run: `pytest tests/x.py::test_a -v`\n"
        "Expected: PASS\n\n"
        "**Step 5: Verify pass**\n"
        "Run: `pytest tests/x.py::test_b -v`\n"
        "Expected: PASS\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    task = doc.task("Task 1")
    # Sanity: the fixture really has two steps whose title matches the
    # rule's pattern, and their Run: commands really differ from each
    # other — otherwise this test would pass for the wrong reason.
    assert [s.title for s in task.steps] == ["Verify pass", "Verify pass"]
    assert task.steps[0].run_command == "pytest tests/x.py::test_a -v"
    assert task.steps[1].run_command == "pytest tests/x.py::test_b -v"
    assert task.check_command == "pytest tests/x.py::test_a -v"

    hits = [
        f for f in consistency.run(ctx).findings
        if f.rule == "check-verify-pass-consistency"
    ]
    assert hits == []


def test_check_verify_pass_consistency_is_silent_with_no_verify_pass_step():
    """Coverage gap: a task with a real `Check:` command and steps present,
    but none of the step titles match the `Verify pass` pattern. Exercises
    the `verify_step is None: continue` early-exit — the rule must not
    crash or false-positive when there is nothing to compare `Check:`
    against."""
    from spellbook.planlint.rules import consistency

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: No verify-pass step\n\n"
        "**Files:**\n- Create: `x.py`\n\n"
        "**Depends:** none\n\n"
        "**Check:** `pytest tests/x.py::test_a -v`\n\n"
        "**Step 1: Implement**\n"
        "Run: `pytest tests/x.py::test_a -v`\n"
        "Expected: PASS\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.REVIEW, repo_root=None)
    task = doc.task("Task 1")
    assert [s.title for s in task.steps] == ["Implement"]
    assert task.check_command == "pytest tests/x.py::test_a -v"

    hits = [
        f for f in consistency.run(ctx).findings
        if f.rule == "check-verify-pass-consistency"
    ]
    assert hits == []


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


# ------------------------------------------------------------------ files

def test_modify_path_missing_fires_only_on_the_absent_path(tmp_path):
    from spellbook.planlint.rules import files

    (tmp_path / "real.py").write_text("# real\n", encoding="utf-8")
    ctx = _ctx("neg_modify_path_missing.md", repo_root=tmp_path)
    findings = files.run(ctx).findings
    hits = [f for f in findings if f.rule == "modify-path-missing"]
    assert len(hits) == 1
    resolved = tmp_path / "does_not_exist.py"
    assert hits[0] == Finding(
        rule="modify-path-missing",
        message=(
            "a `Modify:` entry names a path that does not exist in the "
            "repository, so the task is planned against a tree that is not "
            "there"
        ),
        task="Task 2",
        section="Task 2: Modifies a missing file",
        line=15,
        evidence=f"- Modify: `does_not_exist.py` (resolved: {resolved})",
        severity=ERROR,
    )


def test_modify_path_missing_is_absent_on_the_clean_fixture(tmp_path):
    from spellbook.planlint.rules import files

    (tmp_path / "spellbook" / "sample").mkdir(parents=True)
    (tmp_path / "spellbook" / "sample" / "first.py").write_text("# x\n", encoding="utf-8")
    ctx = _ctx("clean_plan.md", repo_root=tmp_path)
    findings = files.run(ctx).findings
    assert [f for f in findings if f.rule == "modify-path-missing"] == []


def test_modify_path_missing_does_not_fire_on_a_test_entry(tmp_path):
    """A `Test:` path that does not exist is the NORMAL TDD case, not a defect.

    This is the assertion that keeps the rule usable: every plan writing-plans
    emits names a not-yet-written test file, so a rule that checked `Test:`
    would fire on every correct plan. `clean_plan.md`'s own two `Test:` entries
    are absent from the tree built here, and the rule must stay silent about
    both while still deciding the `Modify:` entry beside them."""
    from spellbook.planlint.rules import files

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n**Files:**\n"
        "- Modify: `present.py`\n"
        "- Test: `tests/not_written_yet.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    (tmp_path / "present.py").write_text("# here\n", encoding="utf-8")
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.AUTHORING, repo_root=tmp_path)
    assert [f for f in files.run(ctx).findings if f.rule == "modify-path-missing"] == []


def test_files_rule_skips_and_reports_undecided_when_repo_root_is_none():
    from spellbook.planlint.rules import files

    ctx = _ctx("neg_modify_path_missing.md", repo_root=None)
    result = files.run(ctx)
    assert result.findings == []
    assert result.skipped_reason == "no repo_root supplied"


def test_files_rule_reports_no_input_when_no_files_entries_are_examined(tmp_path):
    """A schema-declaring plan whose tasks carry no `Files:` bullets at all
    (or only `Test:`/`Delete:` bullets, which this rule never examines) must
    NOT report clean. `guard_no_input` is the mechanism every other rule
    module already routes through for this — `files.py` was the one holdout
    that returned a bare `LintResult()` and reported a false clean instead."""
    from spellbook.planlint.rules import files

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n**Files:**\n"
        "- Test: `tests/not_written_yet.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.AUTHORING, repo_root=tmp_path)
    result = files.run(ctx)
    assert result == LintResult(
        name="files",
        findings=[
            Finding(
                rule="no-input",
                message="the files lint examined 0 Files: entries",
                severity=ERROR,
            )
        ],
        examined=0,
        examined_label="Files: entries",
    )


def test_files_rule_counts_only_entries_that_pass_the_path_guards(tmp_path):
    """`examined` must count an entry only after the absolute-path and
    traversal guards let it through — never before. A plan whose ONLY
    `Files:` entries are one absolute path and one traversal path (both
    guarded out, both `Modify:` so `create-path-exists`'s guard tests above
    do not already cover this) must land at `examined == 0` and trip the
    same `guard_no_input` `no-input` finding as a plan with zero `Files:`
    bullets at all — proving the counter sits after the guards, not before
    them. A regression that moves `examined += 1` back above the guards
    would instead report `examined == 2` and no `no-input` finding here."""
    from spellbook.planlint.rules import files

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n**Files:**\n"
        "- Modify: `/etc/passwd`\n"
        "- Modify: `../sibling_target.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.AUTHORING, repo_root=tmp_path)
    result = files.run(ctx)
    assert result == LintResult(
        name="files",
        findings=[
            Finding(
                rule="no-input",
                message="the files lint examined 0 Files: entries",
                severity=ERROR,
            )
        ],
        examined=0,
        examined_label="Files: entries",
    )


def test_create_path_exists_fires_when_a_create_path_already_exists(tmp_path):
    from spellbook.planlint.finding import WARNING
    from spellbook.planlint.rules import files

    (tmp_path / "already_here.py").write_text("# here\n", encoding="utf-8")
    ctx = _ctx(
        "neg_create_path_exists.md", phase=_Phase.AUTHORING, repo_root=tmp_path
    )
    findings = files.run(ctx).findings
    hits = [f for f in findings if f.rule == "create-path-exists"]
    assert len(hits) == 1
    resolved = tmp_path / "already_here.py"
    assert hits[0] == Finding(
        rule="create-path-exists",
        message=(
            "a `Create:` path already exists; this is almost "
            "always a mislabeled `Modify:`"
        ),
        task="Task 1",
        section="Task 1: Creates a path that is already there",
        line=6,
        evidence=f"- Create: `already_here.py` (resolved: {resolved})",
        severity=WARNING,
    )


def test_create_path_exists_is_absent_when_the_create_path_does_not_exist(tmp_path):
    """The negative control for the rule above. `clean_plan.md` cannot serve
    as this control — the tmp tree that makes `modify-path-missing` clean
    there necessarily makes `create-path-exists` fire — so the control is the
    SAME fixture against an empty tree."""
    from spellbook.planlint.rules import files

    ctx = _ctx(
        "neg_create_path_exists.md", phase=_Phase.AUTHORING, repo_root=tmp_path
    )
    assert [f for f in files.run(ctx).findings if f.rule == "create-path-exists"] == []


def test_create_path_exists_is_off_in_execution_phase(tmp_path):
    """`_create_severity` returns None for the execution phase, and the rule
    must not fire at all in that branch — not merely carry a null severity.
    `already_here.py` genuinely exists on disk (per `create-path-exists`'s
    positive test above), so if the OFF-in-execution branch were broken the
    rule would incorrectly report a finding here."""
    from spellbook.planlint.rules import files

    (tmp_path / "already_here.py").write_text("# here\n", encoding="utf-8")
    ctx = _ctx(
        "neg_create_path_exists.md", phase=_Phase.EXECUTION, repo_root=tmp_path
    )
    assert files.run(ctx).findings == []


def test_modify_path_missing_skips_an_absolute_path_entry(tmp_path):
    """An absolute path in a `Modify:` bullet must never reach a real
    filesystem call outside repo_root. `pathlib`'s `__truediv__` silently
    DISCARDS the left operand when the right is absolute
    (`Path("/a/b") / "/etc/passwd" == Path("/etc/passwd")`), so without the
    guard `ctx.repo_root / entry.path` would resolve to the real `/etc/passwd`
    on the machine running the test, which exists on macOS/Linux — a naive
    "does it exist" check would then stay silent (real file exists), masking
    the fact that the check ran outside the repo at all. The construction
    below proves the guard: `create-path-exists` fires on `already_here.py`
    existing inside `repo_root`, but the absolute-path entry, if it escaped
    the guard and resolved to a real, existing `/etc/passwd`, would ALSO
    trip `create-path-exists` for that entry. Asserting there is exactly one
    hit — the legitimate one — proves the absolute entry never got that far."""
    from spellbook.planlint.rules import files

    (tmp_path / "already_here.py").write_text("# here\n", encoding="utf-8")
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: X\n\n**Files:**\n"
        "- Create: `already_here.py`\n"
        "- Create: `/etc/passwd`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=_Phase.AUTHORING, repo_root=tmp_path)
    hits = [f for f in files.run(ctx).findings if f.rule == "create-path-exists"]
    assert len(hits) == 1
    assert "already_here.py" in hits[0].evidence
    assert "/etc/passwd" not in hits[0].evidence


def test_modify_path_missing_skips_a_traversal_escaping_path_entry(tmp_path):
    """Same escape, reached via `..`-traversal instead of an absolute path.

    This does NOT rely on the real `/etc/passwd` or on `tmp_path`'s actual
    nesting depth (pytest's tmp tree is many directories deep, e.g.
    `/private/var/folders/.../pytest-NNNN/test_name0/`, so a fixed number of
    `..` segments like `../../` only climbs INSIDE that tree and never
    reaches the real `/etc/passwd` — a construction that would pass whether
    or not the guard exists, since `resolved.exists()` is `False` either
    way). Instead this exercises the guard's actual decision directly: a
    genuinely-existing SIBLING of `repo_root` stands in for "a real path
    outside the repo". `../sibling_target.py`, resolved against
    `repo_root == tmp_path`, lands at `tmp_path.parent /
    "sibling_target.py"` — outside `repo_root` by construction, regardless
    of how deep `tmp_path` sits on this machine — and that file is created
    so it genuinely exists on disk. Absent the guard, `create-path-exists`
    would fire a SECOND, bogus hit for it. Asserting exactly one hit (the
    legitimate `already_here.py` one) proves the traversal entry never
    reached the filesystem check."""
    from spellbook.planlint.rules import files

    (tmp_path / "already_here.py").write_text("# here\n", encoding="utf-8")
    sibling = tmp_path.parent / "sibling_target.py"
    sibling.write_text("# outside repo_root\n", encoding="utf-8")
    try:
        text = (
            "**Schema:** planlint-v1\n\n"
            "### Task 1: X\n\n**Files:**\n"
            "- Create: `already_here.py`\n"
            "- Create: `../sibling_target.py`\n\n"
            "**Depends:** none\n\n**Check:** `pytest -q`\n"
        )
        doc = PlanDocument.from_text(text)
        ctx = registry.RuleContext(doc=doc, phase=_Phase.AUTHORING, repo_root=tmp_path)
        hits = [f for f in files.run(ctx).findings if f.rule == "create-path-exists"]
        assert len(hits) == 1
        assert "already_here.py" in hits[0].evidence
        assert "sibling_target.py" not in hits[0].evidence
    finally:
        sibling.unlink(missing_ok=True)


# --------------------------------------------------------------- ownership

def test_shared_path_without_owner_fires_when_no_edge_no_annotation():
    """Two tasks `Modify:` the same path; neither an owner annotation nor a
    `Depends:` edge orders them. Full `Finding` equality — not just
    `len(hits) == 1` plus a substring check on `.evidence` — proves `task`,
    `section`, and `.line` all point at the FIRST claimant's bullet (Task 2,
    fixture line 15), and that `.evidence` names both claimants with their
    (absent) annotations rather than merely containing their names somewhere
    in a longer string a wrong implementation could also produce."""
    from spellbook.planlint.finding import WARNING
    from spellbook.planlint.rules import ownership

    findings = _findings_for(ownership, "neg_shared_path_no_owner.md")
    hits = [f for f in findings if f.rule == "shared-path-without-owner"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="shared-path-without-owner",
        message=(
            "two or more tasks write this path, they do not all name the "
            "same `(owner: Task N)`, and no `Depends:` edge orders them; "
            "the writes may race"
        ),
        task="Task 2",
        section="Task 2: First writer",
        line=15,
        evidence=(
            "shared.py claimed by Task 2, Task 5 "
            "(annotations: Task 2=-, Task 5=-; no dependency path between "
            "Task 2 and Task 5)"
        ),
        severity=WARNING,
    )


def test_shared_path_without_owner_is_silent_when_a_depends_edge_orders_them():
    from spellbook.planlint.rules import ownership

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 2: First writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n\n"
        "### Task 5: Second writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** Task 2\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=None, repo_root=None)
    findings = ownership.run(ctx).findings
    assert [f for f in findings if f.rule == "shared-path-without-owner"] == []


def test_shared_path_without_owner_is_silent_with_an_owner_annotation():
    from spellbook.planlint.rules import ownership

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 2: First writer\n\n**Files:**\n"
        "- Modify: `shared.py` (owner: Task 2)\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n\n"
        "### Task 5: Second writer\n\n**Files:**\n"
        "- Modify: `shared.py` (owner: Task 2)\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=None, repo_root=None)
    findings = ownership.run(ctx).findings
    assert [f for f in findings if f.rule == "shared-path-without-owner"] == []


def test_shared_path_without_owner_still_fires_when_only_one_of_three_is_annotated():
    """ONE annotation does not coordinate THREE writers.

    Task 3 declares Task 2 the owner; Tasks 2 and 5 write the same path with no
    annotation and no edge between them. Suppressing on `any` annotation would
    silence this, which would mean the rule gets cheaper to defeat the more
    writers a path collects — backwards from what the finding is worth.

    Full `Finding` equality (not a bare substring check) proves the reported
    `task`/`section`/`.line` are the FIRST claimant's (Task 2, line 6 of this
    inline text) and that `.evidence` lists all THREE claimants with their
    respective annotations — including Task 3's real `owner: Task 2` — rather
    than an implementation that happens to mention "Task 5" somewhere."""
    from spellbook.planlint.finding import WARNING
    from spellbook.planlint.rules import ownership

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 2: First writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n\n"
        "### Task 3: Annotated writer\n\n**Files:**\n"
        "- Modify: `shared.py` (owner: Task 2)\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n\n"
        "### Task 5: Unannotated writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=None, repo_root=None)
    findings = ownership.run(ctx).findings
    hits = [f for f in findings if f.rule == "shared-path-without-owner"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="shared-path-without-owner",
        message=(
            "two or more tasks write this path, they do not all name the "
            "same `(owner: Task N)`, and no `Depends:` edge orders them; "
            "the writes may race"
        ),
        task="Task 2",
        section="Task 2: First writer",
        line=6,
        evidence=(
            "shared.py claimed by Task 2, Task 3, Task 5 "
            "(annotations: Task 2=-, Task 3=Task 2, Task 5=-; no dependency "
            "path between Task 2 and Task 3, or Task 2 and Task 5, or "
            "Task 3 and Task 5)"
        ),
        severity=WARNING,
    )


def test_shared_path_without_owner_is_partial_ordering_names_only_the_unordered_pair():
    """3 writers where ONE pair IS ordered via `Depends:` and the third task is
    unconnected to either. The finding still fires (the group as a whole is not
    resolved), but the evidence must name only the pairs that are ACTUALLY
    unordered (Task 2/Task 7 and Task 3/Task 7) rather than falsely claiming no
    ordering exists anywhere — Task 2 -> Task 3 IS ordered via Depends.

    Full `Finding` equality proves the evidence text does not regress to the
    blanket "no dependency path in either direction" phrasing this test guards
    against."""
    from spellbook.planlint.finding import WARNING
    from spellbook.planlint.rules import ownership

    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 2: First writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n\n"
        "### Task 3: Ordered writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** Task 2\n\n**Check:** `pytest -q`\n\n"
        "### Task 7: Unordered writer\n\n**Files:**\n- Modify: `shared.py`\n\n"
        "**Depends:** none\n\n**Check:** `pytest -q`\n"
    )
    doc = PlanDocument.from_text(text)
    ctx = registry.RuleContext(doc=doc, phase=None, repo_root=None)
    findings = ownership.run(ctx).findings
    hits = [f for f in findings if f.rule == "shared-path-without-owner"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="shared-path-without-owner",
        message=(
            "two or more tasks write this path, they do not all name the "
            "same `(owner: Task N)`, and no `Depends:` edge orders them; "
            "the writes may race"
        ),
        task="Task 2",
        section="Task 2: First writer",
        line=6,
        evidence=(
            "shared.py claimed by Task 2, Task 3, Task 7 "
            "(annotations: Task 2=-, Task 3=-, Task 7=-; no dependency "
            "path between Task 2 and Task 7, or Task 3 and Task 7)"
        ),
        severity=WARNING,
    )


def test_shared_path_without_owner_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import ownership

    findings = _findings_for(ownership, "clean_plan.md")
    assert [f for f in findings if f.rule == "shared-path-without-owner"] == []


# ------------------------------------------------------------------ schema

def test_schema_conflict_fires_and_plan_is_still_linted():
    """The plan-level `Schema:` (line 1, `planlint-v1`) and Task 2's own
    `Schema:` (line 21, `legacy`) disagree. Full `Finding` equality proves the
    reported owner is the FIRST value encountered (the plan header, so
    `task=""`), `.line` is that value's own line, and `.evidence` lists both
    disagreeing values with their owners.

    `section=""` (not `doc.tasks[0].section`): line 1 sits before ANY
    heading, so the correct answer from `doc.section_at_line(1)` is the
    empty string — proving the finding's section is computed from the
    reported line's own position, not hardcoded to the first task.

    The plan IS linted despite the conflict — asserted as WORK DONE, not as
    a type. A rule that returned an empty list without looking at anything
    would satisfy `isinstance(..., list)`; only `examined` proves the two
    task blocks were actually read, and only an empty `skipped_reason`
    proves the result is a decision rather than an abstention."""
    from spellbook.planlint.rules import schema, structure

    findings = _findings_for(schema, "neg_schema_conflict.md")
    hits = [f for f in findings if f.rule == "schema-conflict"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="schema-conflict",
        message=(
            "the plan-level `Schema:` and a task-level `Schema:` "
            "disagree, or two tasks disagree"
        ),
        task="",
        section="",
        line=1,
        evidence="<plan header>: planlint-v1, Task 2: legacy",
        severity=ERROR,
    )

    structure_result = structure.run(_ctx("neg_schema_conflict.md"))
    assert structure_result.examined == 2      # Task 1 and Task 2 both read
    assert structure_result.skipped_reason == ""
    assert structure_result.findings == []     # and it decided them clean


def test_schema_conflict_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import schema

    findings = _findings_for(schema, "clean_plan.md")
    assert [f for f in findings if f.rule == "schema-conflict"] == []


def test_schema_unknown_version_names_the_bad_value():
    """The plan-level `Schema:` on line 1 declares `planlint-v2`, which is
    neither `planlint-v1` nor `legacy`. Full `Finding` equality proves the
    reported owner is the plan header (`task=""`), `.line` is 1, and
    `.evidence` names the exact unrecognized value.

    `section=""`: line 1 precedes any heading, so `doc.section_at_line(1)`
    is the empty string — same reasoning as the schema-conflict test above."""
    from spellbook.planlint.rules import schema

    findings = _findings_for(schema, "neg_schema_unknown_version.md")
    hits = [f for f in findings if f.rule == "schema-unknown-version"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="schema-unknown-version",
        message=(
            "a `Schema:` value is neither `planlint-v1` nor `legacy`; "
            "a plan declaring an unrecognized schema must say so "
            "rather than be linted under the wrong rules"
        ),
        task="",
        section="",
        line=1,
        evidence="Schema: planlint-v2",
        severity=ERROR,
    )


def test_schema_unknown_version_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import schema

    findings = _findings_for(schema, "clean_plan.md")
    assert [f for f in findings if f.rule == "schema-unknown-version"] == []


def test_schema_fallback_reports_once_not_as_a_fake_plan_header():
    """No TRUE plan-level `Schema:` header precedes Task 1 (there is no
    `Schema:` line before line 1's `### Task 1: A`), so
    `document.py`'s `_resolve_plan_schema()` falls back to COPYING Task 1's
    own `Schema:` (`planlint-v9`, line 10) into `doc.schema_text` /
    `doc.schema_line`.

    Before the fix, `schema.py` did not know this was a copy: it read
    `doc.schema_text` as an independent plan-level declaration AND read
    Task 1's own `schema_text`, reporting the SAME single declaration
    TWICE — once as `task=""` (`<plan header>`) and once as `task="Task 1"`.
    Full `Finding` equality proves there is exactly one finding, it is
    attributed to Task 1 (not `task=""`), and its section is Task 1's own
    section (not a synthetic plan-level one)."""
    from spellbook.planlint.rules import schema

    findings = _findings_for(schema, "neg_schema_fallback_unknown_version.md")

    conflict_hits = [f for f in findings if f.rule == "schema-conflict"]
    assert conflict_hits == []

    hits = [f for f in findings if f.rule == "schema-unknown-version"]
    assert len(hits) == 1
    assert hits[0] == Finding(
        rule="schema-unknown-version",
        message=(
            "a `Schema:` value is neither `planlint-v1` nor `legacy`; "
            "a plan declaring an unrecognized schema must say so "
            "rather than be linted under the wrong rules"
        ),
        task="Task 1",
        section="Task 1: A",
        line=10,
        evidence="Schema: planlint-v9",
        severity=ERROR,
    )


def test_schema_conflict_and_unknown_version_attribute_section_to_owning_task():
    """A GENUINE plan-level header (`planlint-v1`, line 1, before any
    heading) conflicts with Task 2's own `Schema:` (`planlint-v9`, line 25,
    under the `## Group B` / `### Task 2: B` headings).

    Before the fix, EVERY finding's `section` was hardcoded to
    `doc.tasks[0].section` (`"Task 1: A"`) regardless of which line/task the
    finding actually belongs to. Full `Finding` equality on both findings
    proves `section` now tracks the OWNING line via `doc.section_at_line()`:
    the plan-header-owned `schema-conflict` finding gets `""` (line 1
    precedes every heading), while the Task-2-owned `schema-unknown-version`
    finding gets `"Task 2: B"` — neither of which is `doc.tasks[0].section`,
    so a regression back to the hardcoded value would fail both."""
    from spellbook.planlint.rules import schema

    findings = _findings_for(schema, "neg_schema_conflict_task_section.md")

    conflict_hits = [f for f in findings if f.rule == "schema-conflict"]
    assert len(conflict_hits) == 1
    assert conflict_hits[0] == Finding(
        rule="schema-conflict",
        message=(
            "the plan-level `Schema:` and a task-level `Schema:` "
            "disagree, or two tasks disagree"
        ),
        task="",
        section="",
        line=1,
        evidence="<plan header>: planlint-v1, Task 2: planlint-v9",
        severity=ERROR,
    )

    unknown_hits = [f for f in findings if f.rule == "schema-unknown-version"]
    assert len(unknown_hits) == 1
    assert unknown_hits[0] == Finding(
        rule="schema-unknown-version",
        message=(
            "a `Schema:` value is neither `planlint-v1` nor `legacy`; "
            "a plan declaring an unrecognized schema must say so "
            "rather than be linted under the wrong rules"
        ),
        task="Task 2",
        section="Task 2: B",
        line=25,
        evidence="Schema: planlint-v9",
        severity=ERROR,
    )
