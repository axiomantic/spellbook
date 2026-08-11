"""check-verify-pass-consistency — `Check:` and the `Verify pass` step must
name the same command. ERROR. NEW rule, no nmg2-tools precedent.

`Check:` is the single source of truth. The invariant this rule ENFORCES is
that the Verify pass step's `Run:` line is copied from `Check:` at
generation time, so the two start identical and can only diverge by a later
hand edit to one and not the other.

That invariant is a TARGET, not a description of today's generator. The
writing-plans template does not yet copy the line; the edit that makes it do
so is Task 19, and this rule ships first ON PURPOSE — a rule that only
becomes true after its enforcement point exists is a rule nobody ever runs
against the plans written in between. Until Task 19 lands, a
`check-verify-pass-consistency` finding on a freshly generated plan is a
correct report about a generator that has not been fixed yet, not a false
positive. Task 22's §9.8 check closes the loop by running this rule over the
Task-19 template itself and asserting zero findings.

Comparison is whitespace-only (collapse internal runs of whitespace, strip
the ends) — deliberately narrow; a richer comparison would make the rule
decide questions it cannot decide (design §4.3).
"""

import re

from spellbook.planlint.finding import ERROR, Finding, guard_no_input

EMITS = frozenset({"check-verify-pass-consistency"})

VERIFY_PASS_TITLE = re.compile(r"(?i)^verify\s+pass$")
_WHITESPACE = re.compile(r"\s+")


def _normalize(text):
    return _WHITESPACE.sub(" ", text).strip()


def run(ctx):
    doc = ctx.doc
    findings = []

    for task in doc.tasks:
        command = task.check_command
        if not command:
            continue  # check-empty / check-not-a-command own this case

        verify_step = next(
            (s for s in task.steps if VERIFY_PASS_TITLE.match(s.title)), None
        )
        if verify_step is None:
            continue  # no such step; not every task has one
        # A task with more than one "Verify pass" step is itself malformed,
        # but no other rule in this package flags it, and inventing one is
        # out of scope here. `next()` picking the first occurrence is a
        # deliberate, minimal choice: it still reports A real drift rather
        # than reporting nothing, and does not silently pick and hide a
        # second, possibly-differently-drifted step.

        if not verify_step.run_command:
            # `run_command` is empty in TWO distinct source shapes, and Step
            # does not retain enough to tell them apart: no `Run:` line under
            # this step at all (`run_line` is 0), or a `Run:` line that IS
            # present but fails `document.py`'s single-backtick-span parse
            # (missing backticks, multiple spans, an unmatched backtick — see
            # `PlanDocument._scan_steps`). Claiming "has no Run: line" would
            # be false in the second shape: the line is right there in the
            # source, just not parseable as one command. The wording below is
            # true of both shapes, so it never mislabels the malformed case.
            findings.append(
                Finding(
                    rule="check-verify-pass-consistency",
                    message=(
                        "the `Check:` field and the `Verify pass` step name "
                        "different commands; `Check:` is the single source of "
                        "truth and the step's `Run:` line must repeat it "
                        "verbatim"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=verify_step.run_line or verify_step.line,
                    evidence=(
                        f"Check: {command}  |  Step {verify_step.number} "
                        "'Verify pass' has no valid Run: command line"
                    ),
                    severity=ERROR,
                )
            )
            continue

        if _normalize(command) != _normalize(verify_step.run_command):
            findings.append(
                Finding(
                    rule="check-verify-pass-consistency",
                    message=(
                        "the `Check:` field and the `Verify pass` step name "
                        "different commands; `Check:` is the single source of "
                        "truth and the step's `Run:` line must repeat it "
                        "verbatim"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=verify_step.run_line or verify_step.line,
                    evidence=(
                        f"Check: {command}  |  Step {verify_step.number} "
                        f"Run: {verify_step.run_command}"
                    ),
                    severity=ERROR,
                )
            )

    return guard_no_input(
        "consistency", findings, len(doc.tasks), "task blocks", "consistency lint"
    )
