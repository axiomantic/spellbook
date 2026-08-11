"""The dependency graph — parameterized edge parsing plus verbatim tarjan().

Section 4.2 of the design: the source project's IDENT_ONLY/IDENT_LEAD/
IDENT_ANY/RANGE/MARKERS vocabulary ([A-Z]{2,6}-\\d+ track prefixes, six-value
MARKERS tuple) is NOT ported. GraphSpec takes that vocabulary as data instead,
so this module carries none of it. `annotation_markers` is an EMPTY frozenset
for spellbook: spellbook plans define no such markers.
"""

import dataclasses
import re
from collections.abc import Callable

from spellbook.planlint import document
from spellbook.planlint.finding import ERROR, Finding


@dataclasses.dataclass(frozen=True)
class GraphSpec:
    field_label: str
    ident_only: re.Pattern[str]
    ident_any: re.Pattern[str]
    range_pattern: re.Pattern[str]
    ident_of_range: Callable[[int], str]
    none_words: frozenset[str]
    annotation_markers: frozenset[str]


DEPENDS = GraphSpec(
    field_label="Depends",
    ident_only=document.TASK_IDENT,
    ident_any=document.TASK_REF,
    range_pattern=document.TASK_RANGE,
    ident_of_range=lambda n: f"Task {n}",
    none_words=document.NONE_WORDS,
    annotation_markers=frozenset(),
)


def _sentences(text):
    parts = re.split(r"(?<=\.)\s+", text.strip())
    return [p for p in parts if p.strip()]


def parse_depends(text, spec):
    """Split a `Depends:`-shaped value into declared edges and prose findings.

    Returns `(edges, findings)`. The findings carry no task/line; the caller
    (`build_edges`) fills those in via `dataclasses.replace`.

    ONLY THE FIRST SENTENCE yields edges. This is intentional, not a
    truncation bug. A `Depends:` value is a comma-separated item list by
    contract (writing-plans emits exactly that shape); a second sentence is by
    definition prose the author appended, and prose on this line is the very
    thing `depends-prose` exists to report rather than silently read as an
    edge. Reading edges out of trailing prose would make the rule's own defect
    invisible. Every sentence after the first is therefore reported, not
    parsed — see the loop below.
    """
    plain = document.strip_markup(text)
    if not plain or plain.lower().rstrip(".") in spec.none_words:
        return [], []

    sentences = _sentences(plain)
    edges = []
    findings = []
    seen = set()

    def add(ident):
        if ident not in seen:
            seen.add(ident)
            edges.append(ident)

    for item in sentences[0].split(","):
        item = item.strip().rstrip(".").strip()
        if not item:
            continue
        if item.lower() in spec.none_words:
            continue
        match = spec.range_pattern.match(item) if spec.range_pattern else None
        if match:
            low, high = int(match.group("low")), int(match.group("high"))
            if low > high:
                findings.append(
                    Finding(
                        rule="depends-prose",
                        message=(
                            f"a range on the `{spec.field_label}:` line is reversed "
                            "(the low endpoint is greater than the high endpoint), "
                            "so it yields no edges; state the range low-to-high or "
                            "as separate items"
                        ),
                        evidence=item,
                        severity=ERROR,
                    )
                )
                continue
            for number in range(low, high + 1):
                add(spec.ident_of_range(number))
            continue
        if spec.ident_only.match(item):
            add(item)
            continue
        extras = spec.ident_any.findall(item)
        if extras:
            for extra in extras:
                findings.append(
                    Finding(
                        rule="depends-prose",
                        message=(
                            f"an identifier sits in prose on the `{spec.field_label}:` "
                            "line, so it is not read as an edge; state it as an item "
                            "or move the note off the line"
                        ),
                        evidence=f"{item} → Task {extra}",
                        severity=ERROR,
                    )
                )
        else:
            findings.append(
                Finding(
                    rule="depends-prose",
                    message=(
                        f"a prose item on the `{spec.field_label}:` line yields 0 "
                        "graph edges and matches no task identifier, range, or 'none'"
                    ),
                    evidence=item,
                    severity=ERROR,
                )
            )

    for trailing in sentences[1:]:
        findings.append(
            Finding(
                rule="depends-prose",
                message=(
                    f"the `{spec.field_label}:` line carries more than one "
                    "sentence; only the first is read as an item list, so nothing "
                    "in this one becomes an edge — state it as an item or move "
                    "the note off the line"
                ),
                evidence=trailing,
                severity=ERROR,
            )
        )

    return edges, findings


def build_edges(doc, spec):
    """`{ident: [dependency, ...]}` plus the findings the parse produced."""
    edges = {}
    findings = []
    for task in doc.tasks:
        declared, prose = parse_depends(task.depends_text, spec)
        edges[task.ident] = declared
        for f in prose:
            findings.append(
                dataclasses.replace(f, task=task.ident, section=task.section, line=task.depends_line or task.line)
            )
    return edges, findings


def tarjan(edges):
    """Every strongly connected component.

    Components are returned in the order each one finishes (reverse
    topological order of the condensation graph), not discovery order.

    Ported verbatim from nmg2-tools/planlint/graph.py:184-234. Pure graph
    code over a plain dict[str, Iterable[str]] edge map; iterative rather
    than recursive to avoid Python's recursion limit on a long dependency
    chain. Nothing here carries source-tool vocabulary, so nothing is
    parameterized.
    """
    index = {}
    low = {}
    stack = []
    on_stack = set()
    components = []
    counter = [0]

    def strong_connect(node):
        work = [(node, iter(edges.get(node, ())))]
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        while work:
            current, children = work[-1]
            advanced = False
            for child in children:
                if child not in edges:
                    continue
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(edges.get(child, ()))))
                    advanced = True
                    break
                if child in on_stack:
                    low[current] = min(low[current], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[current])
            if low[current] == index[current]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == current:
                        break
                components.append(sorted(component))

    for node in edges:
        if node not in index:
            strong_connect(node)
    return components
