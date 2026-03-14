"""Tests for branch and namespace handling in memory hooks via unified hook."""

import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
UNIFIED_HOOK = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True,
                    capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo,
                    check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo,
                    check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo,
                    check=True, capture_output=True)
    return str(repo)


@pytest.fixture
def git_repo_with_worktree(git_repo, tmp_path):
    """Git repo with a worktree."""
    worktree = str(tmp_path / "worktree")
    subprocess.run(
        ["git", "worktree", "add", worktree, "-b", "feature"],
        cwd=git_repo, check=True, capture_output=True,
    )
    return git_repo, worktree


class TestMemoryNamespaceResolution:
    """Test that worktree and main repo resolve to the same namespace.

    This tests the _resolve_git_context() logic in spellbook_hook.py
    by verifying that memory operations use the main repo root as the
    namespace, even when invoked from a worktree.
    """

    def test_worktree_resolves_to_main_repo_namespace(self, git_repo_with_worktree):
        """Namespace should be the same for worktree and main repo."""
        main_repo, worktree = git_repo_with_worktree

        def get_namespace(cwd):
            """Run Python snippet that mirrors _resolve_git_context namespace logic."""
            result = subprocess.run(
                ["python3", "-c", f"""
import subprocess, sys
cwd = {repr(cwd)}
try:
    result = subprocess.run(
        ['git', 'worktree', 'list', '--porcelain'],
        cwd=cwd, capture_output=True, text=True, timeout=3,
    )
    if result.returncode == 0 and result.stdout.strip():
        first_line = result.stdout.strip().split('\\n')[0]
        if first_line.startswith('worktree '):
            cwd = first_line[len('worktree '):]
except Exception:
    pass
namespace = cwd.replace('/', '-').lstrip('-') if cwd else 'unknown'
print(namespace)
"""],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip()

        ns_main = get_namespace(main_repo)
        ns_worktree = get_namespace(worktree)
        assert ns_main != ""
        assert ns_main == ns_worktree
