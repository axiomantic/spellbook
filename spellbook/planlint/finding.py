"""Findings and lint results.

Exit codes are stated once, here, because the source project measured what a
silent zero costs. That project's test runner exited 0 when its filter
pattern matched no test, and about a hundred checks reported PASS against no
code. Not every runner behaves that way — pytest exits 5 on an empty
collection — which is the point: a lint cannot inherit the guarantee from its
runner. So this one reports a hard error when it finds no input to examine.
Nothing to check is never a pass.
"""

import dataclasses

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"

SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    message: str
    task: str = ""
    section: str = ""
    line: int = 0
    evidence: str = ""
    severity: str = ERROR


@dataclasses.dataclass
class LintResult:
    name: str
    findings: list
    examined: int
    examined_label: str = "inputs"
    skipped_reason: str = ""

    @property
    def failed(self):
        """Any finding fails the run. Severity orders the report; it never
        excuses a finding from the exit code."""
        return bool(self.findings)

    def report(self):
        """A human-readable report: task, section, evidence, and the rule.

        `skipped_reason` and `findings` are not mutually exclusive in the
        dataclass's shape, even though no current call path constructs both
        at once (`guard_no_input`/`files.py`'s skip path always sets one or
        the other, never both). If both are ever present, the skip reason is
        reported first, then the findings — never dropping either.
        """
        if self.skipped_reason and not self.findings:
            return f"{self.name}: skipped ({self.skipped_reason})\n"
        if not self.findings:
            return f"{self.name}: clean ({self.examined} {self.examined_label} examined)\n"
        head = (
            f"{self.name}: {len(self.findings)} finding(s) "
            f"({self.examined} {self.examined_label} examined)\n"
        )
        if self.skipped_reason:
            head = f"{self.name}: skipped ({self.skipped_reason})\n" + head
        body = []
        for f in sorted(
            self.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule, f.task, f.line)
        ):
            head_parts = [f"  [{f.severity}] {f.rule}"]
            if f.task:
                head_parts.append(f.task)
            if f.line:
                head_parts.append(f"line {f.line}")
            body.append("  ".join(head_parts))
            if f.section:
                body.append(f"      section: {f.section}")
            body.append(f"      {f.message}")
            if f.evidence:
                body.append(f"      evidence: {f.evidence}")
        return head + "\n".join(body) + "\n"


def guard_no_input(name, findings, examined, label, noun):
    """Turn 'nothing to check' into a hard error, never a pass."""
    if examined == 0:
        findings = list(findings) + [
            Finding(
                rule="no-input",
                message=f"the {noun} examined 0 {label}",
                severity=ERROR,
            )
        ]
    return LintResult(name=name, findings=findings, examined=examined, examined_label=label)


NO_RULES_RAN = Finding(
    rule="no-rules-ran",
    message="phase matched zero registered rules; nothing was checked",
    severity=ERROR,
)
