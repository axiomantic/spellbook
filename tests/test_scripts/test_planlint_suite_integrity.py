"""Suite-hygiene tests, adapted from
nmg2-tools/tests/planlint/test_suite_integrity.py per design §7.3's
disposition table:

  * row 1 (main-guard) — DROPPED, REPLACED by row 6 (collection parity;
    spellbook runs pytest only, no unittest.main() guard is meaningful here).
  * row 2 (README/fixture table sync) — CARRIED OVER.
  * row 3 (discovery is self-verifying) — CARRIED OVER.
  * row 4 (no collected test returns a value) — CARRIED OVER.
  * row 5 (dual pytest+unittest runner parity) — DROPPED. Spellbook has no
    unittest discovery path anywhere in the repo; asserting parity with a
    runner nobody runs is a check that cannot go red for a real reason.
  * row 6 (collection parity WITH THE RUNNER SPELLBOOK USES) — NEW. Runs
    pytest --collect-only as a real subprocess against the runner spellbook
    actually has. Marked slow: it spawns a collector subprocess.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures" / "planlint"
REPO_ROOT = TESTS.parents[1]
README = REPO_ROOT / "spellbook" / "planlint" / "README.md"

# The planlint test modules that EXIST when this file is written (Task 15, after
# Tasks 1-14). `test_planlint_vocabulary.py` was deliberately absent until Task
# 17 created it in the same commit that adds this entry — the promised follow-up
# noted in Task 15's Step 3. The tuple is therefore correct at every point in
# build order — it is never a true list with an entry deleted to buy a green run.
PLANLINT_TEST_MODULES = (
    "test_planlint_finding.py",
    "test_planlint_document.py",
    "test_planlint_graph.py",
    "test_planlint_registry.py",
    "test_planlint_rules.py",
    "test_planlint_api.py",
    "test_planlint_cli.py",
    "test_planlint_schema_census.py",
    "test_planlint_suite_integrity.py",
    "test_planlint_vocabulary.py",
    # Task 19's skill-integration test. `discover_planlint_test_modules` matches
    # on the substring "planlint" anywhere in the name, not on a
    # `test_planlint_` prefix, so a per-skill file named
    # `test_<skill>_planlint.py` is discovered and MUST be registered here in
    # the same commit that creates it. Tasks 20 and 21 add
    # `test_reviewing_impl_plans_skill_planlint.py` and
    # `test_executing_plans_skill_planlint.py` and owe this tuple the same
    # one-line addition.
    "test_writing_plans_skill_planlint.py",
)


def discover_planlint_test_modules():
    """Every planlint test module in this directory, independently scanned
    with os.listdir (not glob), sorted."""
    return sorted(
        TESTS / name
        for name in os.listdir(TESTS)
        if "planlint" in name and name.endswith(".py")
    )


def collected_tests(tree):
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                found.append((None, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            if any(
                isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name == "__init__"
                for member in node.body
            ):
                # pytest refuses to collect a class defining __init__.
                continue
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name.startswith("test"):
                    found.append((node.name, member))
    return found


def qualified_names(path):
    """The `file::function` collection identities in `path`, one per test
    function regardless of parametrize expansion — set membership here is
    about WHICH functions exist, not how many cases each expands to."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for owner, function in collected_tests(tree):
        identity = f"{path.name}::{owner}::{function.name}" if owner else f"{path.name}::{function.name}"
        names.append(identity)
    return names


def returned_values(function):
    found = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            found.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return found


# ------------------------------------------------------------- row 2: README

def _documented_fixtures():
    text = README.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## Fixtures"))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    found = set()
    for line in lines[start:end]:
        if not line.startswith("|"):
            continue
        for cell in line.split("|"):
            for token in cell.replace("`", " ").split():
                if token.endswith(".md"):
                    found.add(token)
    return found


def _committed_fixtures():
    return {p.name for p in FIXTURES.glob("*.md")}


def test_every_fixture_has_a_row_in_the_readme_table():
    committed = _committed_fixtures()
    assert "clean_plan.md" in committed
    assert sorted(committed - _documented_fixtures()) == []


def test_every_readme_row_names_a_fixture_that_exists():
    rows = _documented_fixtures()
    assert "clean_plan.md" in rows
    assert sorted(rows - _committed_fixtures()) == []


# --------------------------------------------------------- row 3: discovery

def test_discovery_finds_every_committed_planlint_test_module():
    found = {p.name for p in discover_planlint_test_modules()}
    assert found == set(PLANLINT_TEST_MODULES)


def test_discovery_is_not_empty():
    assert discover_planlint_test_modules() != []


def test_every_discovered_module_holds_at_least_one_test():
    empty = [p.name for p in discover_planlint_test_modules() if not qualified_names(p)]
    assert empty == []


# ------------------------------------------------------ row 4: return values

def test_no_collected_planlint_test_returns_a_value():
    offenders = []
    for path in discover_planlint_test_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for _, function in collected_tests(tree):
            for node in returned_values(function):
                offenders.append(f"{path.name}::{function.name}:{node.lineno}")
    assert offenders == []


# --------------------------------------------- row 6: pytest collection parity

@pytest.mark.slow
@pytest.mark.timeout(180)
def test_pytest_collection_matches_the_ast_scan():
    """Spawns a full pytest collector as a subprocess, so it needs a budget far
    above pyproject.toml's global `timeout = 30`. The outer mark must exceed the
    inner `timeout=` below, or a slow collection is killed by pytest-timeout and
    reports as an opaque hang instead of a named `subprocess.TimeoutExpired`."""
    scanned = {
        name
        for path in discover_planlint_test_modules()
        for name in qualified_names(path)
    }
    module_paths = [str(p.relative_to(REPO_ROOT)) for p in discover_planlint_test_modules()]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--override-ini=addopts=",
            *module_paths,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    # Only 0 (tests collected) and 5 (no tests collected) are accepted: 5 is a
    # real failure worth asserting on below via an empty `collected` set, not
    # a silent pass, so it is let through here rather than rejected outright.
    assert result.returncode in (0, 5), result.stdout + result.stderr
    collected = set()
    for line in result.stdout.splitlines():
        if "::" not in line:
            continue
        node_id = line.split(" ")[0].split("[", 1)[0]
        file_part, _, rest = node_id.partition("::")
        collected.add(f"{os.path.basename(file_part)}::{rest}")
    assert collected == scanned, (
        f"AST scan and pytest --collect-only disagree on which tests exist.\n"
        f"Only in AST scan (missing from pytest collection): {sorted(scanned - collected)}\n"
        f"Only in pytest collection (missing from AST scan): {sorted(collected - scanned)}\n"
        f"{result.stdout}"
    )
