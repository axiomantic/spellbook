"""Tests for path_utils: detect_git_context."""

import subprocess

import tripwire
import pytest

from spellbook.core.path_utils import detect_git_context


class TestDetectGitContext:
    @pytest.mark.allow("subprocess")
    def test_in_git_repo_on_branch(self, tmp_path):
        """Real git repo, detect branch name."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=repo, capture_output=True, check=True,
            env={**dict(__import__("os").environ), "GIT_AUTHOR_NAME": "Test",
                 "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "Test",
                 "GIT_COMMITTER_EMAIL": "t@t"},
        )

        ctx = detect_git_context(str(repo))
        # Default branch varies by git config; just check it's a non-empty string
        assert ctx.branch is not None
        assert len(ctx.branch) > 0
        assert ctx.is_worktree is False
        assert ctx.worktree_name is None

    def test_git_not_available(self):
        """FileNotFoundError from subprocess -> graceful fallback."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            raises=FileNotFoundError("git not found"),
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="", stderr="",
        )

    def test_git_timeout(self):
        """TimeoutExpired from subprocess -> graceful fallback."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            raises=subprocess.TimeoutExpired(cmd="git", timeout=5),
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="", stderr="",
        )

    def test_not_a_git_repo(self):
        """Non-zero returncode -> graceful fallback."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        tripwire.subprocess.mock_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=128,
            stderr="fatal: not a git repository",
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )
        tripwire.subprocess.assert_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )

    def test_detached_head_returns_short_hash(self):
        """Detached HEAD -> branch is short commit hash, not literal 'HEAD'."""
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="HEAD\n",
        )
        tripwire.subprocess.mock_run(
            command=["git", "rev-parse", "--short", "HEAD"],
            stdout="abc1234\n",
        )
        tripwire.subprocess.mock_run(
            command=["git", "worktree", "list", "--porcelain"],
            stdout="worktree /tmp/nope\nHEAD abc1234567890\nbranch refs/heads/main\n\n",
        )

        with tripwire:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch == "abc1234"
        assert ctx.is_worktree is False
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="HEAD\n", stderr="",
        )
        tripwire.subprocess.assert_run(
            command=["git", "rev-parse", "--short", "HEAD"],
            returncode=0, stdout="abc1234\n", stderr="",
        )
        tripwire.subprocess.assert_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=0,
            stdout="worktree /tmp/nope\nHEAD abc1234567890\nbranch refs/heads/main\n\n",
            stderr="",
        )
