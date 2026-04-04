"""Tests that subpackages are importable from spellbook.*."""

import importlib

import pytest

SUBPACKAGES = [
    "spellbook.security",
    "spellbook.forged",
    "spellbook.fractal",
    "spellbook.coordination",
    "spellbook.code_review",
    "spellbook.pr_distill",
    "spellbook.extractors",
]


@pytest.mark.parametrize("package", SUBPACKAGES)
def test_subpackage_importable(package: str) -> None:
    """Each subpackage should be importable from the new location."""
    mod = importlib.import_module(package)
    assert mod is not None


@pytest.mark.parametrize(
    "package,submodules",
    [
        ("spellbook.security", ["check", "rules", "scanner", "tools"]),
        (
            "spellbook.forged",
            [
                "artifacts",
                "context_filtering",
                "iteration_tools",
                "models",
                "project_graph",
                "project_tools",
                "roundtable",
                "schema",
                "skill_selection",
                "validators",
                "verdict_parsing",
            ],
        ),
        (
            "spellbook.fractal",
            ["graph_ops", "models", "node_ops", "query_ops", "schema"],
        ),
        (
            "spellbook.coordination",
            ["curator", "stint"],
        ),
        (
            "spellbook.code_review",
            ["arg_parser", "deduplication", "edge_cases", "models", "router"],
        ),
        (
            "spellbook.pr_distill",
            ["bless", "config", "errors", "fetch", "matcher", "parse", "patterns", "types"],
        ),
        (
            "spellbook.extractors",
            [
                "files",
                "message_utils",
                "persona",
                "position",
                "skill_phase",
                "skill",
                "todos",
                "types",
                "workflow",
            ],
        ),
    ],
)
def test_subpackage_submodules(package: str, submodules: list[str]) -> None:
    """Each subpackage's submodules should be importable."""
    for submodule in submodules:
        mod = importlib.import_module(f"{package}.{submodule}")
        assert mod is not None
