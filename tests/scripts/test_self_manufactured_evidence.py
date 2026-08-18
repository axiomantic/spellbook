"""The self-manufactured-evidence gate, aimed at the real tree and proven able to fail.

This module is the one place where the gate is pointed at THIS repository. It
would be a poor joke for a check that hunts self-manufactured evidence to be
green only on corpora it built itself, so the structure is deliberate:

* a REAL-TREE GREEN -- ``evaluate(REPO_ROOT)`` over the actual checkout, with
  no scratch anything, asserting no corpus check is running on manufactured
  input alone and nothing is unclassifiable;
* DISCOVERY FLOORS -- a discovery pass that silently matched nothing would
  report that same green over an empty population, so both shapes get a floor;
* RED PROOFS -- planted violations in a synthetic repository, one per decision
  the classifier makes, including the two taint boundaries (a fixture that
  redirects the environment, a fixture that returns a temporary path) whose
  absence used to produce a FALSE CLEAR.

The synthetic repository in the RED proofs is manufactured input, and that is
correct: it drives the subject to prove the subject can fail. What makes this
module honest is that the green above is not.
"""

import sys
from pathlib import Path, PureWindowsPath

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_self_manufactured_evidence import (
    discover_script_checks,
    evaluate,
    rel_posix,
)

VERDICTS, COUNTS = evaluate(REPO_ROOT)
BY_NAME = {v.name: v for v in VERDICTS}


# ---------------------------------------------------------------------------
# Real-tree green
# ---------------------------------------------------------------------------


def test_no_corpus_check_runs_on_self_manufactured_input_alone():
    """The gate itself, over the real checkout."""
    offenders = [v for v in VERDICTS if v.status == "manufactured"]
    assert not offenders, "corpus checks with no real-tree call site:\n  " + "\n  ".join(
        f"{v.name} ({v.shape}) <- {v.evidence}" for v in offenders
    )


def test_nothing_in_the_tree_is_unclassifiable():
    """An unclassified call site is a hole in the taint analysis, not a pass."""
    unknown = [v for v in VERDICTS if v.status == "unclassified"]
    assert not unknown, "call sites this gate cannot classify:\n  " + "\n  ".join(
        f"{v.name} <- {v.evidence}" for v in unknown
    )


# ---------------------------------------------------------------------------
# Discovery floors -- the silent-no-op guard
# ---------------------------------------------------------------------------


def test_script_shaped_discovery_floor():
    """Discovery that matches nothing would report a clean pass over nothing."""
    scripts = [v for v in VERDICTS if v.shape == "script"]
    assert len(scripts) >= 8, (
        f"only {len(scripts)} script-shaped corpus checks discovered. Either the "
        "checkers changed shape and the discovery regexes no longer match them, "
        "or the floor is stale."
    )


def test_test_shaped_discovery_floor():
    """The test-resident population is the richer one; it must not vanish."""
    tests = [v for v in VERDICTS if v.shape == "test"]
    assert len(tests) >= 4, (
        f"only {len(tests)} test-resident corpus checks discovered. Test-resident "
        "checks are invisible to script discovery; a zero here means the gate "
        "silently stopped covering them."
    )


def test_the_gate_discovers_itself():
    """A checker that cannot see its own shape is not checking that shape."""
    assert "check_self_manufactured_evidence" in discover_script_checks(REPO_ROOT)


# ---------------------------------------------------------------------------
# Emitted names are POSIX-shaped on every platform
# ---------------------------------------------------------------------------


def test_emitted_name_is_posix_shaped_under_a_windows_path_flavour():
    """The separator the emitted name carries must not follow the host OS.

    ``rel_posix`` is flavour-agnostic, so a ``PureWindowsPath`` pair exercises
    the Windows rendering from a POSIX runner: ``str()`` on that flavour yields
    a backslash and ``as_posix()`` does not. Drop the normalisation and this
    assertion goes RED here, not only on Windows.
    """
    root = PureWindowsPath(r"C:\checkout")
    assert rel_posix(root / "tests" / "test_corpus_shape.py", root) == (
        "tests/test_corpus_shape.py"
    )


def test_no_verdict_over_the_real_tree_carries_a_backslash():
    """The consumer-visible names, taken from the real-tree pass CI reads."""
    offenders = [
        (v.name, v.evidence, ref)
        for v in VERDICTS
        for ref in v.referenced_by + [v.name, v.evidence]
        if "\\" in ref
    ]
    assert not offenders, offenders


def test_known_checkers_are_reported_as_really_covered():
    """Sanity anchor: the checkers that ARE aimed at the tree read as such."""
    for stem in ("check_reference_resolution", "check_removed_mode_tokens"):
        assert BY_NAME[stem].status == "real", BY_NAME[stem]


# ---------------------------------------------------------------------------
# Synthetic repository for the RED proofs
# ---------------------------------------------------------------------------

VALIDATOR = '''\
from pathlib import Path


def check_corpus(root):
    """Enumerate the skills corpus."""
    return sorted((Path(root) / "skills").rglob("*.md"))


def main(argv=None):
    return 0 if check_corpus(Path(__file__).resolve().parent.parent) else 1
'''


def _mini_repo(tmp_path: Path, tests: dict[str, str], precommit: str = "") -> Path:
    """A synthetic repository holding one planted validator and the given tests."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "skills" / "planted").mkdir(parents=True)
    (root / "skills" / "planted" / "SKILL.md").write_text("# planted\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts" / "check_planted.py").write_text(VALIDATOR, encoding="utf-8")
    (root / ".pre-commit-config.yaml").write_text(precommit, encoding="utf-8")
    for name, body in tests.items():
        (root / "tests" / name).write_text(body, encoding="utf-8")
    return root


def _status(root: Path, name: str) -> str:
    verdicts, _ = evaluate(root)
    matches = [v for v in verdicts if v.name == name]
    assert matches, f"{name!r} was not discovered; verdicts: {[v.name for v in verdicts]}"
    return matches[0].status


# ---------------------------------------------------------------------------
# RED proofs -- script-shaped
# ---------------------------------------------------------------------------


DIRECT_IMPORT = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_planted
"""


def test_red_validator_driven_only_by_a_scratch_tree(tmp_path):
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted.py": DIRECT_IMPORT
            + """

def test_finds_nothing(tmp_path):
    (tmp_path / "skills").mkdir()
    assert check_planted.check_corpus(tmp_path) == []
"""
        },
    )
    assert _status(repo, "check_planted") == "manufactured"


def test_green_validator_driven_by_the_checkout(tmp_path):
    """The gate is not a blanket fail: one root-derived call site clears it."""
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted.py": DIRECT_IMPORT
            + """

REPO = Path(__file__).resolve().parents[1]


def test_real(tmp_path):
    assert check_planted.check_corpus(REPO)
"""
        },
    )
    assert _status(repo, "check_planted") == "real"


def test_green_validator_registered_in_pre_commit(tmp_path):
    """Registration aims it at the checkout on every commit."""
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted.py": DIRECT_IMPORT
            + """

def test_finds_nothing(tmp_path):
    (tmp_path / "skills").mkdir()
    assert check_planted.check_corpus(tmp_path) == []
"""
        },
        precommit="repos:\n  - repo: local\n    hooks:\n"
        "      - id: planted\n        entry: python3 scripts/check_planted.py\n",
    )
    assert _status(repo, "check_planted") == "real"


# ---------------------------------------------------------------------------
# RED proofs -- the taint boundaries
# ---------------------------------------------------------------------------


def test_red_fixture_that_redirects_the_environment_is_not_real_coverage(tmp_path):
    """Defect: a subprocess launch looks unredirected at the call site.

    ``_run_cli`` names no temporary path. The redirection happens one boundary
    away, inside a fixture, via ``monkeypatch.setenv``. An analysis that stops
    at the call site credits this as a real-tree launch -- a FALSE CLEAR, the
    dangerous direction. This is the exact shape of
    ``tests/scripts/test_develop_gate_ledger.py``.
    """
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted_cli.py": """\
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_planted.py"


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("SPELLBOOK_DIR", str(tmp_path))
    return tmp_path


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args], capture_output=True, text=True
    )


def test_cli_runs(scratch):
    assert _run_cli("show").returncode in (0, 1)
"""
        },
    )
    assert _status(repo, "check_planted") == "manufactured"


def test_green_subprocess_launch_with_no_redirection_anywhere(tmp_path):
    """The counterpart: with the fixture gone, the same launch IS real coverage.

    Without this pair, the test above would also pass if the gate simply
    stopped crediting every subprocess launch.
    """
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted_cli.py": """\
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_planted.py"


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args], capture_output=True, text=True
    )


def test_cli_runs():
    assert _run_cli("show").returncode in (0, 1)
"""
        },
    )
    assert _status(repo, "check_planted") == "real"


def test_red_conftest_fixture_redirection_is_seen(tmp_path):
    """The redirecting fixture may live in conftest.py, a file away."""
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted_cli.py": """\
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_planted.py"


def test_cli_runs(scratch):
    assert subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True
    ).returncode in (0, 1)
"""
        },
    )
    (repo / "tests" / "conftest.py").write_text(
        """\
import pytest


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path
""",
        encoding="utf-8",
    )
    assert _status(repo, "check_planted") == "manufactured"


def test_red_unknown_fixture_is_unclassified_not_cleared(tmp_path):
    """A parameter naming no fixture this gate can read is never credited."""
    repo = _mini_repo(
        tmp_path,
        {
            "test_planted_cli.py": """\
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_planted.py"


def test_cli_runs(fixture_defined_in_a_plugin):
    assert subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True
    ).returncode in (0, 1)
"""
        },
    )
    assert _status(repo, "check_planted") == "unclassified"


# ---------------------------------------------------------------------------
# RED proofs -- test-resident checks
# ---------------------------------------------------------------------------


def test_red_test_resident_check_enumerating_only_a_scratch_corpus(tmp_path):
    """A corpus check living inside pytest, green on a corpus it manufactured.

    The scratch tree reaches the enumeration through a fixture RETURN, the
    second taint boundary. Asserting ``manufactured`` rather than merely
    "flagged" is what pins that propagation: without it the fixture parameter
    is untraceable and the verdict would be ``unclassified``.
    """
    repo = _mini_repo(
        tmp_path,
        {
            "test_corpus_shape.py": """\
import pytest


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "skills" / "a").mkdir(parents=True)
    (tmp_path / "skills" / "a" / "SKILL.md").write_text("x")
    return tmp_path


def test_every_skill_has_a_body(corpus):
    for path in (corpus / "skills").rglob("SKILL.md"):
        assert path.read_text()
"""
        },
    )
    assert _status(repo, "tests/test_corpus_shape.py") == "manufactured"


def test_green_test_resident_check_enumerating_the_checkout(tmp_path):
    repo = _mini_repo(
        tmp_path,
        {
            "test_corpus_shape.py": """\
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_every_skill_has_a_body():
    for path in (REPO / "skills").rglob("SKILL.md"):
        assert path.read_text()
"""
        },
    )
    assert _status(repo, "tests/test_corpus_shape.py") == "real"


def test_installer_shaped_test_is_not_a_corpus_check(tmp_path):
    """A module with a first-party SUBJECT is testing that subject.

    Its scratch trees are the subject's input and output, not a manufactured
    corpus standing in for the real one. This is the narrowing that keeps the
    installer suites out of the population; without it they are false
    positives.
    """
    repo = _mini_repo(tmp_path, {})
    (repo / "installer").mkdir()
    (repo / "installer" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "tests" / "test_install.py").write_text(
        """\
from installer import place


def test_installs_rules(tmp_path):
    target = tmp_path / "claude" / "rules"
    place(target)
    assert sorted(p.name for p in target.glob("*.md")) == ["00-core.md"]
""",
        encoding="utf-8",
    )
    verdicts, _ = evaluate(repo)
    assert "tests/test_install.py" not in {v.name for v in verdicts}


def test_unreferenced_checker_is_a_plain_gap_not_an_instance(tmp_path):
    """No test mentions it, so it never wore the costume of a verified one."""
    repo = _mini_repo(tmp_path, {})
    assert _status(repo, "check_planted") == "unreferenced"


@pytest.mark.parametrize("status", ["manufactured", "unclassified"])
def test_exit_code_is_nonzero_for_every_failing_status(tmp_path, status):
    """The verdict a consumer reads must follow the worst item, not the count.

    An aggregator that reports findings and still exits 0 is the silent
    failure this whole gate exists to catch.
    """
    from check_self_manufactured_evidence import main

    bodies = {
        "manufactured": DIRECT_IMPORT
        + """

def test_finds_nothing(tmp_path):
    (tmp_path / "skills").mkdir()
    assert check_planted.check_corpus(tmp_path) == []
""",
        "unclassified": """\
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_planted.py"


def test_cli_runs(fixture_defined_in_a_plugin):
    assert subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True
    ).returncode in (0, 1)
""",
    }
    repo = _mini_repo(tmp_path, {"test_planted.py": bodies[status]})
    assert _status(repo, "check_planted") == status
    assert main([str(repo)]) == 1


def test_exit_code_is_zero_on_the_real_tree():
    """The consumer-visible signal, taken from the same path CI takes."""
    from check_self_manufactured_evidence import main

    assert main([str(REPO_ROOT)]) == 0
