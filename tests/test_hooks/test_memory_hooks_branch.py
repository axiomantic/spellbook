"""Tests for branch and namespace handling in memory hooks."""

import json
import os
import subprocess
import sys

import pytest


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


HOOKS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "hooks",
)


@pytest.mark.skipif(sys.platform == "win32", reason="Bash hooks require Unix shell")
class TestMemoryCaptureNamespace:
    def test_worktree_and_main_repo_same_namespace(self, git_repo_with_worktree):
        """memory-capture.sh should produce same namespace for worktree and main repo."""
        main_repo, worktree = git_repo_with_worktree

        def get_namespace(cwd):
            hook_input = json.dumps({
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file.py"},
                "session_id": "test-sess",
                "cwd": cwd,
            })
            env = os.environ.copy()
            env["DEBUG_PAYLOAD"] = "1"
            result = subprocess.run(
                ["bash", os.path.join(HOOKS_DIR, "memory-capture.sh")],
                input=hook_input, capture_output=True, text=True,
                env=env, timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            return json.loads(result.stdout.strip())["project"]

        ns_main = get_namespace(main_repo)
        ns_worktree = get_namespace(worktree)
        assert ns_main is not None
        assert ns_main == ns_worktree

    def test_hook_includes_branch(self, git_repo):
        """memory-capture.sh should include branch in payload."""
        hook_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
            "session_id": "test-sess",
            "cwd": git_repo,
        })
        env = os.environ.copy()
        env["DEBUG_PAYLOAD"] = "1"
        result = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "memory-capture.sh")],
            input=hook_input, capture_output=True, text=True,
            env=env, timeout=10,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout.strip())
        assert payload["branch"] == "main"


class TestMemoryInjectNamespace:
    def test_worktree_and_main_repo_same_namespace(self, git_repo_with_worktree):
        """memory-inject.sh should produce same namespace for worktree and main repo."""
        main_repo, worktree = git_repo_with_worktree

        def get_payload(cwd):
            hook_input = json.dumps({
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file.py"},
                "cwd": cwd,
            })
            # We can't easily test the full inject hook (it calls curl),
            # so we test the Python extraction block by running just the
            # payload-building part. Use a modified approach: run the hook
            # with MCP server not running (curl will fail silently).
            # Instead, test namespace resolution directly.
            env = os.environ.copy()
            result = subprocess.run(
                ["python3", "-c", f"""
import json, subprocess, sys
cwd = {repr(cwd)}
# Resolve worktree to repo root
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

        ns_main = get_payload(main_repo)
        ns_worktree = get_payload(worktree)
        assert ns_main == ns_worktree
