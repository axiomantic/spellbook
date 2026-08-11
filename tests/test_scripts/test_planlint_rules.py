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
    from spellbook.planlint.rules import structure

    findings = _findings_for(structure, "neg_unmatched_backtick.md")
    hits = [f for f in findings if f.rule == "unmatched-backtick"]
    assert len(hits) == 1
    # fixture line 10 is the `**Check:**` line, which carries 3 backticks —
    # one pair plus one unmatched opener. See the fixture's line table.
    assert hits[0].line == 10


def test_unmatched_backtick_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import structure

    findings = _findings_for(structure, "clean_plan.md")
    assert [f for f in findings if f.rule == "unmatched-backtick"] == []


def test_unclosed_fence_fires_at_the_opening_line():
    from spellbook.planlint.rules import structure

    findings = _findings_for(structure, "neg_unclosed_fence.md")
    hits = [f for f in findings if f.rule == "unclosed-fence"]
    assert len(hits) == 1
    # fixture line 13 is the opening fence with no partner. See the line table.
    assert hits[0].line == 13


def test_unclosed_fence_does_not_hide_tasks_below_it():
    """The second assertion that would have caught source defect L-5: the
    plan must still parse both Task 2 and Task 3 below the broken fence."""
    doc = PlanDocument.from_path(FIXTURES / "neg_unclosed_fence.md")
    assert doc.has_task("Task 2")
    assert doc.has_task("Task 3")


def test_unclosed_fence_is_absent_on_the_clean_fixture():
    from spellbook.planlint.rules import structure

    findings = _findings_for(structure, "clean_plan.md")
    assert [f for f in findings if f.rule == "unclosed-fence"] == []
