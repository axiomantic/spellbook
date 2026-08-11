"""Tests for spellbook.planlint.cli — the spellbook-planlint entry point.

The CLI is a thin wrapper (design §1.4): it holds no rule logic. Exercised
as a real subprocess, matching test_branch_context.py's "no mocking of the
subject under test" convention, since the whole point is to prove the
INSTALLED entry point works, not just the Python function.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "planlint"
REPO_ROOT = Path(__file__).resolve().parents[2]

# pyproject.toml sets a GLOBAL `timeout = 30`. Every test in this module spawns
# a fresh interpreter, and interpreter start plus package import can be slow on
# a cold cache — so the per-test budget is raised here and the subprocess's own
# timeout is set BELOW it. Ordering matters: if the outer budget fired first,
# the failure would be an opaque pytest-timeout kill instead of the
# subprocess.TimeoutExpired that names the command that hung.
pytestmark = pytest.mark.timeout(60)

SUBPROCESS_TIMEOUT = 20


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "spellbook.planlint.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
        check=False,
    )


def test_cli_exits_zero_on_a_clean_plan():
    result = _run_cli(str(FIXTURES / "clean_plan.md"))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.slow
def test_the_installed_console_script_runs():
    """`python -m spellbook.planlint.cli` proves the MODULE runs. It says
    nothing about the `[project.scripts]` entry THIS TASK adds — a typo in the
    `spellbook-planlint = "spellbook.planlint.cli:main"` target, or the entry
    landing in the wrong table, leaves every other test in this file green
    while the thing users actually type does not exist.

    Skipped, not failed, when the console script is not on PATH: an editable
    install that predates this task's `pyproject.toml` edit has not
    regenerated its scripts yet, and that is an environment fact, not a defect
    in the port. The skip REASON names the reinstall, so a skipped run is
    actionable rather than silent. Marked slow because it depends on an
    install step having happened.
    """
    executable = shutil.which("spellbook-planlint")
    if executable is None:
        pytest.skip(
            "spellbook-planlint not on PATH; run `uv sync` (or reinstall the "
            "project) so the new [project.scripts] entry is generated, then "
            "re-run this test"
        )
    result = subprocess.run(
        [executable, str(FIXTURES / "clean_plan.md")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_exits_nonzero_on_a_finding(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text((FIXTURES / "neg_check_empty.md").read_text(encoding="utf-8"), encoding="utf-8")
    result = _run_cli(str(bad))
    assert result.returncode != 0
    assert "check-empty" in result.stdout


def test_cli_exits_zero_on_a_legacy_plan_and_says_so():
    result = _run_cli(str(FIXTURES / "legacy_plan.md"))
    assert result.returncode == 0
    assert "not linted" in result.stdout.lower() or "legacy" in result.stdout.lower()


def test_cli_reports_missing_file_and_exits_nonzero(tmp_path):
    result = _run_cli(str(tmp_path / "does_not_exist.md"))
    assert result.returncode != 0


def test_cli_with_repo_root_exits_zero_on_a_clean_plan(tmp_path):
    """`--repo-root` arrives from argparse as a `str`, and
    `rules/files.py` does `ctx.repo_root / entry.path`. Without a coercion to
    `Path` at the CLI boundary that is a `TypeError`, which the per-rule error
    barrier would swallow into a CRASH — a nonzero exit blaming the plan for a
    caller bug. This test decides the coercion; nothing else does.

    Run under `--phase execution` because that is the only phase in which
    `clean_plan.md` can be clean against a populated tree: it names
    `spellbook/sample/first.py` under `Create:` in Task 1 and `Modify:` in
    Task 2, so any tree that satisfies `modify-path-missing` necessarily
    trips `create-path-exists` — which EXECUTION turns off (design §4.5).
    """
    for relative in (
        "spellbook/sample/first.py",
        "tests/test_scripts/test_sample_first.py",
        "tests/test_scripts/test_sample_second.py",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# x\n", encoding="utf-8")

    result = _run_cli(
        str(FIXTURES / "clean_plan.md"),
        "--repo-root",
        str(tmp_path),
        "--phase",
        "execution",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CRASHED" not in result.stdout
