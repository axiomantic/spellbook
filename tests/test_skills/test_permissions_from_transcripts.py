"""Tests for the ``permissions-from-transcripts`` skill.

Asserts:

* ``skills/permissions-from-transcripts/SKILL.md`` exists with valid YAML
  frontmatter (``name`` + ``description``).
* The CLI script honors ``--dry-run`` (does NOT write the proposal JSON).
* The script and skill reuse the SAME classification module
  (``spellbook.gates.transcript_analyzer``) - no duplicate ``CATEGORY_*``
  constants live in the script.
* Per-subcommand classification regression tests for the Step 3.5
  multi-word CLI tightening (``gh pr view`` is read-only,
  ``gh pr create`` rejects, plus a second pair from a different runner).
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "permissions-from-transcripts" / "SKILL.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze_yolo_transcripts.py"


def _load_script_module():
    """Load the CLI script as a module for invocation tests."""
    spec = importlib.util.spec_from_file_location("analyze_yolo_transcripts", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_yolo_transcripts"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script_module()


# ---------------------------------------------------------------------------
# SKILL.md presence + frontmatter
# ---------------------------------------------------------------------------


def test_skill_file_exists():
    assert SKILL_PATH.exists(), f"SKILL.md missing at {SKILL_PATH}"


def test_skill_frontmatter_parses():
    """SKILL.md must open with a YAML frontmatter block carrying ``name`` and ``description``."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with '---' frontmatter delimiter"
    closing = text.find("\n---", 4)
    assert closing != -1, "SKILL.md frontmatter must terminate with '---'"
    frontmatter_raw = text[4:closing]
    data = yaml.safe_load(frontmatter_raw)
    assert isinstance(data, dict), "Frontmatter must parse to a mapping"
    assert data.get("name") == "permissions-from-transcripts"
    description = data.get("description", "")
    assert isinstance(description, str) and description.strip(), "description must be non-empty"
    # Trigger phrasings called out by the plan / orchestrator must surface
    # in the description so the dispatcher matches user intent.
    lower = description.lower()
    assert "transcripts" in lower
    assert "allow" in lower


# ---------------------------------------------------------------------------
# Dry-run never writes the proposal file
# ---------------------------------------------------------------------------


def test_dry_run_does_not_write_proposal(script, tmp_path, capsys):
    """``--dry-run`` must skip writing the proposal JSON, even when --output points at a file."""
    output = tmp_path / "proposed_allow_list.json"
    fixtures = REPO_ROOT / "tests" / "test_scripts" / "fixtures" / "yolo_transcripts"
    rc = script.main(
        [
            "--days",
            "3650",  # large window so the fixture is in-range
            "--config-dir",
            str(fixtures),
            "--output",
            str(output),
            "--dry-run",
        ]
    )
    assert rc == 0
    assert not output.exists(), (
        f"--dry-run must NOT create the proposal file, but it exists at {output}"
    )
    # Sanity: the summary still went to stdout.
    captured = capsys.readouterr()
    assert "Proposed permissions.allow" in captured.out


def test_non_dry_run_writes_proposal(script, tmp_path):
    """Counterpart sanity check: without ``--dry-run`` the file is written."""
    output = tmp_path / "proposed_allow_list.json"
    fixtures = REPO_ROOT / "tests" / "test_scripts" / "fixtures" / "yolo_transcripts"
    rc = script.main(
        [
            "--days",
            "3650",
            "--config-dir",
            str(fixtures),
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    assert output.exists(), "non-dry-run invocation must produce the proposal file"


# ---------------------------------------------------------------------------
# Single source of truth: classification lives in the gates library only.
# ---------------------------------------------------------------------------


def test_script_imports_classification_from_library(script):
    """The script's classification constants must be the SAME objects as the library's."""
    from spellbook.gates import transcript_analyzer as lib

    for name in (
        "READ_ONLY_SAFE",
        "SEARCH_INSPECT",
        "BUILD_TEST_IDEMPOTENT",
        "LOCAL_FILE_CACHE",
        "LOCAL_GIT_MUTATION",
        "MUTATING",
        "CATEGORY_ORDER",
        "MULTI_WORD_RUNNERS",
        "THREE_WORD_RUNNERS",
        "FOUR_WORD_RUNNERS",
        "TWO_WORD_SPECIALS",
    ):
        assert getattr(script, name) is getattr(lib, name), (
            f"{name} must be re-exported from spellbook.gates.transcript_analyzer, "
            f"not redefined inside the script."
        )

    # Same goes for the bucketing/classification functions.
    for fn in ("classify", "bucket_key", "bucket_and_classify", "extract_bash_commands"):
        assert getattr(script, fn) is getattr(lib, fn)


def test_script_does_not_redefine_category_constants():
    """Static guard: the script source must not assign any CATEGORY_* / *_RUNNERS / MUTATING constants.

    All such tables MUST live in ``spellbook.gates.transcript_analyzer``. The
    script file is allowed to bind them as imported names (via ``from ... import``)
    but never to assign new values.
    """
    forbidden_targets = {
        "READ_ONLY_SAFE",
        "SEARCH_INSPECT",
        "BUILD_TEST_IDEMPOTENT",
        "LOCAL_FILE_CACHE",
        "LOCAL_GIT_MUTATION",
        "MUTATING",
        "CATEGORY_ORDER",
        "MULTI_WORD_RUNNERS",
        "THREE_WORD_RUNNERS",
        "FOUR_WORD_RUNNERS",
        "TWO_WORD_SPECIALS",
    }
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in forbidden_targets:
                    pytest.fail(
                        f"Script reassigns '{target.id}' - this constant must be "
                        f"imported from spellbook.gates.transcript_analyzer, not "
                        f"redefined."
                    )
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id in forbidden_targets:
                pytest.fail(
                    f"Script annotates '{target.id}' as a new value - this constant "
                    f"must be imported from spellbook.gates.transcript_analyzer."
                )


# ---------------------------------------------------------------------------
# Step 3.5: per-subcommand classification regression tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected_category",
    [
        # gh pr - read-only triple
        ("gh pr view --web 123", "search_inspect"),
        # gh pr - mutating triple
        ("gh pr create --title X --body Y", "mutating"),
        # gh run - mixed pair to lock the pattern
        ("gh run list --limit 5", "search_inspect"),
        ("gh run cancel 999", "mutating"),
        # gh issue - mixed pair, distinct second-token
        ("gh issue view 42", "search_inspect"),
        ("gh issue close 42", "mutating"),
        # acli jira - four-word read vs four-word mutating
        ("acli jira workitem view PROJ-1", "search_inspect"),
        ("acli jira workitem transition PROJ-1 Done", "mutating"),
    ],
)
def test_per_subcommand_classification(command, expected_category):
    """Lock per-subcommand 3-word / 4-word classification (Step 3.5).

    Plain ``gh pr`` would resolve unclassified under WI-2's two-word
    runner, so we must classify by the 3-word triple. Same goes for
    other multi-word CLIs.
    """
    from spellbook.gates.transcript_analyzer import bucket_key, classify

    first_token, _ = bucket_key(command)
    assert classify(first_token) == expected_category, (
        f"{command!r} -> first_token={first_token!r} classified as "
        f"{classify(first_token)!r}, expected {expected_category!r}"
    )


# ---------------------------------------------------------------------------
# Cycle-5 H4: ``git worktree`` / ``git branch`` flag-blind READ_ONLY_SAFE
# ---------------------------------------------------------------------------
#
# The 2-word ``git worktree`` and ``git branch`` keys are in READ_ONLY_SAFE,
# but the underlying tool is not uniformly read-only:
#
# * ``git worktree list`` is safe; ``git worktree add path`` mutates.
# * ``git branch`` (no args / ``--list``) is safe; ``git branch -d feature``
#   deletes a local branch and ``git branch newname`` creates one.
#
# A flag-blind classifier short-circuits to ``read_only_safe`` for all of
# the above — exactly the bypass we patched. These tests lock in the
# corrected classification.


@pytest.mark.parametrize(
    "command,expected_category",
    [
        # git worktree - safe form: list (with or without flags).
        ("git worktree list", "read_only_safe"),
        ("git worktree list --porcelain", "read_only_safe"),
        # git worktree - mutating subcommands.
        ("git worktree add /tmp/x", "local_git_mutation"),
        ("git worktree add /tmp/x feature", "local_git_mutation"),
        ("git worktree remove /tmp/x", "local_git_mutation"),
        ("git worktree move /tmp/x /tmp/y", "local_git_mutation"),
        ("git worktree prune", "local_git_mutation"),
        ("git worktree repair", "local_git_mutation"),
        ("git worktree unlock /tmp/x", "local_git_mutation"),
        ("git worktree lock /tmp/x", "local_git_mutation"),
        # git branch - safe forms.
        ("git branch", "read_only_safe"),
        ("git branch --list", "read_only_safe"),
        ("git branch -a", "read_only_safe"),
        ("git branch -v", "read_only_safe"),
        # git branch - mutating short flags.
        ("git branch -d feature", "local_git_mutation"),
        ("git branch -D feature", "local_git_mutation"),
        ("git branch -m old new", "local_git_mutation"),
        ("git branch -M old new", "local_git_mutation"),
        ("git branch -c old new", "local_git_mutation"),
        ("git branch -C old new", "local_git_mutation"),
        # git branch - mutating long flags.
        ("git branch --delete feature", "local_git_mutation"),
        ("git branch --move old new", "local_git_mutation"),
        # git branch - bare positional (creates a branch).
        ("git branch newname", "local_git_mutation"),
        # Cycle-7 F4: ``--list``/``-l`` makes positional args a glob filter,
        # NOT a new branch name. Must classify as read-only.
        ("git branch --list 'feat/*'", "read_only_safe"),
        ("git branch -l 'feat/*'", "read_only_safe"),
        ("git branch --list feat/foo", "read_only_safe"),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_git_worktree_and_branch_flag_aware_classification(command, expected_category):
    """Cycle-5 H4: ``git worktree``/``git branch`` must classify per
    subcommand/flags, not as a blanket read-only form."""
    from spellbook.gates.transcript_analyzer import bucket_key, classify

    first_token, _ = bucket_key(command)
    actual = classify(first_token)
    assert actual == expected_category, (
        f"{command!r} -> first_token={first_token!r} classified as "
        f"{actual!r}, expected {expected_category!r}"
    )


def test_mutating_gh_pr_create_not_in_allow_list():
    """End-to-end: ``gh pr create`` must land in rejected_mutating, not any allow category."""
    from datetime import datetime, timezone

    from spellbook.gates.transcript_analyzer import (
        BashRecord,
        bucket_and_classify,
        render_proposed_list,
    )

    rec = BashRecord(
        command="gh pr create --title test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        session_id="s",
        is_sidechain=False,
        source_file=Path("/tmp/x.jsonl"),
    )
    categorized = bucket_and_classify([rec])
    proposal = render_proposed_list(
        categorized,
        scanned_roots=["/tmp"],
        since=datetime(2026, 1, 1, tzinfo=timezone.utc),
        days=30,
    )
    allow_patterns: set[str] = set()
    for entries in proposal["categories"].values():
        for entry in entries:
            allow_patterns.add(entry["pattern"])
    rejected_patterns = {e["pattern"] for e in proposal["rejected_mutating"]}
    assert "Bash(gh pr create:*)" not in allow_patterns
    assert "Bash(gh pr create:*)" in rejected_patterns
