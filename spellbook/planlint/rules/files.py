"""`Files:` path existence — modify-path-missing, create-path-exists.

modify-path-missing: ERROR, all phases. A `Modify:` path (line range suffix
removed) that does not exist under repo_root.
create-path-exists: WARNING in AUTHORING, INFO in REVIEW, OFF in EXECUTION.
A `Create:` path that already exists — almost always a mislabeled Modify:
at authoring time.

`Delete:` and `Test:` paths are exempt from both. `Delete:` because a plan
may legitimately delete a path an earlier task already removed. `Test:`
because under TDD a test file that does not exist yet is the NORMAL case —
the task exists to create it — so checking it would make the rule fire on
every correct plan this repo's own writing-plans skill emits. Globs ('*' in
the path) are skipped, not resolved, per design §4.5's judgment call.

When repo_root is None, this rule returns ZERO findings with skipped_reason
set — never a clean report. decided_claims() (api.py, Task 12) reports a
skipped rule as UNDECIDED so the prose review still covers the claim.
"""

from spellbook.planlint.finding import ERROR, INFO, WARNING, Finding, LintResult

EMITS = frozenset({"modify-path-missing", "create-path-exists"})


def _create_severity(phase_value):
    if phase_value == "authoring":
        return WARNING
    if phase_value == "review":
        return INFO
    return None  # OFF in execution


def run(ctx):
    doc = ctx.doc
    findings = []
    examined = 0

    if ctx.repo_root is None:
        return LintResult(
            name="files",
            findings=[],
            examined=0,
            examined_label="Files: entries",
            skipped_reason="no repo_root supplied",
        )

    phase_value = getattr(ctx.phase, "value", ctx.phase)
    create_severity = _create_severity(phase_value)

    for task in doc.tasks:
        for entry in task.files_entries:
            if entry.verb in ("Delete", "Test"):
                continue
            if "*" in entry.path:
                continue
            examined += 1
            resolved = ctx.repo_root / entry.path

            if entry.verb == "Modify":
                if not resolved.exists():
                    findings.append(
                        Finding(
                            rule="modify-path-missing",
                            message=(
                                "a `Modify:` entry names a path that does not "
                                "exist in the repository, so the task is "
                                "planned against a tree that is not there"
                            ),
                            task=task.ident,
                            section=task.section,
                            line=entry.line,
                            evidence=f"- {entry.verb}: `{entry.raw}` (resolved: {resolved})",
                            severity=ERROR,
                        )
                    )
            elif (
                entry.verb == "Create"
                and create_severity is not None
                and resolved.exists()
            ):
                findings.append(
                    Finding(
                        rule="create-path-exists",
                        message=(
                            "a `Create:` path already exists; this is almost "
                            "always a mislabeled `Modify:`"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=entry.line,
                        evidence=f"- Create: `{entry.raw}` (resolved: {resolved})",
                        severity=create_severity,
                    )
                )

    return LintResult(
        name="files", findings=findings, examined=examined, examined_label="Files: entries"
    )
