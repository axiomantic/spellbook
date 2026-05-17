"""CLI-entry cwd plumbing tests for ``python -m spellbook.gates.check``.

The CLI is the entry point invoked by the OpenCode plugin and the Gemini
policy engine. Both pass the Claude Code hook-protocol JSON on stdin
(including the ``cwd`` field). Without forwarding ``cwd`` into
``check_tool_input``, the git-push pre-pass cannot resolve the current
branch and falls back to fail-safe T2 for every push -- even on feature
branches that should be silently allowed.

These tests invoke the real CLI subprocess (the system under test). The
project's tripwire firewall whitelists ``subprocess:*`` in
``pyproject.toml`` -> ``[tool.tripwire.firewall].allow``, so direct
``subprocess.run`` is permitted here without explicit mocking.

The autouse ``_reset_git_push_caches`` fixture is supplied by
``tests/test_security/conftest.py``.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)

pytestmark = pytest.mark.integration


def _make_git_repo(path: Path, branch: str = "main") -> None:
    """Build a minimal .git directory pointing HEAD at refs/heads/<branch>.

    Mirrors the helper in ``test_git_push_classifier.py`` -- duplicated
    here to keep this file independently runnable and to avoid coupling
    test modules through implicit imports.
    """
    git = path / ".git"
    git.mkdir(exist_ok=True)
    (git / "HEAD").write_text(
        f"ref: refs/heads/{branch}\n", encoding="utf-8"
    )
    refs_heads = git / "refs" / "heads"
    refs_heads.mkdir(parents=True, exist_ok=True)
    ref_file = refs_heads / branch
    ref_file.parent.mkdir(parents=True, exist_ok=True)
    ref_file.write_text("0" * 40 + "\n", encoding="utf-8")


def _run_check(payload: dict) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess with ``payload`` on stdin."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT
    # Disable any autonomous-mode bypass so the failsafe path is observable.
    env.pop("SPELLBOOK_GIT_PUSH_AUTONOMOUS", None)
    return subprocess.run(
        [sys.executable, "-m", "spellbook.gates.check"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        cwd=PROJECT_ROOT,
    )


def test_cli_forwards_cwd_protected_branch_blocks(tmp_path):
    """`git push` from protected-branch cwd -> exit 2 (T2 ask).

    Forwarding ``cwd`` lets the resolver read .git/HEAD and identify the
    branch as protected. Without forwarding, the resolver fails over to
    fail-safe T2 from a different reason -- but the externally observable
    behaviour (exit 2) is the same. The companion feature-branch test
    below is what proves the cwd actually reached the classifier.
    """
    _make_git_repo(tmp_path, branch="main")
    proc = _run_check({
        "tool_name": "Bash",
        "tool_input": {"command": "git push"},
        "cwd": str(tmp_path),
    })
    assert proc.returncode == 2, (
        f"expected exit 2 on protected-branch push, got "
        f"{proc.returncode}; stderr={proc.stderr!r}"
    )


def test_cli_forwards_cwd_feature_branch_allows(tmp_path):
    """`git push` from a feature-branch cwd -> exit 0.

    This is the load-bearing assertion: only a real cwd forwarded into
    the classifier can flip a `git push` from fail-safe T2 (exit 2) to
    silently allowed (exit 0). If the CLI ignored ``cwd`` from the
    payload, this test would exit 2.
    """
    _make_git_repo(tmp_path, branch="feature/x")
    proc = _run_check({
        "tool_name": "Bash",
        "tool_input": {"command": "git push"},
        "cwd": str(tmp_path),
    })
    assert proc.returncode == 0, (
        f"expected exit 0 on feature-branch push, got "
        f"{proc.returncode}; stderr={proc.stderr!r}"
    )


def test_cli_empty_cwd_coerced_to_none_failsafe(tmp_path):
    """Empty-string ``cwd`` -> coerced to None -> failsafe T2 (exit 2).

    Some hook surfaces emit ``cwd: ""`` rather than omitting the field.
    The CLI must treat that as "unknown directory" and trigger the
    failsafe, not pass `""` through to `classify_git_push` (which would
    silently bypass the pre-pass).
    """
    proc = _run_check({
        "tool_name": "Bash",
        "tool_input": {"command": "git push"},
        "cwd": "",
    })
    assert proc.returncode == 2, (
        f"expected exit 2 on empty-cwd push (failsafe), got "
        f"{proc.returncode}; stderr={proc.stderr!r}"
    )


def test_cli_missing_cwd_failsafe(tmp_path):
    """No ``cwd`` field at all -> failsafe T2 (exit 2).

    Backwards-compatible behaviour: pre-fix callers that don't include
    ``cwd`` in the payload still get the failsafe rather than crashing.
    """
    proc = _run_check({
        "tool_name": "Bash",
        "tool_input": {"command": "git push"},
    })
    assert proc.returncode == 2, (
        f"expected exit 2 on missing-cwd push (failsafe), got "
        f"{proc.returncode}; stderr={proc.stderr!r}"
    )
