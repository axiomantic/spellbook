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


def _run_gate(gate: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(gate), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=gate.parent,
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


# The synthetic pair that models a real gate/negative-control pair. The
# runner selects gates by glob, so a name-selective bug -- one that treats
# ``*-neg.sh`` differently -- only has something to bite when a gate
# carrying that suffix is present in the sandbox.
COUNTERPART_GATE = "verify-synthetic-counterpart.sh"
NEG_GATE = "verify-synthetic-counterpart-neg.sh"
NEG_FIXTURE = "synthetic-violation.md"

# Models a positive gate: clean when run over real content (no argument),
# non-zero when pointed at a negative-control fixture.
_COUNTERPART_SRC = """#!/usr/bin/env bash
set -u
if [ "$#" -eq 0 ]; then
    echo "synthetic counterpart: clean"
    exit 0
fi
echo "synthetic counterpart: violation found in $1"
exit 1
"""

# Models the real ``-neg`` contract: run the positive counterpart against a
# negative-control fixture, exit 0 only when that counterpart returns
# non-zero. Inverting internally is the gate's job, never the runner's.
_NEG_SRC = f"""#!/usr/bin/env bash
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$SCRIPT_DIR/fixtures/{NEG_FIXTURE}"
if [ ! -f "$FIXTURE" ]; then
    echo "FAIL: negative-control fixture missing: $FIXTURE"
    exit 1
fi
if bash "$SCRIPT_DIR/{COUNTERPART_GATE}" "$FIXTURE" >/dev/null 2>&1; then
    echo "FAIL: counterpart silently passed against the negative-control fixture"
    exit 1
fi
echo "PASS: counterpart rejected the negative-control fixture"
exit 0
"""


@pytest.fixture
def staged_runner(tmp_path: Path) -> Path:
    """Stage the runner alone, with synthetic gates in place of the real ones.

    The runner derives the repo root as ``<script dir>/../..``. Synthetic
    gates keep this test free of the gates' external tool dependencies:
    what is under test is the aggregator -- discovery, the floor, and
    whether a child's non-zero status reaches the runner's exit code.

    Two of the staged gates are a counterpart/negative-control pair rather
    than bare ``exit 0`` stubs. A sandbox of uniformly passing gates cannot
    distinguish a runner that leaves statuses alone from one that inverts
    only the negative controls, because there would be no negative control
    to invert.
    """
    staged = tmp_path / "tests" / "dedupe-skill"
    staged.mkdir(parents=True)
    shutil.copy(RUNNER, staged / RUNNER.name)

    fixtures = staged / "fixtures"
    fixtures.mkdir()
    (fixtures / NEG_FIXTURE).write_text("planted violation\n", encoding="utf-8")

    for name, src in ((COUNTERPART_GATE, _COUNTERPART_SRC), (NEG_GATE, _NEG_SRC)):
        gate = staged / name
        gate.write_text(src, encoding="utf-8")
        gate.chmod(0o755)

    for index in range(MIN_GATES - 2):
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


def test_the_sandbox_negative_control_models_the_real_contract(
    staged_runner: Path,
) -> None:
    """The synthetic ``-neg`` gate must invert, not merely exit 0.

    A stub that returned 0 unconditionally would carry the ``-neg`` name
    while exercising nothing, and the inversion test below would pass over
    a hollow control.
    """
    fixture = staged_runner / "fixtures" / NEG_FIXTURE

    clean = _run_gate(staged_runner / COUNTERPART_GATE)
    assert clean.returncode == 0, clean.stdout + clean.stderr

    dirty = _run_gate(staged_runner / COUNTERPART_GATE, str(fixture))
    assert dirty.returncode != 0, "counterpart passed its own violation fixture"

    neg = _run_gate(staged_runner / NEG_GATE)
    assert neg.returncode == 0, neg.stdout + neg.stderr

    fixture.unlink()
    starved = _run_gate(staged_runner / NEG_GATE)
    assert starved.returncode != 0, "the control passed with its fixture removed"


def test_runner_does_not_invert_a_negative_control_gate(staged_runner: Path) -> None:
    """The ``-neg`` gates invert internally; the runner must not invert again.

    A runner that flipped a child's status would turn the calibrated
    negative controls into passes-when-broken, which is worse than leaving
    them unwired. Every real gate is uniformly exit-0-is-pass, so the
    negative control staged here must be reported PASS verbatim.
    """
    staged_negatives = sorted(staged_runner.glob("verify-*-neg.sh"))
    assert staged_negatives == [staged_runner / NEG_GATE], (
        "the sandbox holds no negative-control gate; without one this test "
        "re-runs the green baseline and cannot detect a runner that inverts "
        f"only *-neg.sh gates. found: {staged_negatives}"
    )

    result = _run(staged_runner / RUNNER.name)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"PASS: {NEG_GATE}" in result.stdout
    assert f"FAIL: {NEG_GATE}" not in result.stdout
    assert f"Passed:     {MIN_GATES}" in result.stdout
    assert "Failed:     0" in result.stdout


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
