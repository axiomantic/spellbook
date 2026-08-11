"""schema-conflict, schema-unknown-version — both ERROR.

A `Schema:` value can appear at the plan level and/or per-task (design
§3.1.2). This rule reads the RAW values directly (not the gated
`declares_planlint_schema`) because it must see the disagreement to report
it — gating it would make it unable to report a conflict.
"""

from spellbook.planlint.document import SCHEMA_LEGACY, SCHEMA_MARKER
from spellbook.planlint.finding import ERROR, Finding, guard_no_input

EMITS = frozenset({"schema-conflict", "schema-unknown-version"})

KNOWN_VALUES = frozenset({SCHEMA_MARKER, SCHEMA_LEGACY})


def run(ctx):
    doc = ctx.doc
    findings = []

    values = []
    if doc.schema_text:
        values.append(("<plan header>", doc.schema_text, doc.schema_line))
    for task in doc.tasks:
        if task.schema_text:
            values.append((task.ident, task.schema_text, task.schema_line))

    distinct = {v for _, v, _ in values}
    if len(distinct) > 1:
        owner, value, line = values[0]
        findings.append(
            Finding(
                rule="schema-conflict",
                message=(
                    "the plan-level `Schema:` and a task-level `Schema:` "
                    "disagree, or two tasks disagree"
                ),
                task=owner if owner != "<plan header>" else "",
                section=doc.tasks[0].section if doc.tasks else "",
                line=line,
                evidence=", ".join(f"{o}: {v}" for o, v, _ in values),
                severity=ERROR,
            )
        )

    for owner, value, line in values:
        if value not in KNOWN_VALUES:
            findings.append(
                Finding(
                    rule="schema-unknown-version",
                    message=(
                        "a `Schema:` value is neither `planlint-v1` nor `legacy`; "
                        "a plan declaring an unrecognized schema must say so "
                        "rather than be linted under the wrong rules"
                    ),
                    task=owner if owner != "<plan header>" else "",
                    section=doc.tasks[0].section if doc.tasks else "",
                    line=line,
                    evidence=f"Schema: {value}",
                    severity=ERROR,
                )
            )

    return guard_no_input(
        "schema", findings, len(doc.tasks), "task blocks", "schema lint"
    )
