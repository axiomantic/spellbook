"""Three call-site entry points: lint_for_authoring, lint_for_review,
lint_on_write. Plus the two lower-level functions they wrap (lint_text,
lint_path) and the schema gate (declares_schema) they all share.

Every function here returns; none raises for an ordinary lint outcome
(missing file, legacy plan, ERROR findings). A rule CRASH is caught by
registry.run_rules()'s barrier and surfaced in PlanLintReport.internal_errors
— not raised either, except for BaseException subclasses, which propagate
through every layer by design (design §5.2, tested by
test_barrier_propagates_keyboardinterrupt in Task 4 and here).
"""

import dataclasses
import re
from pathlib import Path

from spellbook.planlint import registry
from spellbook.planlint.document import (
    SCHEMA_FAMILY,
    SCHEMA_LEGACY,
    PlanDocument,
    fenced_line_indexes,
)
from spellbook.planlint.finding import ERROR, NO_RULES_RAN, LintResult
from spellbook.planlint.registry import Phase  # re-exported for callers

_SCHEMA_LINE = re.compile(r"^\s*(?:\*\*)?Schema\s*:(?:\*\*)?\s?(?P<value>.*)$")


@dataclasses.dataclass(frozen=True)
class DecidedClaim:
    """One rule's verdict for reviewing-impl-plans's Phase 0 pre-pass."""

    rule: str
    decided: bool
    finding_count: int
    reason: str = ""  # populated when decided is False


# `skip_kind` — a structured reason code for why `linted` is False, set ONLY
# at the actual except-handlers / gate branches that decide it, never derived
# from `skip_reason`'s prose. `skip_reason` interpolates caller-controlled
# text (a plan's own `Schema:` field value), so substring-sniffing it for
# exit-code decisions is fooled by a plan whose `Schema:` field happens to
# contain the words "unreadable" or "not UTF-8". `skip_kind` is the
# structural fact a caller (cli.py) can safely branch on.
SKIP_UNREADABLE = "unreadable"
SKIP_NOT_UTF8 = "not_utf8"
SKIP_NO_SCHEMA = "no_schema"


@dataclasses.dataclass(frozen=True)
class PlanLintReport:
    """The whole answer. Never raised through; always returned."""

    plan: str
    linted: bool
    skip_reason: str
    results: "tuple[LintResult, ...]"
    internal_errors: "tuple[registry.RuleCrash, ...]"
    skip_kind: str = ""  # one of the SKIP_* constants above; "" when linted

    @property
    def findings(self):
        out = []
        for result in self.results:
            out.extend(result.findings)
        return tuple(out)

    @property
    def errors(self):
        return tuple(f for f in self.findings if f.severity == ERROR)

    @property
    def failed(self):
        """True when any finding exists OR any rule crashed. A crash counts."""
        return bool(self.findings) or bool(self.internal_errors)

    def report(self):
        if not self.linted:
            return f"{self.plan}: not linted ({self.skip_reason})\n"
        parts = [r.report() for r in self.results]
        for crash in self.internal_errors:
            parts.append(
                f"{crash.rule}: CRASHED ({crash.exc_type}: {crash.message})\n{crash.traceback_text}"
            )
        return "".join(parts)

    def summary_line(self):
        if not self.linted:
            return f"{self.plan}: not linted ({self.skip_reason})"
        error_count = len(self.errors)
        crash_count = len(self.internal_errors)
        if not self.failed:
            # len(self.results), never a literal 7. The rule set is not a
            # constant: a phase filter can drop rows, and a test that
            # monkeypatches registry.RULES can replace them entirely. A
            # hardcoded count would state a wrong fact about the run that
            # produced it — the exact class of defect this linter exists to
            # catch, in the linter's own summary line.
            claims = decided_claims(self)
            skipped = [c for c in claims if not c.decided]
            if skipped:
                decided_count = len(claims) - len(skipped)
                return (
                    f"{self.plan}: clean ({decided_count} of {len(claims)} rule(s) "
                    f"decided, {len(skipped)} skipped, 0 findings)"
                )
            return f"{self.plan}: clean ({len(self.results)} rule(s), 0 findings)"
        return (
            f"{self.plan}: {len(self.findings)} finding(s), "
            f"{error_count} error(s), {crash_count} crash(es)"
        )


def _first_schema_value(text):
    """The value of the FIRST `Schema:` line in the raw text, or None.

    FENCE-AWARE, and that is not optional. `PlanDocument._resolve_plan_schema`
    skips lines inside a closed fenced block, so a fence-BLIND gate and a
    fence-AWARE parser would disagree about the same document: a plan whose
    only `Schema:` mention sits inside a fenced example block (a plan ABOUT
    plans — this port's own plan is one) would be gated IN by the scan and
    then parsed as carrying no schema at all. The gate and the parser must
    read the same document, so both skip fenced lines, using the same
    `fenced_line_indexes` the parser's `_scan_fences` mirrors.

    Taking the FIRST such line matches the parser's "plan header first, else
    the first task's own value" reading, because a header line necessarily
    precedes any task's own `Schema:` line in the text.

    Cost: two linear passes over the split lines. No PlanDocument is built, no
    task block is parsed, no rule is imported.
    """
    lines = text.splitlines()
    fenced = fenced_line_indexes(lines)
    for index, line in enumerate(lines):
        if index in fenced:
            continue
        match = _SCHEMA_LINE.match(line)
        if match:
            return match.group("value").strip()
    return None


def _opts_in(value):
    """True when a RAW gate value opts this plan into the linter.

    The test is FAMILY membership (`planlint-<something>`), not equality with
    `SCHEMA_MARKER`. That widening is what makes `schema-unknown-version`
    reachable: an exact-marker gate routes `planlint-v2` down the same skip path
    as a plan with no field at all, so the rule that exists to raise the alarm
    never runs and the alarm is dead code. The gate answers only "is this a
    planlint plan?"; WHICH planlint version, and whether this build knows it, is
    `rules/schema.py`'s judgment to make — with a real ERROR finding, in a real
    report, on a plan that was really linted.

    `legacy` and every non-`planlint-` value stay out, so the legacy fleet's
    zero-invocation guarantee is untouched.
    """
    return value is not None and SCHEMA_FAMILY.match(value) is not None


def declares_schema(text):
    """The GATE. True when this plan text opts into the linter."""
    return _opts_in(_first_schema_value(text))


def _skip_reason_for(value):
    """Why a plan was not linted, from the RAW gate value — never from a
    document. Building a PlanDocument here just to phrase a skip reason would
    contradict design §6.1's "declares_schema False → ZERO further work" and
    §8.1's cost claim for the legacy fleet, which is the whole reason the gate
    is a text scan rather than a parse."""
    if value is None or value == "":
        return "no Schema: field (legacy plan)"
    if value == SCHEMA_LEGACY:
        return "Schema: legacy (explicit opt-out)"
    displayed = value if len(value) <= 50 else f"{value[:50]}..."
    return f"Schema: {displayed} (not a planlint schema)"


def lint_text(text, *, name="<text>", phase=Phase.REVIEW, repo_root=None):
    """Lint plan TEXT. Returns a report; never raises (except BaseException
    subclasses propagating through registry.run_rules()'s barrier)."""
    value = _first_schema_value(text)
    if not _opts_in(value):
        return PlanLintReport(
            plan=name,
            linted=False,
            skip_reason=_skip_reason_for(value),
            results=(),
            internal_errors=(),
            skip_kind=SKIP_NO_SCHEMA,
        )

    doc = PlanDocument.from_text(text, name=name)
    ctx = registry.RuleContext(doc=doc, phase=phase, repo_root=repo_root)
    results, crashes = registry.run_rules(ctx)
    if not results and not crashes:
        # Every rule was dispatch-filtered out (an unrecognized phase, or
        # `phase=None`, matches no rule's `frozenset(Phase)`). Nothing ran,
        # so a clean report here would be a silent PASS on zero evidence —
        # the exact failure mode `guard_no_input` exists to prevent for a
        # single rule's own input, applied at the whole-run level.
        results = (
            LintResult(
                name="no-rules-ran",
                findings=[NO_RULES_RAN],
                examined=0,
                examined_label="rules",
            ),
        )
    return PlanLintReport(
        plan=name, linted=True, skip_reason="", results=results, internal_errors=crashes
    )


def lint_path(path, *, phase=Phase.REVIEW, repo_root=None):
    """Lint a plan FILE. Returns a report; never raises.

    An unreadable path is a report with linted=False and a skip_reason, not
    an exception.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return PlanLintReport(
            plan=str(path),
            linted=False,
            skip_reason=f"unreadable: {exc}",
            results=(),
            internal_errors=(),
            skip_kind=SKIP_UNREADABLE,
        )
    except UnicodeDecodeError:
        return PlanLintReport(
            plan=str(path),
            linted=False,
            skip_reason="not UTF-8",
            results=(),
            internal_errors=(),
            skip_kind=SKIP_NOT_UTF8,
        )
    return lint_text(text, name=str(path), phase=phase, repo_root=repo_root)


def lint_for_authoring(path, *, repo_root=None):
    """Lint a plan the author has just written. Phase.AUTHORING turns ON
    create-path-exists (WARNING) and leaves modify-path-missing on."""
    return lint_path(path, phase=Phase.AUTHORING, repo_root=repo_root)


def lint_for_review(path, *, repo_root=None):
    """Lint a plan before a human-judgment review reads it. Phase.REVIEW
    behaves as AUTHORING except create-path-exists drops to INFO."""
    return lint_path(path, phase=Phase.REVIEW, repo_root=repo_root)


def lint_on_write(path, text, *, repo_root=None):
    """Lint an amended plan that was JUST written to disk. `text` is passed
    in rather than re-read, so the report describes the bytes the caller
    produced. Returns None — and does nothing else — when the plan declares
    no schema. Phase.EXECUTION turns OFF create-path-exists entirely.
    FAIL-OPEN: the caller must never revert the write on a crash (design
    §5.3) — that policy lives in the CALLER (executing-plans's SKILL.md,
    Task 21), not here; this function's contract is simply "return a
    report, or None, and never raise for an ordinary crash".
    """
    if not declares_schema(text):
        return None
    return lint_text(text, name=str(path), phase=Phase.EXECUTION, repo_root=repo_root)


def decided_claims(report):
    """The claims this run already DECIDED, as tuple[DecidedClaim, ...].

    One entry per rule that RAN. A rule that ran and found nothing has
    decided its claim. A rule that was SKIPPED (LintResult.skipped_reason
    set) is reported as UNDECIDED, never as clean. A rule that CRASHED
    (present in `report.internal_errors`) is also reported as UNDECIDED,
    with `reason` set to `"crashed: <type>: <message>"`.
    """
    claims = []
    for result in report.results:
        if result.skipped_reason:
            claims.append(
                DecidedClaim(
                    rule=result.name,
                    decided=False,
                    finding_count=0,
                    reason=result.skipped_reason,
                )
            )
        else:
            claims.append(
                DecidedClaim(
                    rule=result.name,
                    decided=True,
                    finding_count=len(result.findings),
                )
            )
    for crash in report.internal_errors:
        claims.append(
            DecidedClaim(
                rule=crash.rule,
                decided=False,
                finding_count=0,
                reason=f"crashed: {crash.exc_type}: {crash.message}",
            )
        )
    return tuple(claims)
