"""Tests for spellbook.planlint.cli — the spellbook-planlint entry point.

The CLI is a thin wrapper (design §1.4): it holds no rule logic. Exercised
as a real subprocess, matching test_branch_context.py's "no mocking of the
subject under test" convention, since the whole point is to prove the
INSTALLED entry point works, not just the Python function.

One test (the rule-crash exit-code test) calls `cli.main()` directly instead
of via subprocess, because triggering a genuine rule crash from a black-box
subprocess would require a malformed fixture that happens to break a real
rule module — fragile and liable to silently stop crashing once a rule gets
more defensive. `tripwire.mock` on `registry._rules` (the same seam
test_planlint_registry.py and test_planlint_api.py use) gives a crash that
is deliberate, readable, and immune to a rule module's own bug fixes.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import tripwire

from spellbook.planlint import api, cli, registry
from spellbook.planlint.finding import LintResult

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
    assert result.returncode == 0
    plan = str(FIXTURES / "clean_plan.md")
    assert result.stdout == (
        "structure: clean (2 task bodies examined)\n"
        "depends: clean (2 task blocks examined)\n"
        "checks: clean (2 task blocks examined)\n"
        "consistency: clean (2 task blocks examined)\n"
        "files: skipped (no repo_root supplied)\n"
        "ownership: clean (2 task blocks examined)\n"
        "schema: clean (2 task blocks examined)\n"
        f"{plan}: clean (6 of 7 rule(s) decided, 1 skipped, 0 findings)\n"
    )
    assert result.stderr == ""


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


def test_cli_exits_nonzero_on_a_finding():
    bad = FIXTURES / "neg_check_empty.md"
    result = _run_cli(str(bad))
    assert result.returncode == 1
    assert result.stdout == (
        "structure: clean (1 task bodies examined)\n"
        "depends: clean (1 task blocks examined)\n"
        "checks: 1 finding(s) (1 task blocks examined)\n"
        "  [ERROR] check-empty  Task 1  line 10\n"
        "      section: Task 1: Empty check\n"
        "      the `Check:` field is absent or empty; a task with no proving "
        "command has no definition of done\n"
        "consistency: clean (1 task blocks examined)\n"
        "files: skipped (no repo_root supplied)\n"
        "ownership: clean (1 task blocks examined)\n"
        "schema: clean (1 task blocks examined)\n"
        f"{bad}: 1 finding(s), 1 error(s), 0 crash(es)\n"
    )
    assert result.stderr == ""


def test_cli_exits_zero_on_a_legacy_plan_and_says_so():
    result = _run_cli(str(FIXTURES / "legacy_plan.md"))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == (
        f"{FIXTURES / 'legacy_plan.md'}: not linted (no Schema: field (legacy plan))\n"
    )


def test_cli_reports_missing_file_and_exits_nonzero(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    result = _run_cli(str(missing))
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        f"{missing}: not linted (unreadable: [Errno 2] No such file or directory: '{missing}')\n"
    )


def test_cli_reports_non_utf8_file_and_exits_nonzero(tmp_path):
    bad = tmp_path / "bad_encoding.md"
    bad.write_bytes(b"\xff\xfe Schema: planlint-v1")
    result = _run_cli(str(bad))
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == f"{bad}: not linted (not UTF-8)\n"


def test_cli_rejects_a_nonexistent_repo_root(tmp_path):
    missing_root = tmp_path / "does_not_exist_dir"
    result = _run_cli(str(FIXTURES / "clean_plan.md"), "--repo-root", str(missing_root))
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "usage: spellbook-planlint [-h] [--repo-root REPO_ROOT]\n"
        "                          [--phase {authoring,review,execution}]\n"
        "                          plan\n"
        f"spellbook-planlint: error: --repo-root {str(missing_root)!r} is not an "
        "existing directory\n"
    )


def test_cli_rejects_an_unrecognized_phase():
    result = _run_cli(str(FIXTURES / "clean_plan.md"), "--phase", "bogus")
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "usage: spellbook-planlint [-h] [--repo-root REPO_ROOT]\n"
        "                          [--phase {authoring,review,execution}]\n"
        "                          plan\n"
        "spellbook-planlint: error: argument --phase: invalid choice: 'bogus' "
        "(choose from 'authoring', 'review', 'execution')\n"
    )


def test_cli_phase_choices_exactly_match_the_real_phase_enum():
    """I4: pins that argparse's `choices=[p.value for p in Phase]` is not
    silently stale against the real enum — a future `Phase` member that the
    CLI forgets to accept would fail this test instead of surfacing only as
    a confusing `invalid choice` at runtime."""
    result = _run_cli("--help")
    assert result.returncode == 0
    expected_choices = "{" + ",".join(p.value for p in api.Phase) + "}"
    assert f"--phase {expected_choices}" in result.stdout


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
    assert result.returncode == 0
    plan = str(FIXTURES / "clean_plan.md")
    assert result.stdout == (
        "structure: clean (2 task bodies examined)\n"
        "depends: clean (2 task blocks examined)\n"
        "checks: clean (2 task blocks examined)\n"
        "consistency: clean (2 task blocks examined)\n"
        "files: clean (3 Files: entries examined)\n"
        "ownership: clean (2 task blocks examined)\n"
        "schema: clean (2 task blocks examined)\n"
        f"{plan}: clean (7 rule(s), 0 findings)\n"
    )
    assert result.stderr == ""
    assert "CRASHED" not in result.stdout


def test_cli_exits_2_and_reports_a_rule_crash_on_stderr(capsys):
    """I4: a rule CRASH (registry.RuleCrash) must exit 2 (M3: distinct from
    the exit-1 "plan has defects" case) and land on stderr (M2: diagnostics,
    not linter findings)."""

    def crashing_rule(ctx):
        raise KeyError("boom")

    def survivor_rule(ctx):
        return LintResult(name="survivor", findings=[], examined=1)

    crasher = registry.Rule(
        name="crasher", run=crashing_rule, emits=frozenset(), phases=frozenset(api.Phase)
    )
    survivor = registry.Rule(
        name="survivor", run=survivor_rule, emits=frozenset(), phases=frozenset(api.Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((crasher, survivor))
    with tripwire:
        exit_code = cli.main([str(FIXTURES / "clean_plan.md")])
    rules_mock.assert_call(args=(), kwargs={})

    assert exit_code == 2
    captured = capsys.readouterr()
    plan = str(FIXTURES / "clean_plan.md")
    # summary_line() always goes to stdout (it is the one-line machine-
    # parseable outcome); the full rule-by-rule report — which embeds the
    # crash — is the diagnostic and goes to stderr instead.
    assert captured.out == f"{plan}: 0 finding(s), 0 error(s), 1 crash(es)\n"
    assert "crasher: CRASHED (KeyError: 'boom')" in captured.err
    assert "survivor: clean (1 inputs examined)" in captured.err
