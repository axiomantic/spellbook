"""The shell integration harness must exit non-zero when an assertion fails.

The defect this guards: every ``assert_*`` helper in ``test-helpers.sh``
returns 1 on failure, but no caller collected the return value, and each
test script ended with a bare ``echo``. A script's exit status was
therefore that echo's -- always 0. ``run-all-tests.sh`` branches on the
child's status, so it counted FILES RUN rather than assertions, printed
``Failed: 0`` beside visible ``x`` lines, and exited 0. The
``shell-integration-tests`` CI job reported green unconditionally from the
harness's first commit onward.

A test that only ran the suite against the real repository would pass
whether or not the accumulator exists, so it would reproduce the original
silence. Instead the suite is staged into a sandbox that reproduces the
repository layout the scripts read, asserted GREEN there, then given one
deliberately false assertion and asserted RED. Only the green-to-red
transition proves the exit status tracks assertions.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

# The harness under test is a POSIX shell suite; CI runs shell-integration-tests
# on ubuntu only. On Windows `bash` resolves to the WSL stub, which reports no
# installed distribution rather than running anything.
pytestmark = pytest.mark.posix_only


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_DIR = REPO_ROOT / "tests" / "claude-code"
RUNNER = HARNESS_DIR / "run-all-tests.sh"

# Repository paths the harness's assertions read. The sandbox links these
# back to the real tree so the staged copy has a genuine green baseline.
_FIXTURE_PATHS = (".version", "CHANGELOG.md", ".claude-plugin", ".codex")


def _stage(tmp_path: Path) -> Path:
    """Copy the harness into ``tmp_path`` laid out as the scripts expect.

    The scripts derive ``REPO_ROOT`` as ``<script dir>/../..``, so the copy
    must sit at ``tests/claude-code`` for the linked fixtures to resolve.
    """
    staged = tmp_path / "tests" / "claude-code"
    staged.parent.mkdir(parents=True)
    shutil.copytree(HARNESS_DIR, staged)
    for name in _FIXTURE_PATHS:
        (tmp_path / name).symlink_to(REPO_ROOT / name)
    return staged


_EXIT_LINE = "exit $((failures > 0))"


def _plant_failure(script: Path, assertion: str) -> None:
    """Insert a failing assertion ahead of the script's exit line.

    Appending would place the plant after ``exit`` and never run it -- a
    test that passes for the wrong reason.
    """
    text = script.read_text(encoding="utf-8")
    assert _EXIT_LINE in text, f"{script.name} has no exit line to plant before"
    plant = f"{assertion} || failures=$((failures + 1))\n\n{_EXIT_LINE}"
    script.write_text(text.replace(_EXIT_LINE, plant, 1), encoding="utf-8")


def _run(runner: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(runner)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def staged_harness(tmp_path: Path) -> Path:
    return _stage(tmp_path)


def test_staged_harness_is_green(staged_harness: Path) -> None:
    """The sandbox baseline must pass, or the red case proves nothing."""
    result = _run(staged_harness / "run-all-tests.sh")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Failed: 0" in result.stdout


def test_failed_assertion_fails_the_suite(staged_harness: Path) -> None:
    _plant_failure(
        staged_harness / "test-version.sh",
        'assert_file_exists "$REPO_ROOT/no-such-file" "planted failure"',
    )

    result = _run(staged_harness / "run-all-tests.sh")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "planted failure" in result.stdout
    assert "Failed: 1" in result.stdout


def test_runner_reports_no_stale_success_banner(staged_harness: Path) -> None:
    """A failing assertion must not leave the all-passed banner behind."""
    _plant_failure(
        staged_harness / "test-bootstrap.sh",
        'assert_contains "" "planted absent token" "planted failure"',
    )

    result = _run(staged_harness / "run-all-tests.sh")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "All tests passed" not in result.stdout


def test_every_harness_script_collects_assertion_results() -> None:
    """Each script must accumulate failures and exit on the accumulator.

    Guards the shape of the original defect directly: a script that calls
    an assertion without collecting its status reintroduces the silence,
    even while the suite is green.
    """
    scripts = sorted(HARNESS_DIR.glob("test-*.sh"))
    scripts = [s for s in scripts if s.name != "test-helpers.sh"]
    assert scripts, "no harness test scripts found"

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "exit $((failures > 0))" in text, f"{script.name} lacks a failure exit"
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("assert_"):
                continue
            assert "failures=$((failures + 1))" in stripped, (
                f"{script.name}:{number} calls an assertion without "
                f"collecting its result: {stripped}"
            )
