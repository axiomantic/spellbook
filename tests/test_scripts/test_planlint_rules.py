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
