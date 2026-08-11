"""Tests for spellbook.planlint.graph — tarjan(), GraphSpec, build_edges().

tarjan() is ported verbatim from nmg2-tools/planlint/graph.py:184-234 and is
pure graph code with no vocabulary; these tests exercise it directly on plain
dicts, matching the source project's own test shape.
"""

from spellbook.planlint import document
from spellbook.planlint.graph import DEPENDS, build_edges, parse_depends, tarjan


def test_tarjan_finds_no_components_in_an_acyclic_graph():
    edges = {"a": ["b"], "b": ["c"], "c": []}
    components = tarjan(edges)
    assert all(len(c) < 2 for c in components)


def test_tarjan_finds_a_three_node_cycle():
    edges = {"a": ["b"], "b": ["c"], "c": ["a"]}
    components = tarjan(edges)
    cyclic = [c for c in components if len(c) > 1]
    assert cyclic == [["a", "b", "c"]]


def test_tarjan_ignores_a_self_loop_as_a_size_one_component():
    edges = {"a": ["a"]}
    components = tarjan(edges)
    assert all(len(c) < 2 for c in components)


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
    assert len(findings) == 1
    assert findings[0].rule == "depends-prose"
    assert "Task 2" in findings[0].evidence


def test_parse_depends_reports_a_second_sentence_instead_of_dropping_it():
    """Only the first sentence yields edges — by contract, not by accident.
    A second sentence must therefore be REPORTED, never silently ignored."""
    edges, findings = parse_depends("Task 1. Task 2 must land first.", DEPENDS)
    assert edges == ["Task 1"]
    assert [f.rule for f in findings] == ["depends-prose"]
    assert "Task 2 must land first." in findings[0].evidence


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
