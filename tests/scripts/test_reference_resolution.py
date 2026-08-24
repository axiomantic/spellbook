"""Every row of the reference-resolution gate must be able to fail.

A row nobody has watched fail is a claim, not a check. The defect this suite
guards is the one the gate itself was built for: a checker that reports green
because its extractor silently matched nothing. That already happened once here
-- the extension row matched only ``callTool('<name>')``, and when the last
caller of that helper was deleted the row passed over zero references while a
live ``/tool/<name>`` caller named an unregistered tool.

So each row gets two tests:

* an EXTRACTION FLOOR, asserting the row still finds at least as many
  references as were measured when it was written. A row that drops to zero
  fails loudly instead of passing vacuously.
* a RED PROOF, which plants a violation of that specific row in a scratch copy
  of the repository and asserts the row names it.

The scratch copy is built from symlinked top-level entries, so planting a
violation never touches the real tree.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

from check_reference_resolution import (
    ALLOWLIST,
    PROSE_DIRS,
    PROSE_FILES,
    PROSE_SOURCE_LABEL,
    SKIP_PARTS,
    Reference,
    build_rows,
    extract_prose_paths,
    is_allowlisted,
    iter_prose_files,
    registered_mcp_tools,
    run_row,
    tracked_files,
)

ROWS = {row.name: row for row in build_rows(REPO_ROOT)}


# ---------------------------------------------------------------------------
# Scratch repository
# ---------------------------------------------------------------------------


def _scratch_repo(tmp_path: Path, materialize: tuple[str, ...]) -> Path:
    """Build a scratch repo: every top-level entry symlinked, except ``materialize``.

    Entries named in ``materialize`` are deep-copied so a test can edit them.
    Everything else is a symlink, which keeps the copy cheap and makes it
    impossible for a test to mutate the real tree.
    """
    root = tmp_path / "repo"
    root.mkdir()
    for entry in REPO_ROOT.iterdir():
        if entry.name in {".git", "node_modules", "__pycache__", ".venv"}:
            continue
        target = root / entry.name
        if entry.name in materialize:
            if entry.is_dir():
                shutil.copytree(
                    entry,
                    target,
                    symlinks=True,
                    ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".venv"),
                )
            else:
                shutil.copy2(entry, target)
        else:
            os.symlink(entry, target)
    return root


def _targets(row_name: str, repo: Path) -> list[str]:
    """Run one row against ``repo`` and return the unresolved reference targets."""
    row = {r.name: r for r in build_rows(repo)}[row_name]
    return [ref.target for ref in run_row(repo, row).unresolved]


# ---------------------------------------------------------------------------
# Extraction floors -- the silent-no-op guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row_name", sorted(ROWS), ids=sorted(ROWS))
def test_row_extracts_at_least_its_floor(row_name):
    """An extractor that matches nothing would pass every resolution below."""
    row = ROWS[row_name]
    result = run_row(REPO_ROOT, row)
    assert result.extracted >= row.min_refs, (
        f"Row {row_name!r} extracted {result.extracted} references, below its "
        f"floor of {row.min_refs}. Either the source changed shape and the "
        f"extractor no longer matches it, or the floor is stale. A row that "
        f"extracts nothing reports a clean pass over an unchecked source."
    )


def test_no_unresolved_references_in_the_tree():
    """The gate itself: every declared reference in this repository resolves.

    This is the assertion the whole module exists to make. It is separate from
    the per-row RED proofs on purpose -- those prove the rows CAN fail, this one
    asserts the tree is currently clean.
    """
    failures = []
    for row in build_rows(REPO_ROOT):
        for ref in run_row(REPO_ROOT, row).unresolved:
            failures.append(
                f"[{row.name}] {ref.source}:{ref.lineno}: {ref.target!r} "
                f"names no {row.what}"
            )
    assert not failures, (
        f"{len(failures)} unresolved reference(s):\n  " + "\n  ".join(failures)
    )


def test_registered_mcp_tools_is_not_empty():
    """The MCP resolver's allowlist-of-truth must not silently scan to nothing."""
    assert len(registered_mcp_tools(REPO_ROOT)) >= 20


def test_every_row_has_a_red_proof():
    """A row added without a RED proof is an unwatched claim."""
    proven = {
        "workflow-scripts",
        "dependabot-directories",
        "extension-mcp-tools",
        "prose-paths",
        "prose-modules",
        "prose-skills",
        "prose-commands",
    }
    assert set(ROWS) == proven, (
        "build_rows() and the RED-proof set disagree. Add a red-proof test for "
        "the new row and list it here."
    )


# ---------------------------------------------------------------------------
# RED proofs -- one per row
# ---------------------------------------------------------------------------


def test_red_workflow_scripts(tmp_path):
    repo = _scratch_repo(tmp_path, (".github",))
    workflow = repo / ".github" / "workflows" / "lint.yml"
    workflow.write_text(
        "name: lint\non: [push]\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: uv run scripts/deleted_by_someone.py\n",
        encoding="utf-8",
    )
    assert "scripts/deleted_by_someone.py" in _targets("workflow-scripts", repo)


def test_red_dependabot_directories(tmp_path):
    repo = _scratch_repo(tmp_path, (".github",))
    config = repo / ".github" / "dependabot.yml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + '\n  - package-ecosystem: "npm"\n    directory: "/ghost-package"\n'
        '    schedule:\n      interval: "weekly"\n',
        encoding="utf-8",
    )
    assert "/ghost-package" in _targets("dependabot-directories", repo)


def test_red_extension_mcp_tools(tmp_path):
    repo = _scratch_repo(tmp_path, ("extensions",))
    planted = repo / "extensions" / "prime-agent" / "planted.ts"
    planted.write_text(
        "const a = await client.callTool('tool_that_was_deleted', {});\n"
        "const b = await fetch(`${baseUrl}/tool/bridge_tool_that_was_deleted`);\n",
        encoding="utf-8",
    )
    unresolved = _targets("extension-mcp-tools", repo)
    assert "tool_that_was_deleted" in unresolved
    assert "bridge_tool_that_was_deleted" in unresolved


def test_red_extension_mcp_tools_accepts_a_registered_name(tmp_path):
    """The row must not fail every name; a registered tool resolves."""
    repo = _scratch_repo(tmp_path, ("extensions",))
    planted = repo / "extensions" / "prime-agent" / "planted_ok.ts"
    planted.write_text(
        "const a = await client.callTool('spellbook_health_check', {});\n",
        encoding="utf-8",
    )
    assert "spellbook_health_check" not in _targets("extension-mcp-tools", repo)


def test_red_prose_paths(tmp_path):
    repo = _scratch_repo(tmp_path, ("rules",))
    planted = repo / "rules" / "99-planted.md"
    planted.write_text(
        "Run `scripts/a_script_that_does_not_exist.py` before committing.\n",
        encoding="utf-8",
    )
    assert "scripts/a_script_that_does_not_exist.py" in _targets("prose-paths", repo)


@pytest.mark.parametrize(
    "tree, planted_path",
    [
        ("patterns", "patterns/99-planted.md"),
        ("extensions", "extensions/prime-agent/99-planted.md"),
    ],
    ids=["patterns", "extensions"],
)
def test_red_prose_paths_in_a_widened_tree(tmp_path, tree, planted_path):
    """A widened tree must be able to FAIL, not merely appear in the label.

    Set equality against git proves the walker reaches the tree. This proves
    the reference it finds there travels all the way to a verdict: a filter
    added between the walk and the resolver would leave set equality intact
    while every finding in the tree vanished.
    """
    repo = _scratch_repo(tmp_path, (tree,))
    planted = repo / planted_path
    planted.write_text(
        "Run `scripts/a_script_that_does_not_exist.py` before committing.\n",
        encoding="utf-8",
    )
    assert "scripts/a_script_that_does_not_exist.py" in _targets("prose-paths", repo)


def test_red_prose_paths_resolves_skill_relative_references(tmp_path):
    """A skill naming a sibling file relatively is correct, not a violation."""
    repo = _scratch_repo(tmp_path, ("skills",))
    skill = repo / "skills" / "dedupe" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8") + "\nSee `references/safety-markers.md`.\n",
        encoding="utf-8",
    )
    assert "references/safety-markers.md" not in _targets("prose-paths", repo)


def test_red_prose_modules(tmp_path):
    repo = _scratch_repo(tmp_path, ("rules",))
    planted = repo / "rules" / "99-planted.md"
    planted.write_text(
        "State lives in `spellbook.core.module_that_was_deleted`.\n"
        "The helper is `spellbook.mcp.tools.config.function_that_was_deleted`.\n",
        encoding="utf-8",
    )
    unresolved = _targets("prose-modules", repo)
    assert "spellbook.core.module_that_was_deleted" in unresolved
    assert "spellbook.mcp.tools.config.function_that_was_deleted" in unresolved


def test_red_prose_skills(tmp_path):
    repo = _scratch_repo(tmp_path, ("rules",))
    planted = repo / "rules" / "99-planted.md"
    planted.write_text("Load `skills/a-skill-that-was-deleted` first.\n", encoding="utf-8")
    assert "a-skill-that-was-deleted" in _targets("prose-skills", repo)


def test_red_prose_commands(tmp_path):
    repo = _scratch_repo(tmp_path, ("rules",))
    planted = repo / "rules" / "99-planted.md"
    planted.write_text("Invoke `/a-command-that-was-deleted` to start.\n", encoding="utf-8")
    assert "a-command-that-was-deleted" in _targets("prose-commands", repo)


def test_red_prose_commands_accepts_commands_and_skills(tmp_path):
    """Both command shapes and a skill name resolve; the row is not a blanket fail."""
    repo = _scratch_repo(tmp_path, ("rules",))
    planted = repo / "rules" / "99-planted.md"
    planted.write_text(
        "Use `/verify`, then `/systematic-debugging`, then `/develop`.\n",
        encoding="utf-8",
    )
    unresolved = _targets("prose-commands", repo)
    for name in ("verify", "systematic-debugging", "develop"):
        assert name not in unresolved


# ---------------------------------------------------------------------------
# Row labels must describe the source actually scanned
# ---------------------------------------------------------------------------


PROSE_ROWS = ("prose-paths", "prose-modules", "prose-skills", "prose-commands")


@pytest.mark.parametrize("row_name", PROSE_ROWS)
def test_prose_row_label_matches_the_scanned_source(row_name):
    """A hardcoded label misreports the moment the scanned set changes.

    The label is what a reader sees beside a count, so a stale one turns a
    widened scan into a false statement about what was checked. This was
    OBSERVED: the four-tree label printed unchanged beside a nine-tree scan.

    Not subsumed by the identity test below. Identity pins every row to the
    same object; it says nothing about whether that object is right. Build
    PROSE_SOURCE_LABEL with the wrong separator, or from PROSE_DIRS alone
    with PROSE_FILES dropped, and every identity assertion still holds while
    this one -- which recomputes the label independently -- is the only thing
    that fails.
    """
    expected = ", ".join(
        [f"{d}/" for d in PROSE_DIRS] + [str(f) for f in PROSE_FILES]
    )
    assert ROWS[row_name].source == expected, (
        f"Row {row_name!r} labels its source {ROWS[row_name].source!r}, but it "
        f"scans {expected!r}. The label is duplicated data, not derived data, "
        f"so it can misreport what was checked."
    )


@pytest.mark.parametrize("row_name", PROSE_ROWS)
def test_prose_row_label_is_derived_not_copied(row_name):
    """Equality today is not derivation; a copy that matches still rots.

    PROSE_SOURCE_LABEL is built at import time by ``join``, so it is not an
    interned literal. A hardcoded label that happens to read the same is a
    DIFFERENT object, and that is exactly the state this pins against: the
    copy stays put while PROSE_DIRS moves underneath it.
    """
    assert ROWS[row_name].source is PROSE_SOURCE_LABEL, (
        f"Row {row_name!r} carries its own copy of the source label instead of "
        f"PROSE_SOURCE_LABEL. It reads correctly now and will not when "
        f"PROSE_DIRS changes."
    )


def test_prose_row_label_names_every_scanned_dir():
    """Derivation, not just equality: every scanned tree appears in the label."""
    for row_name in PROSE_ROWS:
        label = ROWS[row_name].source
        for d in PROSE_DIRS:
            assert f"{d}/" in label, (
                f"Row {row_name!r} scans {d}/ but its label {label!r} omits it."
            )
        for f in PROSE_FILES:
            assert str(f) in label, (
                f"Row {row_name!r} scans {f} but its label {label!r} omits it."
            )


# ---------------------------------------------------------------------------
# Allowlist discipline
# ---------------------------------------------------------------------------


def test_allowlist_entries_are_content_anchored():
    """A path-only entry suppresses a whole file and can widen silently."""
    for row_name, entries in ALLOWLIST.items():
        for entry in entries:
            assert entry.anchor, (
                f"Allowlist entry for row {row_name!r} on {entry.path_glob!r} has "
                "no content anchor. Anchor it on the text that makes it legitimate."
            )
            assert entry.reason, f"Allowlist entry {entry.path_glob!r} has no reason."


def test_allowlist_anchors_are_not_line_numbers():
    """Line numbers rot as files shift; anchors must be content."""
    for entries in ALLOWLIST.values():
        for entry in entries:
            assert not entry.anchor.strip().isdigit()


def test_allowlist_does_not_suppress_a_differently_worded_line():
    """The anchor must bind to content, so a real regression nearby still fails."""
    entry_row = "prose-commands"
    legitimate = Reference(
        source="AGENTS.md", lineno=1, target="mcp", line="comment `/mcp` on a PR"
    )
    regression = Reference(
        source="AGENTS.md", lineno=1, target="mcp", line="run `/mcp-deleted` now"
    )
    assert is_allowlisted(entry_row, legitimate) is not None
    assert is_allowlisted(entry_row, regression) is None


def test_every_allowlist_entry_still_suppresses_something():
    """A stale entry is dead weight that hides the allowlist's real size."""
    unused = []
    for row_name, entries in ALLOWLIST.items():
        row = ROWS[row_name]
        refs = row.extract(REPO_ROOT)
        for entry in entries:
            if not any(
                not row.resolve(REPO_ROOT, ref) and is_allowlisted(row_name, ref) is entry
                for ref in refs
            ):
                unused.append(f"{row_name}: {entry.path_glob} :: {entry.anchor}")
    assert not unused, "Allowlist entries that suppress nothing:\n  " + "\n  ".join(unused)


# ---------------------------------------------------------------------------
# The scanned population is the COMMITTED repository
# ---------------------------------------------------------------------------


def _git_repo(tmp_path: Path) -> Path:
    """A real one-commit git repository carrying one tracked prose file."""
    root = tmp_path / "gitrepo"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "10-tracked.md").write_text(
        "Run `scripts/ghost_tracked.py` first.\n", encoding="utf-8"
    )
    for argv in (
        ["init", "-q"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
        ["add", "rules/10-tracked.md"],
        ["commit", "-qm", "init"],
    ):
        subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True)
    return root


def test_untracked_file_on_disk_is_not_scanned(tmp_path):
    """Generated and vendored files sit on a developer's disk, not in the repo.

    A gate whose population is "whatever is on this disk" reports findings that
    exist for one developer and not for CI. The population is the committed
    repository.
    """
    root = _git_repo(tmp_path)
    (root / "rules" / "20-untracked.md").write_text(
        "Run `scripts/ghost_untracked.py` first.\n", encoding="utf-8"
    )

    targets = [ref.target for ref in extract_prose_paths(root)]

    assert "scripts/ghost_tracked.py" in targets, (
        "the tracked file must still be scanned; a filter that scans nothing "
        "passes vacuously"
    )
    assert "scripts/ghost_untracked.py" not in targets


def test_prose_scan_covers_every_file_when_tracked_ness_is_unknowable(tmp_path):
    """Outside a git checkout the filter must widen, never narrow.

    A tarball export, or the symlinked scratch repos below, have no index to
    ask. Scanning everything is the conservative direction: it can only find
    more, never silently fewer.
    """
    root = tmp_path / "notarepo"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "10-loose.md").write_text(
        "Run `scripts/ghost_loose.py` first.\n", encoding="utf-8"
    )

    targets = [ref.target for ref in extract_prose_paths(root)]

    assert "scripts/ghost_loose.py" in targets


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True
    )


def test_tracked_files_widens_under_a_directory_nested_in_another_checkout(tmp_path):
    """An untracked subdirectory of a checkout is not that checkout's root.

    ``git ls-files`` run there exits 0 and prints NOTHING, which is
    indistinguishable, by exit code alone, from a checkout that tracks no
    files. Trusting the exit code makes the verdict depend on where the scan
    root happens to sit relative to other checkouts -- a pytest ``tmp_path``
    under ``--basetemp`` inside a checkout reaches this, and every scratch-repo
    proof in this file breaks there. Widening is the documented direction.
    """
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init")
    (outer / "tracked.md").write_text("real\n", encoding="utf-8")
    _git(outer, "add", "tracked.md")
    _git(outer, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init")

    nested = outer / "nested"
    (nested / "rules").mkdir(parents=True)
    (nested / "rules" / "10-loose.md").write_text(
        "Run `scripts/ghost_nested.py` first.\n", encoding="utf-8"
    )

    assert _git(nested, "ls-files", "--cached").stdout == b""
    assert tracked_files(nested) is None
    assert "scripts/ghost_nested.py" in [ref.target for ref in extract_prose_paths(nested)]


def test_tracked_files_still_raises_for_a_checkout_root_tracking_nothing(tmp_path):
    """The empty-list guard keeps the case it was written for.

    A genuine checkout root -- ``rev-parse --show-toplevel`` IS this directory
    -- that tracks no files is not a state this gate can run against, and must
    stay loud. That is what separates it from the nested case above.
    """
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init")

    with pytest.raises(RuntimeError, match="tracks no files"):
        tracked_files(root)


# ---------------------------------------------------------------------------
# The scanned trees, and that the walker actually reaches each one
# ---------------------------------------------------------------------------


def test_prose_dirs_covers_every_authored_prose_tree():
    """Naming the trees explicitly, so a widening or a narrowing is a decision.

    ``patterns/`` and ``extensions/`` hold authored prose that names this
    repository's own files by backticked path, and nothing else checked those
    references. Their absence was drift, not a decision.
    """
    assert set(PROSE_DIRS) == {
        "skills",
        "commands",
        "agents",
        "rules",
        "patterns",
        "extensions",
    }


@pytest.mark.parametrize("tree", sorted(PROSE_DIRS), ids=sorted(PROSE_DIRS))
def test_prose_scan_yields_every_tracked_markdown_under_each_tree(tree):
    """A tree named in PROSE_DIRS that the walker never reaches scans nothing.

    Adding a name to PROSE_DIRS is not evidence that the tree is scanned: every
    existing assertion -- the floors, the labels, the clean-tree gate -- still
    passes over a tree the enumerator silently skips. Set equality against what
    git tracks is what forces the widening to be real.
    """
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--cached", "--", tree],
        capture_output=True,
        check=True,
    )
    tracked = {
        name
        for name in completed.stdout.decode("utf-8").split("\0")
        if name.endswith(".md") and not (SKIP_PARTS & set(Path(name).parts))
    }
    assert tracked, f"git tracks no Markdown under {tree}/; the assertion is vacuous"

    scanned = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in iter_prose_files(REPO_ROOT)
        if path.relative_to(REPO_ROOT).parts[0] == tree
    }
    assert scanned == tracked
