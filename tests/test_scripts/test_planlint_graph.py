"""Tests for spellbook.planlint.graph — tarjan(), GraphSpec, build_edges().

tarjan() is ported verbatim from nmg2-tools/planlint/graph.py:184-234 and is
pure graph code with no vocabulary; these tests exercise it directly on plain
dicts, matching the source project's own test shape.
"""

from spellbook.planlint import document
from spellbook.planlint.finding import ERROR, Finding
from spellbook.planlint.graph import DEPENDS, build_edges, parse_depends, tarjan


def test_tarjan_finds_no_components_in_an_acyclic_graph():
    edges = {"a": ["b"], "b": ["c"], "c": []}
    components = tarjan(edges)
    assert sorted(map(sorted, components)) == sorted(map(sorted, [["a"], ["b"], ["c"]]))


def test_tarjan_finds_a_three_node_cycle():
    edges = {"a": ["b"], "b": ["c"], "c": ["a"]}
    components = tarjan(edges)
    cyclic = [c for c in components if len(c) > 1]
    assert cyclic == [["a", "b", "c"]]


def test_tarjan_ignores_a_self_loop_as_a_size_one_component():
    edges = {"a": ["a"]}
    components = tarjan(edges)
    assert components == [["a"]]


def test_parse_depends_yields_edges_for_plain_idents():
    edges, findings = parse_depends("Task 1, Task 2", DEPENDS)
    assert edges == ["Task 1", "Task 2"]
    assert findings == []


def test_parse_depends_expands_a_range():
    edges, findings = parse_depends("Task 3 to Task 6", DEPENDS)
    assert edges == ["Task 3", "Task 4", "Task 5", "Task 6"]
    assert findings == []


def test_parse_depends_none_word_yields_no_edges_no_findings():
    edges, findings = parse_depends("none", DEPENDS)
    assert edges == []
    assert findings == []


def test_parse_depends_prose_yields_a_finding_and_no_phantom_edge():
    edges, findings = parse_depends(
        "Task 1, and Task 2 once the fixtures land.", DEPENDS
    )
    assert edges == ["Task 1"]
    assert findings == [
        Finding(
            rule="depends-prose",
            message=(
                "an identifier sits in prose on the `Depends:` line, so it is "
                "not read as an edge; state it as an item or move the note "
                "off the line"
            ),
            evidence="and Task 2 once the fixtures land → Task 2",
            severity=ERROR,
        )
    ]


def test_parse_depends_reports_a_second_sentence_instead_of_dropping_it():
    """Only the first sentence yields edges — by contract, not by accident.
    A second sentence must therefore be REPORTED, never silently ignored."""
    edges, findings = parse_depends("Task 1. Task 2 must land first.", DEPENDS)
    assert edges == ["Task 1"]
    assert findings == [
        Finding(
            rule="depends-prose",
            message=(
                "the `Depends:` line carries more than one sentence; only the "
                "first is read as an item list, so nothing in this one becomes "
                "an edge — state it as an item or move the note off the line"
            ),
            evidence="Task 2 must land first.",
            severity=ERROR,
        )
    ]


def test_parse_depends_reversed_range_yields_a_finding_and_no_edges():
    """Task 6 to Task 3: low > high must not silently vanish. Every other
    malformed `Depends:` shape in parse_depends emits a depends-prose
    finding; a reversed range is the sole path that used to produce zero
    edges AND zero findings (range(6, 4) is empty, so nothing was added
    and nothing was reported)."""
    edges, findings = parse_depends("Task 6 to Task 3", DEPENDS)
    assert edges == []
    assert findings == [
        Finding(
            rule="depends-prose",
            message=(
                "a range on the `Depends:` line is reversed (the low endpoint "
                "is greater than the high endpoint), so it yields no edges; "
                "state the range low-to-high or as separate items"
            ),
            evidence="Task 6 to Task 3",
            severity=ERROR,
        )
    ]


def test_build_edges_reads_every_task_depends_field():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: A\n\n**Files:**\n- Create: `a.py`\n\n**Depends:** none\n\n"
        "**Check:** `pytest a`\n\n"
        "### Task 2: B\n\n**Files:**\n- Create: `b.py`\n\n**Depends:** Task 1\n\n"
        "**Check:** `pytest b`\n"
    )
    doc = document.PlanDocument.from_text(text)
    edges, findings = build_edges(doc, DEPENDS)
    assert edges == {"Task 1": [], "Task 2": ["Task 1"]}
    assert findings == []


def test_document_declared_dependencies_uses_graph_parse_depends():
    text = (
        "**Schema:** planlint-v1\n\n"
        "### Task 1: A\n\n**Files:**\n- Create: `a.py`\n\n"
        "**Depends:** Task 2, and Task 3 once ready.\n\n**Check:** `pytest a`\n\n"
        "### Task 2: B\n\n**Files:**\n- Create: `b.py`\n\n**Depends:** none\n\n"
        "**Check:** `pytest b`\n"
    )
    doc = document.PlanDocument.from_text(text)
    assert doc.task("Task 1").declared_dependencies == ("Task 2",)
