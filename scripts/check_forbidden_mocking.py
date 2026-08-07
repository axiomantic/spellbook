#!/usr/bin/env python3
"""Ratchet gate: forbid NEW non-tripwire mocking under ``tests/``.

AGENTS.md ("Testing with Tripwire") makes tripwire the only permitted mocking
framework. Forbidden here:

* ``unittest.mock`` / ``mock`` imports in any form
* the ``mocker`` fixture (pytest-mock)
* ``monkeypatch.setattr`` / ``setitem`` / ``delattr`` / ``delitem``

``monkeypatch.setenv`` / ``delenv`` / ``chdir`` / ``syspath_prepend`` remain
allowed -- those are pytest built-ins for environment, cwd, and sys.path, not
mocking.

The repository still carries a large legacy population of forbidden calls, so
this gate is a RATCHET rather than a clean-tree assertion: ``ALLOWLIST`` records
a per-file budget of known-legacy occurrences. A file may contain FEWER than its
budget (converting tests to tripwire is always allowed, and tightening the
budget afterwards is encouraged), but never more, and a file absent from the
allowlist has a budget of zero. The count can therefore only go down.

Detection is AST-based, so prose in docstrings and comments that merely
*mentions* ``unittest.mock`` does not trip the gate.

Usage:
    python scripts/check_forbidden_mocking.py [repo_root]
Exits non-zero and prints ``path:line: message`` for each violation.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

MOCK_METHODS = frozenset({"setattr", "setitem", "delattr", "delitem"})
ALLOWED_METHODS = frozenset({"setenv", "delenv", "chdir", "syspath_prepend"})
MOCK_MODULES = frozenset({"unittest.mock", "mock"})

# --- Wildcard matchers -------------------------------------------------------
# THE LIST BELOW IS NOT THE DEFINITION. The property is: "a matcher that compares
# equal to every value, and therefore cannot make an assertion fail."
#
# This gate exists because the previous rule named a LIBRARY (`mock.ANY`) instead
# of that property. The repo migrated off ``unittest.mock`` onto tripwire, the
# rule was satisfied by construction, and ``dirty_equals.AnyThing`` walked in
# through the gap and accumulated silently. Every new mocking/matching framework
# introduces its own spelling of the same idea. When one arrives, add it here --
# that is a one-line change -- and do not mistake the list for the rule.
WILDCARD_NAMES = frozenset({"ANY", "AnyThing"})
WILDCARD_DOTTED = frozenset({"mock.ANY", "unittest.mock.ANY"})

# Wildcards that are CLASSES, so a bare reference is a live trap rather than a
# merely-weak assertion. See _bare_class_wildcards() for why.
WILDCARD_CLASSES = frozenset({"AnyThing"})


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    lineno: int
    kind: str
    detail: str


def _iter_test_files(root: Path):
    tests = root / "tests"
    if not tests.is_dir():
        return
    for p in sorted(tests.rglob("*.py")):
        if "__pycache__" not in p.parts:
            yield p


def _dotted(node: ast.AST) -> str | None:
    """Render a Name/Attribute chain as a dotted string, else None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _is_wildcard(node: ast.AST) -> bool:
    """True if this expression is an always-equal matcher.

    Covers both the instance form (``AnyThing()``) and every bare form
    (``ANY``, ``mock.ANY``, ``AnyThing``). The bare CLASS is included on
    purpose: it compares equal to everything just like the instance does.
    """
    if isinstance(node, ast.Call):
        return _is_wildcard(node.func)
    dotted = _dotted(node)
    if dotted is None:
        return False
    return dotted in WILDCARD_DOTTED or dotted.split(".")[-1] in WILDCARD_NAMES


def _bare_class_wildcards(tree: ast.AST, rel: str) -> list[Violation]:
    """Flag a wildcard CLASS referenced as a value instead of instantiated.

    ``AnyThing`` is a class; ``AnyThing()`` is an instance. Both compare equal to
    everything, so both weaken an assertion identically -- but only the instance
    is *detectable*. tripwire's own all-wildcard guard tests
    ``isinstance(v, AnyThing)`` (``_verifier.py:223,261``), and
    ``isinstance(AnyThing, AnyThing)`` is False. So the bare class matches every
    value AND slips past the guard built to catch exactly that, while the
    instance trips it. A bare-class reference is never what anyone means.
    """
    out: list[Violation] = []
    called: set[int] = set()
    imported: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called.add(id(node.func))
        # `from dirty_equals import AnyThing` is a binding, not a usage.
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imported.add(id(node))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Name, ast.Attribute)):
            continue
        if id(node) in called:
            continue
        dotted = _dotted(node)
        if dotted is None or dotted.split(".")[-1] not in WILDCARD_CLASSES:
            continue
        out.append(
            Violation(
                rel,
                node.lineno,
                "bare-class wildcard",
                f"{dotted} used as a value; write {dotted}() so tripwire's "
                "all-wildcard guard can see it",
            )
        )
    return out


def _all_wildcard_assertions(tree: ast.AST, rel: str) -> list[Violation]:
    """Flag ``assert_*(...)`` calls whose every keyword value is a wildcard.

    Such an assertion has no failing input: it passes for any behaviour the code
    under test could possibly exhibit, including none at all. It is a green
    mirage -- strictly worse than no assertion, because it reads as coverage.
    """
    out: list[Violation] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert_")
        ):
            continue
        # Positional args are opaque here; only judge the all-keyword shape
        # tripwire's assert_call uses.
        if node.args or not node.keywords:
            continue
        if any(kw.arg is None for kw in node.keywords):
            continue
        if all(_is_wildcard(kw.value) for kw in node.keywords):
            fields = ", ".join(kw.arg for kw in node.keywords)
            out.append(
                Violation(
                    rel,
                    node.lineno,
                    "all-wildcard assertion",
                    f"{node.func.attr}({fields}) -- every field is a wildcard, "
                    "so this assertion cannot fail",
                )
            )
    return out


def scan_wildcards(path: Path, rel: str) -> list[Violation]:
    """Return every wildcard-matcher violation in one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    return _all_wildcard_assertions(tree, rel) + _bare_class_wildcards(tree, rel)


def scan_file(path: Path, rel: str) -> list[Violation]:
    """Return every forbidden-mocking occurrence in one file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    out: list[Violation] = []
    for node in ast.walk(tree):
        # monkeypatch.<mocking method>(...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "monkeypatch"
            and node.func.attr in MOCK_METHODS
        ):
            out.append(
                Violation(rel, node.lineno, "monkeypatch", f"monkeypatch.{node.func.attr}()")
            )
        # import mock / import unittest.mock
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in MOCK_MODULES or a.name.startswith("unittest.mock"):
                    out.append(Violation(rel, node.lineno, "unittest.mock", f"import {a.name}"))
        # from unittest.mock import ... / from mock import ...
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module in MOCK_MODULES or node.module.startswith("unittest.mock")):
                out.append(
                    Violation(rel, node.lineno, "unittest.mock", f"from {node.module} import ...")
                )
        # def test_x(mocker) -- the pytest-mock fixture
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            if any(a.arg == "mocker" for a in args.posonlyargs + args.args + args.kwonlyargs):
                out.append(Violation(rel, node.lineno, "pytest-mock", f"{node.name}(mocker)"))
    return out


def find_violations(root: Path) -> list[Violation]:
    """Violations exceeding each file's allowlisted legacy budget.

    Two independent ratchets, so converting mocking cannot pay for new wildcards
    or vice versa.
    """
    out: list[Violation] = []
    for path in _iter_test_files(root):
        rel = path.relative_to(root).as_posix()
        for scan, allow in ((scan_file, ALLOWLIST), (scan_wildcards, WILDCARD_ALLOWLIST)):
            found = sorted(scan(path, rel))
            budget = allow.get(rel, 0)
            if len(found) > budget:
                # Report only the overage, deterministically: the tail beyond budget.
                out.extend(found[budget:])
    return out


def format_violation(v: Violation) -> str:
    return f"{v.path}:{v.lineno}: forbidden {v.kind} -- {v.detail} (use tripwire; see AGENTS.md)"


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[1]
    violations = find_violations(root)
    if violations:
        print(f"{len(violations)} forbidden mocking violation(s):", file=sys.stderr)
        for v in violations:
            print(format_violation(v), file=sys.stderr)
        return 1
    print("OK: no new forbidden mocking under tests/")
    return 0


# --- Legacy budget -----------------------------------------------------------
# Generated from the tree at the time this gate was introduced. Each entry is a
# CAP, not a target: lower it whenever you convert a file to tripwire. Never
# raise an entry, and never add a new one -- new tests must use tripwire.
ALLOWLIST: dict[str, int] = {}

# Same ratchet semantics, tracked separately: all-wildcard assertions and
# bare-class wildcard references.
WILDCARD_ALLOWLIST: dict[str, int] = {}


def _load_allowlist() -> None:
    import json

    p = Path(__file__).with_name("forbidden_mocking_allowlist.json")
    if not p.is_file():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    # Legacy shape was a flat {path: cap} map of mocking caps only.
    if "mocking" in data or "wildcards" in data:
        ALLOWLIST.update(data.get("mocking", {}))
        WILDCARD_ALLOWLIST.update(data.get("wildcards", {}))
    else:
        ALLOWLIST.update(data)


_load_allowlist()

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
