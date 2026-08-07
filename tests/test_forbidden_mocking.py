"""Ratchet gate: no NEW non-tripwire mocking may enter ``tests/``.

AGENTS.md ("Testing with Tripwire") makes tripwire the only permitted mocking
framework: no ``unittest.mock``, no pytest-mock ``mocker``, and no
``monkeypatch.setattr/setitem/delattr/delitem``. Only ``setenv``, ``delenv``,
``chdir``, and ``syspath_prepend`` remain legitimate monkeypatch uses.

The tree still carries a large legacy population of forbidden calls, so the
checker is a RATCHET: ``scripts/forbidden_mocking_allowlist.json`` records a
per-file CAP of known-legacy occurrences. Converting a file to tripwire (and
lowering its cap) is always allowed; exceeding a cap, or introducing any
forbidden call in a file that has no cap, fails. The population can only shrink.

The reproducible checker lives in ``scripts/check_forbidden_mocking.py``; this
test asserts both directions of the contract:
  - the gate PASSES on the current tree, and
  - the gate FAILS for each forbidden construct when one is planted.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_forbidden_mocking.py"
ALLOWLIST_PATH = REPO_ROOT / "scripts" / "forbidden_mocking_allowlist.json"


def _load_checker():
    """Load the checker module from scripts/ (not an installed package)."""
    spec = importlib.util.spec_from_file_location("check_forbidden_mocking", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_forbidden_mocking"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _load_checker()


# ---------------------------------------------------------------------------
# (1) Ratchet contract: the current tree is within its allowlisted budget.
# ---------------------------------------------------------------------------


def test_current_tree_is_within_allowlisted_budget(checker):
    """No file exceeds its legacy cap, and no uncapped file has any violation.

    Asserts EXACT emptiness so any newly introduced forbidden call surfaces
    here with an actionable ``path:line`` message.
    """
    violations = checker.find_violations(REPO_ROOT)
    assert violations == [], "New forbidden mocking found:\n" + "\n".join(
        checker.format_violation(v) for v in violations
    )


def test_allowlist_is_a_ceiling_not_a_floor(checker):
    """A file with FEWER forbidden calls than its cap must still pass.

    This is what lets the ratchet turn: converting tests to tripwire without
    immediately editing the allowlist must never fail the gate.
    """
    rel = next(iter(json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))["mocking"]))
    original = checker.ALLOWLIST[rel]
    checker.ALLOWLIST[rel] = original + 5  # pretend budget exceeds reality
    try:
        assert checker.find_violations(REPO_ROOT) == []
    finally:
        checker.ALLOWLIST[rel] = original


def test_allowlist_entries_all_correspond_to_real_files(checker):
    """Every allowlisted path exists -- stale entries would hide regressions."""
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entries = [rel for section in allowlist.values() for rel in section]
    missing = [rel for rel in entries if not (REPO_ROOT / rel).is_file()]
    assert missing == [], f"Allowlist references files that no longer exist: {missing}"


# ---------------------------------------------------------------------------
# (2) Planted-violation contract: each forbidden construct is detected.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "kind", "detail"),
    [
        (
            'def test_a(monkeypatch):\n    monkeypatch.setattr("os.getcwd", lambda: "/x")\n',
            "monkeypatch",
            "monkeypatch.setattr()",
        ),
        (
            'def test_a(monkeypatch):\n    monkeypatch.setitem({}, "k", 1)\n',
            "monkeypatch",
            "monkeypatch.setitem()",
        ),
        (
            'def test_a(monkeypatch):\n    monkeypatch.delattr("os.getcwd")\n',
            "monkeypatch",
            "monkeypatch.delattr()",
        ),
        (
            'def test_a(monkeypatch):\n    monkeypatch.delitem({}, "k")\n',
            "monkeypatch",
            "monkeypatch.delitem()",
        ),
        (
            "from unittest.mock import MagicMock\n",
            "unittest.mock",
            "from unittest.mock import ...",
        ),
        ("import unittest.mock\n", "unittest.mock", "import unittest.mock"),
        ("import mock\n", "unittest.mock", "import mock"),
        ("def test_a(mocker):\n    pass\n", "pytest-mock", "test_a(mocker)"),
    ],
    ids=[
        "setattr",
        "setitem",
        "delattr",
        "delitem",
        "from-unittest-mock",
        "import-unittest-mock",
        "import-mock",
        "mocker-fixture",
    ],
)
def test_planted_forbidden_construct_is_detected(checker, tmp_path, source, kind, detail):
    """Each forbidden construct planted in an uncapped test file is reported."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_planted.py").write_text(source, encoding="utf-8")

    violations = checker.find_violations(tmp_path)

    assert len(violations) == 1, f"expected exactly one violation, got {violations}"
    assert violations[0].path == "tests/test_planted.py"
    assert violations[0].kind == kind
    assert violations[0].detail == detail


def test_exceeding_an_existing_cap_is_detected(checker, tmp_path):
    """A capped file that grows past its cap reports only the OVERAGE.

    Two forbidden calls against a cap of one yields exactly one violation,
    pointing at the second (new) call -- so the message blames the added line,
    not the pre-existing legacy one.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_capped.py").write_text(
        'def test_a(monkeypatch):\n'
        '    monkeypatch.setattr("os.getcwd", lambda: "/x")\n'
        '    monkeypatch.setattr("os.getpid", lambda: 1)\n',
        encoding="utf-8",
    )
    checker.ALLOWLIST["tests/test_capped.py"] = 1
    try:
        violations = checker.find_violations(tmp_path)
    finally:
        del checker.ALLOWLIST["tests/test_capped.py"]

    assert len(violations) == 1
    assert violations[0].lineno == 3


def test_prose_mentioning_unittest_mock_is_not_flagged(checker, tmp_path):
    """Docstrings/comments naming the forbidden APIs must NOT trip the gate.

    Detection is AST-based precisely so that the many test docstrings which
    explain the tripwire rule (and therefore name ``unittest.mock`` and
    ``monkeypatch.setattr``) do not register as violations.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_prose.py").write_text(
        '"""Tripwire rule: no unittest.mock, no monkeypatch.setattr here."""\n'
        "# monkeypatch.setattr('os.getcwd', ...) would be forbidden\n"
        "def test_a():\n"
        "    pass\n",
        encoding="utf-8",
    )

    assert checker.find_violations(tmp_path) == []


# ---------------------------------------------------------------------------
# (3) Wildcard matchers: assertions that cannot fail.
# ---------------------------------------------------------------------------


def _plant(tmp_path, source: str, name: str = "test_planted.py"):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / name).write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "kinds"),
    [
        # The exact shape that defeated tripwire's own guard: bare CLASS
        # AnyThing matches every value, but isinstance(AnyThing, AnyThing) is
        # False, so _verifier.py's all-wildcard check never fires.
        (
            "def test_a():\n"
            "    m.assert_call(args=AnyThing, kwargs=AnyThing)\n",
            ["all-wildcard assertion", "bare-class wildcard", "bare-class wildcard"],
        ),
        # Instance form: still an assertion that cannot fail.
        (
            "def test_a():\n"
            "    m.assert_call(args=AnyThing(), kwargs=AnyThing())\n",
            ["all-wildcard assertion"],
        ),
        # A bare class anywhere, not just inside an assertion.
        ("def test_a():\n    sentinel = AnyThing\n", ["bare-class wildcard"]),
        # The legacy unittest.mock spelling of the same property.
        (
            "def test_a():\n    m.assert_call(args=mock.ANY, kwargs=ANY)\n",
            ["all-wildcard assertion"],
        ),
    ],
    ids=["bare-class-in-assert", "instance-in-assert", "bare-class-alone", "mock-ANY"],
)
def test_planted_wildcard_construct_is_detected(checker, tmp_path, source, kinds):
    """Every spelling of an always-true matcher is reported."""
    _plant(tmp_path, source)

    violations = checker.find_violations(tmp_path)

    assert sorted(v.kind for v in violations) == sorted(kinds)


def test_assertion_with_one_real_field_is_not_flagged(checker, tmp_path):
    """A wildcard is only banned when it makes the WHOLE assertion vacuous.

    ``args=(1,)`` still constrains behaviour, so ``kwargs=AnyThing()`` beside it
    is a deliberate don't-care, not a green mirage.
    """
    _plant(tmp_path, "def test_a():\n    m.assert_call(args=(1,), kwargs=AnyThing())\n")

    assert checker.find_violations(tmp_path) == []


def test_importing_anything_is_not_itself_a_violation(checker, tmp_path):
    """The import binds the name; only USING it bare is the trap."""
    _plant(
        tmp_path,
        "from dirty_equals import AnyThing\n"
        "def test_a():\n"
        "    m.assert_call(args=(1,), kwargs=AnyThing())\n",
    )

    assert checker.find_violations(tmp_path) == []


def test_wildcard_ratchet_is_independent_of_the_mocking_ratchet(checker, tmp_path):
    """A mocking budget must not buy wildcards.

    The two populations are tracked separately so that converting monkeypatch
    sites can never silently fund a vacuous assertion in the same file.
    """
    _plant(tmp_path, "def test_a():\n    m.assert_call(args=AnyThing(), kwargs=AnyThing())\n")
    checker.ALLOWLIST["tests/test_planted.py"] = 50
    try:
        violations = checker.find_violations(tmp_path)
    finally:
        checker.ALLOWLIST.pop("tests/test_planted.py", None)

    assert [v.kind for v in violations] == ["all-wildcard assertion"]


def test_allowed_monkeypatch_methods_are_not_flagged(checker, tmp_path):
    """setenv/delenv/chdir/syspath_prepend stay legal under the rule."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_env.py").write_text(
        "def test_a(monkeypatch, tmp_path):\n"
        '    monkeypatch.setenv("A", "1")\n'
        '    monkeypatch.delenv("B", raising=False)\n'
        "    monkeypatch.chdir(tmp_path)\n"
        "    monkeypatch.syspath_prepend(str(tmp_path))\n",
        encoding="utf-8",
    )

    assert checker.find_violations(tmp_path) == []
