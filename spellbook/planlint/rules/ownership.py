"""shared-path-without-owner — WARNING.

Two or more tasks name the SAME path with a writing verb (Create, Modify,
Delete; Test does not count as a write) and neither an `(owner: Task N)`
annotation nor a `Depends:` reachability path (either direction) orders
them. This rule CONSULTS the dependency graph read-only; it never
contributes an edge to it — a `Files:` overlap carries no ordering meaning.
"""

from spellbook.planlint.finding import WARNING, Finding, guard_no_input
from spellbook.planlint.graph import DEPENDS, build_edges

EMITS = frozenset({"shared-path-without-owner"})

WRITE_VERBS = frozenset({"Create", "Modify", "Delete"})


def _reachable(start, edges):
    seen = set()
    stack = [start]
    while stack:
        node = stack.pop()
        for neighbor in edges.get(node, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen


def _ordered(a, b, edges):
    """True if a Depends: path connects a and b in EITHER direction."""
    return b in _reachable(a, edges) or a in _reachable(b, edges)


def _ownership_is_declared(claims, idents):
    """True when EVERY claimant of a path agrees on ONE owner that is itself a
    claimant.

    Every claimant, not any claimant. A single `(owner: Task 4)` annotation on
    one of five bullets does not make the other four coordinated — it makes
    ONE of them coordinated and leaves four writers racing, which is the exact
    situation this rule exists to report. Suppressing on `any` would let a
    plan silence the whole finding by annotating one bullet, and the more
    claimants a path collects the more valuable the finding is and the cheaper
    it would be to suppress.

    The owner's OWN bullet needs no annotation: a task naming itself as owner
    of a path it writes is redundant, and requiring it would make the common
    correct shape (owner writes plainly, every later modifier annotates) fire.
    """
    owners = {owner for _, owner, _ in claims if owner}
    if len(owners) != 1:
        return False              # zero owners, or two tasks claiming ownership
    owner = next(iter(owners))
    if owner not in idents:
        return False              # names a task that does not write this path
    return all(
        annotation == owner or task.ident == owner
        for task, annotation, _ in claims
    )


def run(ctx):
    doc = ctx.doc
    edges, _ = build_edges(doc, DEPENDS)

    claimants = {}  # path -> list[(task, owner_annotation)]
    for task in doc.tasks:
        for entry in task.files_entries:
            if entry.verb not in WRITE_VERBS:
                continue
            claimants.setdefault(entry.path, []).append((task, entry.owner, entry.line))

    findings = []
    for path, claims in claimants.items():
        if len(claims) < 2:
            continue
        idents = [task.ident for task, _, _ in claims]
        if _ownership_is_declared(claims, idents):
            continue

        unordered_pairs = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                task_a = claims[i][0].ident
                task_b = claims[j][0].ident
                if not _ordered(task_a, task_b, edges):
                    unordered_pairs.append((task_a, task_b))

        if not unordered_pairs:
            continue

        first_task, _, first_line = claims[0]
        findings.append(
            Finding(
                rule="shared-path-without-owner",
                message=(
                    "two or more tasks write this path, they do not all name the "
                    "same `(owner: Task N)`, and no `Depends:` edge orders them; "
                    "the writes may race"
                ),
                task=first_task.ident,
                section=first_task.section,
                line=first_line,
                evidence=(
                    f"{path} claimed by " + ", ".join(idents) +
                    " (annotations: " +
                    ", ".join(
                        f"{task.ident}={annotation or '-'}"
                        for task, annotation, _ in claims
                    ) +
                    "; no dependency path between " +
                    ", or ".join(
                        f"{task_a} and {task_b}" for task_a, task_b in unordered_pairs
                    ) +
                    ")"
                ),
                severity=WARNING,
            )
        )

    return guard_no_input(
        "ownership", findings, len(doc.tasks), "task blocks", "ownership lint"
    )
