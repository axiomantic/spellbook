"""The generated docs/ mirror must match its sources.

docs/ is produced by scripts/generate_docs.py from skills/, commands/,
agents/, and rules/. Nothing enforced freshness, so a source edit could
land while the mirror kept describing the previous version -- the same
"artifact changed, consumer did not follow" shape this suite guards
against.

Working-tree safety: this test never writes to the repository. It shells
out to ``generate_docs.py --check``, which renders every page IN MEMORY
and compares against disk. To keep that a mechanism rather than a
promise, the tests snapshot every entry under a docs tree -- files with
(size, mtime_ns) and directories by existence -- before and after the
run, and assert the snapshot is unchanged.

A snapshot of the repo's own docs/ cannot catch a regression on its own:
the tree is already current, so the write path would rewrite identical
bytes and ``write_if_changed`` would no-op. The teeth come from
``test_check_writes_nothing_against_a_stale_tree``, which runs --check
against a copy whose docs/ has been made deliberately stale, so the
write path WOULD change bytes and create directories.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_docs.py"
DOCS_DIR = REPO_ROOT / "docs"
SOURCE_DIRS = ("scripts", "skills", "commands", "agents", "rules", "docs")


def _snapshot(docs_dir: Path = DOCS_DIR) -> dict[str, tuple[str, int, int]]:
    """Record every entry under ``docs_dir``, directories included.

    Directories are recorded because the write path calls ``mkdir`` before
    writing; a file-only snapshot cannot see a directory the run created.
    """
    snapshot: dict[str, tuple[str, int, int]] = {}
    for path in sorted(docs_dir.rglob("*")):
        rel = str(path.relative_to(docs_dir))
        if path.is_dir():
            snapshot[rel] = ("dir", 0, 0)
        else:
            stat = path.stat()
            snapshot[rel] = ("file", stat.st_size, stat.st_mtime_ns)
    return snapshot


def _scratch_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for name in SOURCE_DIRS:
        shutil.copytree(REPO_ROOT / name, root / name)
    return root


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


def test_check_writes_nothing_against_a_stale_tree(tmp_path):
    """--check against a tree the write path WOULD change must still not write.

    The scratch tree is made stale two ways, one per failure mode a
    file-only snapshot of an already-current tree misses: a page whose
    bytes differ (so ``write_if_changed`` would write) and a missing
    output directory (so the write path would ``mkdir`` it).
    """
    root = _scratch_repo(tmp_path)
    docs = root / "docs"
    shutil.rmtree(docs / "rules")
    (docs / "commands" / "handoff.md").write_text("stale\n", encoding="utf-8")

    before = _snapshot(docs)
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "generate_docs.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=300,
    )
    after = _snapshot(docs)

    assert after == before, (
        "generate_docs.py --check wrote to a stale tree; it must only read\n"
        f"added: {sorted(set(after) - set(before))[:10]}\n"
        f"removed: {sorted(set(before) - set(after))[:10]}"
    )
    assert result.returncode == 1, (
        f"--check must report a stale tree as failure\n{result.stdout}{result.stderr}"
    )
    assert "Stale or missing generated page(s)" in result.stdout


def test_check_reports_orphan_pages_and_writes_nothing(tmp_path):
    """A page whose source is gone must be reported, not silently kept.

    The generator only ever wrote pages, so deleting a skill left its
    page in docs/ forever. --check was blind to it by construction: it
    compared rendered pages against disk and never asked the reverse
    question.
    """
    root = _scratch_repo(tmp_path)
    docs = root / "docs"
    orphan = docs / "skills" / "ghost-skill.md"
    orphan.write_text("# ghost\n", encoding="utf-8")

    before = _snapshot(docs)
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "generate_docs.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=300,
    )
    after = _snapshot(docs)

    assert after == before, "--check removed an orphan; it must only read"
    assert result.returncode == 1, (
        f"--check must report an orphan page as failure\n{result.stdout}{result.stderr}"
    )
    assert "skills/ghost-skill.md" in result.stdout, result.stdout


def test_write_run_prunes_orphans_but_keeps_hand_authored_pages(tmp_path):
    """Pruning is confined to the generated subtrees.

    docs/ also holds hand-authored pages. docs/skills/index.md sits
    INSIDE a generated subtree and is not generated, so a prune keyed
    only on "not produced by this run" would delete real documentation.
    """
    root = _scratch_repo(tmp_path)
    docs = root / "docs"
    orphans = [
        docs / "skills" / "ghost-skill.md",
        docs / "commands" / "ghost-command.md",
        docs / "agents" / "ghost-agent.md",
        docs / "rules" / "99-ghost.md",
    ]
    for path in orphans:
        path.write_text("# ghost\n", encoding="utf-8")

    survivors = [
        docs / "skills" / "index.md",
        docs / "windows-support-report.md",
        docs / "index.md",
    ]
    for path in survivors:
        assert path.exists(), f"fixture expects {path} to exist in the source tree"

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "generate_docs.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=300,
    )

    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    for path in orphans:
        assert not path.exists(), f"orphan survived the prune: {path}"
    for path in survivors:
        assert path.exists(), f"prune deleted a hand-authored page: {path}"

    recheck = subprocess.run(
        [sys.executable, str(root / "scripts" / "generate_docs.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=300,
    )
    assert recheck.returncode == 0, f"{recheck.stdout}{recheck.stderr}"


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
