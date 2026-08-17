"""The generated docs/ mirror must match its sources.

docs/ is produced by scripts/generate_docs.py from skills/, commands/,
agents/, and rules/. Nothing enforced freshness, so a source edit could
land while the mirror kept describing the previous version -- the same
"artifact changed, consumer did not follow" shape this suite guards
against, here at ~740 lines of drift.

Working-tree safety: this test never writes. It shells out to
``generate_docs.py --check``, which renders every page IN MEMORY and
compares against disk. To keep that a mechanism rather than a promise,
the test snapshots (size, mtime_ns) of every file under docs/ before and
after the run and asserts the snapshot is unchanged -- so a future
regression that makes --check write is caught here instead of in a
developer's tree.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_docs.py"
DOCS_DIR = REPO_ROOT / "docs"


def _snapshot() -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(REPO_ROOT)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(DOCS_DIR.rglob("*"))
        if p.is_file()
    }


def test_generated_docs_mirror_is_current():
    before = _snapshot()
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=300,
    )
    after = _snapshot()

    assert after == before, (
        "generate_docs.py --check modified the working tree; it must only read"
    )
    assert result.returncode == 0, (
        "the generated docs/ mirror is stale. Run: python3 scripts/generate_docs.py\n"
        f"{result.stdout}{result.stderr}"
    )


def test_check_mode_reports_staleness_and_help_writes_nothing():
    """--help must not regenerate anything.

    With no argument parser at all, `generate_docs.py --help` silently
    ignored the flag and rewrote every page. This pins the fixed
    behavior: usage on stdout, exit 0, tree untouched.
    """
    before = _snapshot()
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    after = _snapshot()

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "--check" in result.stdout
    assert after == before, "generate_docs.py --help modified the working tree"
