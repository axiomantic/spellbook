"""The dedupe-skill verification gates must actually be run by CI.

The defect this guards: ``tests/dedupe-skill/`` shipped nine gate scripts
that no runner, workflow, or test ever invoked. Two of them had been red
since ``a303f811`` -- a feature drifted straight through the invariants
they encode and nothing reported it, because a gate nobody runs is
indistinguishable from a gate that passes.

Wiring alone is not enough to guard that. A runner that globbed zero
scripts would also exit 0, reproducing the original silence with a green
banner on top. So the floor on the discovered count is asserted here, and
the runner is driven to RED in a sandbox by a planted failing gate --
only the green-to-red transition proves a failing gate reaches the exit
status CI reads.

The sandbox uses synthetic gates. What is under test here is the
aggregator -- discovery, the floor, and whether a child's non-zero status
survives to the runner's exit code. The real gates carry external tool
dependencies and are executed by the ``dedupe-skill-gates`` CI job, which
this module asserts exists and calls the runner.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

# The gates are a POSIX shell suite invoked by an ubuntu-only CI job. On
# Windows `bash` resolves to the WSL stub, which runs nothing.
pytestmark = pytest.mark.posix_only

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_DIR = REPO_ROOT / "tests" / "dedupe-skill"
RUNNER = GATE_DIR / "run-all-gates.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"

# The floor the runner enforces. Duplicated here deliberately: if someone
# lowers it in the runner to accommodate a deleted gate, this test is the
# thing that notices.
MIN_GATES = 9


def _run(runner: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(runner)],
        capture_output=True,
        text=True,
        check=False,
        cwd=runner.parent,
    )


def test_runner_exists_and_is_executable() -> None:
    assert RUNNER.is_file(), f"{RUNNER} is missing; the gates would be unrun"


def test_gate_count_meets_floor() -> None:
    """Fewer gates than the floor means one was deleted or renamed away."""
    gates = sorted(GATE_DIR.glob("verify-*.sh"))
    assert len(gates) >= MIN_GATES, f"found {len(gates)} gate scripts: {gates}"


def test_runner_floor_is_not_below_the_expected_minimum() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert f"MIN_GATES={MIN_GATES}" in text, (
        "the runner's discovery floor was changed; a lowered floor lets a "
        "deleted gate pass unnoticed"
    )


def test_ci_workflow_invokes_the_runner() -> None:
    """A runner no workflow calls is the original defect wearing a new name."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "tests/dedupe-skill/run-all-gates.sh" in text


def test_ci_workflow_installs_gate_dependencies() -> None:
    """The gates fail loudly on a missing tool; CI must supply all three."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for tool in ("jq", "perl", "markdownlint-cli2"):
        assert tool in text, f"CI does not install {tool}"


@pytest.fixture
def staged_runner(tmp_path: Path) -> Path:
    """Stage the runner alone, with synthetic gates in place of the real ones.

    The runner derives the repo root as ``<script dir>/../..``. Synthetic
    gates keep this test free of the gates' external tool dependencies:
    what is under test is the aggregator -- discovery, the floor, and
    whether a child's non-zero status reaches the runner's exit code.
    """
    staged = tmp_path / "tests" / "dedupe-skill"
    staged.mkdir(parents=True)
    shutil.copy(RUNNER, staged / RUNNER.name)
    for index in range(MIN_GATES):
        gate = staged / f"verify-synthetic-{index}.sh"
        gate.write_text(f'#!/usr/bin/env bash\necho "synthetic gate {index}"\nexit 0\n')
        gate.chmod(0o755)
    return staged


def test_staged_runner_is_green(staged_runner: Path) -> None:
    """The sandbox baseline must pass, or the red cases prove nothing."""
    result = _run(staged_runner / RUNNER.name)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Failed:     0" in result.stdout
    assert "PASS: dedupe-skill gates" in result.stdout


def test_a_failing_gate_fails_the_runner(staged_runner: Path) -> None:
    """A planted red gate must reach the runner's exit status."""
    plant = staged_runner / "verify-planted-failure.sh"
    plant.write_text('#!/usr/bin/env bash\necho "planted gate failure"\nexit 1\n')
    plant.chmod(0o755)

    result = _run(staged_runner / RUNNER.name)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "planted gate failure" in result.stdout
    assert "FAIL: verify-planted-failure.sh" in result.stdout
    assert "PASS: dedupe-skill gates" not in result.stdout


def test_runner_does_not_invert_a_negative_control_gate(staged_runner: Path) -> None:
    """The ``-neg`` gates invert internally; the runner must not invert again.

    A runner that flipped a child's status would turn the calibrated
    negative controls into passes-when-broken, which is worse than leaving
    them unwired.
    """
    result = _run(staged_runner / RUNNER.name)
    assert result.returncode == 0
    assert f"Passed:     {MIN_GATES}" in result.stdout


def test_empty_discovery_fails_rather_than_passing(staged_runner: Path) -> None:
    """A glob that collects nothing must go red, not report a clean run."""
    for gate in staged_runner.glob("verify-*.sh"):
        gate.unlink()

    result = _run(staged_runner / RUNNER.name)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "discovery floor breached" in result.stdout
    assert "PASS: dedupe-skill gates" not in result.stdout


def test_partial_discovery_fails_the_floor(staged_runner: Path) -> None:
    """One gate short of the floor is a deletion, not a smaller suite."""
    next(iter(sorted(staged_runner.glob("verify-*.sh")))).unlink()

    result = _run(staged_runner / RUNNER.name)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "discovery floor breached" in result.stdout
