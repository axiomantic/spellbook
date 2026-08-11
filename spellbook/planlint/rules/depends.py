"""Dependency-graph acyclicity — depends-prose, self-dependency,
unknown-dependency, dependency-cycle. All four ERROR.

`Depends:` edges ONLY. A `Files:` overlap never becomes an edge here — that
is rules/ownership.py's business and it carries no ordering meaning.

`depends-prose` is declared in `EMITS` but never constructed by `run()`
below. `graph.build_edges` (Task 3) constructs that Finding while parsing
each task's `Depends:` text and `run()` merely forwards what `build_edges`
returns. This is a deliberate, documented cross-module split, not an
oversight — see the design section for this rule.
"""

from spellbook.planlint.document import strip_markup
from spellbook.planlint.finding import ERROR, Finding, guard_no_input
from spellbook.planlint.graph import DEPENDS, build_edges, tarjan

EMITS = frozenset(
    {"depends-prose", "self-dependency", "unknown-dependency", "dependency-cycle"}
)


def run(ctx):
    doc = ctx.doc
    edges, findings = build_edges(doc, DEPENDS)

    for task in doc.tasks:
        for dependency in edges[task.ident]:
            if dependency == task.ident:
                findings.append(
                    Finding(
                        rule="self-dependency",
                        message="a task names itself on its `Depends:` line",
                        task=task.ident,
                        section=task.section,
                        line=task.depends_line or task.line,
                        evidence=f"Depends: {strip_markup(task.depends_text)}",
                        severity=ERROR,
                    )
                )
            elif not doc.has_task(dependency):
                findings.append(
                    Finding(
                        rule="unknown-dependency",
                        message=(
                            "a `Depends:` line names an identifier this plan defines "
                            "in no task block"
                        ),
                        task=task.ident,
                        section=task.section,
                        line=task.depends_line or task.line,
                        evidence=(
                            f"Depends: {strip_markup(task.depends_text)} → {dependency}"
                        ),
                        severity=ERROR,
                    )
                )

    for component in tarjan(edges):
        if len(component) < 2:
            continue
        head = doc.task(component[0])
        findings.append(
            Finding(
                rule="dependency-cycle",
                message=(
                    "these tasks wait on each other and none of them can start"
                ),
                task=component[0],
                section=head.section if head else "",
                line=head.line if head else 0,
                evidence="strongly connected component: " + ", ".join(component),
                severity=ERROR,
            )
        )

    return guard_no_input(
        "depends", findings, len(doc.tasks), "task blocks", "depends lint"
    )
