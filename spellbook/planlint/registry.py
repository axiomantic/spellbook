"""The rule table and the per-rule error barrier.

RULES starts empty here and is grown by one row per rule module — Tasks 5-11
each append their own Rule(...) entry via a Modify to this file. Populating
the table incrementally (rather than importing all seven rule modules up
front, which do not exist yet at this point in the build order) keeps this
task's own Check line runnable in isolation.
"""

import dataclasses
import traceback
from collections.abc import Callable
from pathlib import Path

from spellbook.planlint.document import PlanDocument
from spellbook.planlint.finding import LintResult
from spellbook.planlint.rules import checks, consistency, depends, structure


@dataclasses.dataclass(frozen=True)
class Rule:
    """One row of the rule table.

    INVARIANT: `name` must equal the `LintResult.name` the rule's own `run`
    returns. `api.decided_claims()` builds its per-rule verdict list from
    `LintResult.name` alone, and `reviewing-impl-plans`'s Phase 0 report
    (design §3.2.2) names rules from that list. If the two disagree, the
    review report attributes a claim to a rule that did not decide it, or
    reports a rule as absent that ran — a wrong fact in a review gate, which
    is worse than a missing one. `guard_no_input(name=...)` is the single
    place the returned name is set, so keeping the two in step means passing
    this same literal there. Will be enforced by
    `test_every_rule_result_name_matches_its_registry_row_name`, added in
    Task 18 (not yet written).
    """

    name: str
    run: Callable[["RuleContext"], LintResult]
    emits: frozenset[str]  # every rule ID this module may put in a Finding
    phases: frozenset     # the Phase values in which it runs


@dataclasses.dataclass(frozen=True)
class RuleContext:
    """Everything a rule is allowed to see. Frozen: a rule never mutates it.

    `phase` — a `Phase` member, or `None`. The two readings differ and both
    are deliberate:
      * Under `run_rules()`, `None` causes EVERY rule to be skipped, because
        the dispatch test is `ctx.phase not in rule.phases` and `None` is a
        member of no rule's `frozenset(Phase)`. A caller that means "run
        everything" passes a real Phase; `None` is not a wildcard.
      * Under a DIRECT call (`rule_module.run(ctx)`, which is how every
        rule-level test in `test_planlint_rules.py` invokes a rule), there is
        no dispatch test, so `None` simply means phase-gated behavior is off:
        `rules/files.py` reads `getattr(ctx.phase, "value", ctx.phase)` and
        computes no `create-path-exists` severity, and every phase-blind rule
        behaves exactly as it would under any phase.

    `repo_root` — a `pathlib.Path`, or `None`. COERCION CONTRACT: callers pass
    a `Path`, never a `str`. `rules/files.py` does `ctx.repo_root / entry.path`,
    where `entry.path` is `FilesEntry.path`, typed `str` in `document.py` — so
    a `str` `repo_root` makes that expression `str / str`, which raises
    `TypeError` — and that `TypeError` would be caught by `run_rules()`'s
    error barrier and reported as a rule CRASH rather than as the caller bug
    it is. Any boundary that receives a string (argparse in `cli.py`, an
    operator-supplied value) coerces at that boundary, before constructing
    this dataclass. `None` means "path existence is undecidable here" and
    makes `rules/files.py` return a skipped result — never a clean one.
    """

    doc: PlanDocument
    phase: object           # Phase, or None (see docstring)
    repo_root: "Path | None"


@dataclasses.dataclass(frozen=True)
class RuleCrash:
    rule: str
    exc_type: str
    message: str
    traceback_text: str


RULES = (
    Rule(
        name="structure",
        run=structure.run,
        emits=structure.EMITS,
        phases=frozenset(
            {"authoring", "review", "execution"}
        ),  # placeholder set of phase VALUES; Task 12 replaces this with
            # frozenset(Phase) once api.Phase exists. Every subsequent rule
            # task's registry.py edit uses this same placeholder until Task 12.
    ),
    Rule(
        name="depends",
        run=depends.run,
        emits=depends.EMITS,
        phases=frozenset({"authoring", "review", "execution"}),
    ),
    Rule(
        name="checks",
        run=checks.run,
        emits=checks.EMITS,
        phases=frozenset({"authoring", "review", "execution"}),
    ),
    Rule(
        name="consistency",
        run=consistency.run,
        emits=consistency.EMITS,
        phases=frozenset({"authoring", "review", "execution"}),
    ),
)


def _rules():
    """Indirection over the module-level `RULES` tuple.

    `RULES` itself is plain data (a tuple), not a callable, so it cannot be
    substituted via `tripwire.mock()` — tripwire replaces call sites, not
    data attributes. This thin wrapper gives tests a callable seam to mock,
    per AGENTS.md's "if tripwire can't express what you need, refactor the
    code under test" guidance.
    """
    return RULES


def run_rules(ctx):
    """(results, crashes). One rule's crash never stops another rule.

    The blanket `except Exception` below is the ONLY such barrier in this
    package (every other module raises normally); it swallows nothing (type,
    message, and full traceback are preserved in RuleCrash, surfaced in
    PlanLintReport.report(), and counted by PlanLintReport.failed); and its
    absence has a worse failure mode (one rule's KeyError on an odd markdown
    shape would take down the plan-file write in executing-plans).
    KeyboardInterrupt and SystemExit derive from BaseException, not
    Exception, so this barrier does not catch them — asserted by
    test_run_rules_barrier_does_not_catch_keyboardinterrupt.
    """
    results, crashes = [], []
    for rule in _rules():
        if ctx.phase not in rule.phases:
            continue
        try:
            results.append(rule.run(ctx))
        except Exception as exc:
            crashes.append(
                RuleCrash(
                    rule=rule.name,
                    exc_type=type(exc).__name__,
                    message=str(exc),
                    traceback_text=traceback.format_exc(),
                )
            )
    return tuple(results), tuple(crashes)
