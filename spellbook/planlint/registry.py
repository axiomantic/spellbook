"""The rule table and the per-rule error barrier.

RULES starts empty here and is grown by one row per rule module — Tasks 5-11
each append their own Rule(...) entry via a Modify to this file. Populating
the table incrementally (rather than importing all seven rule modules up
front, which do not exist yet at this point in the build order) keeps this
task's own Check line runnable in isolation.
"""

import dataclasses
import traceback
from pathlib import Path


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
    this same literal there. Enforced by
    `test_every_rule_result_name_matches_its_registry_row_name` (Task 18).
    """

    name: str
    run: object          # Callable[[RuleContext], LintResult]
    emits: frozenset      # every rule ID this module may put in a Finding
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
    which raises `TypeError` on a `str` — and that `TypeError` would be caught
    by `run_rules()`'s error barrier and reported as a rule CRASH rather than
    as the caller bug it is. Any boundary that receives a string (argparse in
    `cli.py`, an operator-supplied value) coerces at that boundary, before
    constructing this dataclass. `None` means "path existence is undecidable
    here" and makes `rules/files.py` return a skipped result — never a clean
    one.
    """

    doc: object            # PlanDocument
    phase: object           # Phase, or None (see docstring)
    repo_root: "Path | None"


@dataclasses.dataclass(frozen=True)
class RuleCrash:
    rule: str
    exc_type: str
    message: str
    traceback_text: str


RULES = ()


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
    for rule in RULES:
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
