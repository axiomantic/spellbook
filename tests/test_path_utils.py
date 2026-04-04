"""Tests for path_utils: slugify_alias, derive_messaging_alias, detect_git_context."""

import re
import subprocess

import bigfoot
import pytest

from spellbook.core.path_utils import (
    slugify_alias,
    derive_messaging_alias,
    detect_git_context,
    GitContext,
    MAX_ALIAS_BASE,
)


class TestSlugifyAlias:
    def test_slash_replaced_with_hyphen(self):
        assert slugify_alias("feature/add-auth") == "feature-add-auth"

    def test_uppercase_lowered(self):
        assert slugify_alias("elijahr/ODY-1234") == "elijahr-ody-1234"

    def test_head_string(self):
        assert slugify_alias("HEAD") == "head"

    def test_underscores_preserved(self):
        assert slugify_alias("UPPER_case") == "upper_case"

    def test_consecutive_hyphens_collapsed(self):
        assert slugify_alias("a//b///c") == "a-b-c"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify_alias("///weird///chars///") == "weird-chars"

    def test_empty_string_returns_session(self):
        assert slugify_alias("") == "session"

    def test_all_hyphens_returns_session(self):
        assert slugify_alias("---") == "session"

    def test_all_invalid_chars_returns_session(self):
        assert slugify_alias("@#$%^&*()") == "session"

    def test_normal_string_unchanged(self):
        assert slugify_alias("my-project") == "my-project"

    def test_digits_preserved(self):
        assert slugify_alias("v2-beta3") == "v2-beta3"

    def test_dots_replaced(self):
        assert slugify_alias("v1.2.3") == "v1-2-3"

    def test_spaces_replaced(self):
        assert slugify_alias("my project name") == "my-project-name"


class TestDeriveMessagingAlias:
    def test_explicit_session_name_takes_priority(self):
        # No mock for resolve_repo_root: it should NOT be called
        ctx = GitContext(branch="main")
        result = derive_messaging_alias(
            "/tmp/myrepo", session_name="my-custom-name", git_context=ctx
        )
        assert result == "my-custom-name"

    def test_explicit_session_name_slugified(self):
        # No mock needed: session_name path doesn't call resolve_repo_root
        result = derive_messaging_alias(
            "/tmp/myrepo", session_name="My Custom/Name"
        )
        assert result == "my-custom-name"

    def test_git_branch_with_project_basename(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo")

        ctx = GitContext(branch="main")
        with bigfoot:
            result = derive_messaging_alias("/tmp/myrepo", git_context=ctx)
        assert result == "myrepo-main"
        mock_resolve.assert_call(args=("/tmp/myrepo",))

    def test_worktree_name_preferred_over_branch(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo")

        ctx = GitContext(branch="feature/auth", worktree_name="auth-worktree", is_worktree=True)
        with bigfoot:
            result = derive_messaging_alias("/tmp/myrepo", git_context=ctx)
        assert result == "myrepo-auth-worktree"
        mock_resolve.assert_call(args=("/tmp/myrepo",))

    def test_no_git_context_uses_basename(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo")

        with bigfoot:
            result = derive_messaging_alias("/tmp/myrepo", git_context=None)
        assert result == "myrepo"
        mock_resolve.assert_call(args=("/tmp/myrepo",))

    def test_git_context_all_none_uses_basename(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo")

        ctx = GitContext(branch=None, worktree_name=None, is_worktree=False)
        with bigfoot:
            result = derive_messaging_alias("/tmp/myrepo", git_context=ctx)
        assert result == "myrepo"
        mock_resolve.assert_call(args=("/tmp/myrepo",))

    def test_truncation_with_hash_for_long_names(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo")

        long_branch = "a" * 100
        ctx = GitContext(branch=long_branch)
        with bigfoot:
            result = derive_messaging_alias("/tmp/myrepo", git_context=ctx)
        assert len(result) <= MAX_ALIAS_BASE
        assert re.fullmatch(r"[a-z0-9_-]+", result)
        mock_resolve.assert_call(args=("/tmp/myrepo",))

    def test_truncation_preserves_determinism(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo").returns("/tmp/myrepo")

        long_branch = "a" * 100
        ctx = GitContext(branch=long_branch)
        with bigfoot:
            r1 = derive_messaging_alias("/tmp/myrepo", git_context=ctx)
            r2 = derive_messaging_alias("/tmp/myrepo", git_context=ctx)
        assert r1 == r2
        mock_resolve.assert_call(args=("/tmp/myrepo",))
        mock_resolve.assert_call(args=("/tmp/myrepo",))

    def test_fallback_to_session_when_path_is_root(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/")

        with bigfoot:
            result = derive_messaging_alias("/")
        # os.path.basename("/") is "", slugify("") -> "session"
        assert result == "session"
        mock_resolve.assert_call(args=("/",))

    def test_session_name_empty_string_ignored(self):
        mock_resolve = bigfoot.mock("spellbook.core.path_utils:resolve_repo_root")
        mock_resolve.returns("/tmp/myrepo")

        ctx = GitContext(branch="dev")
        with bigfoot:
            result = derive_messaging_alias("/tmp/myrepo", session_name="", git_context=ctx)
        assert result == "myrepo-dev"
        mock_resolve.assert_call(args=("/tmp/myrepo",))


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
        bigfoot.subprocess_mock.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            raises=FileNotFoundError("git not found"),
        )

        with bigfoot:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        bigfoot.subprocess_mock.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="", stderr="",
        )

    def test_git_timeout(self):
        """TimeoutExpired from subprocess -> graceful fallback."""
        bigfoot.subprocess_mock.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            raises=subprocess.TimeoutExpired(cmd="git", timeout=5),
        )

        with bigfoot:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        bigfoot.subprocess_mock.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="", stderr="",
        )

    def test_not_a_git_repo(self):
        """Non-zero returncode -> graceful fallback."""
        bigfoot.subprocess_mock.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        bigfoot.subprocess_mock.mock_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=128,
            stderr="fatal: not a git repository",
        )

        with bigfoot:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch is None
        assert ctx.worktree_name is None
        assert ctx.is_worktree is False
        bigfoot.subprocess_mock.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )
        bigfoot.subprocess_mock.assert_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )

    def test_detached_head_returns_short_hash(self):
        """Detached HEAD -> branch is short commit hash, not literal 'HEAD'."""
        bigfoot.subprocess_mock.mock_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="HEAD\n",
        )
        bigfoot.subprocess_mock.mock_run(
            command=["git", "rev-parse", "--short", "HEAD"],
            stdout="abc1234\n",
        )
        bigfoot.subprocess_mock.mock_run(
            command=["git", "worktree", "list", "--porcelain"],
            stdout="worktree /tmp/nope\nHEAD abc1234567890\nbranch refs/heads/main\n\n",
        )

        with bigfoot:
            ctx = detect_git_context("/tmp/nope")
        assert ctx.branch == "abc1234"
        assert ctx.is_worktree is False
        bigfoot.subprocess_mock.assert_run(
            command=["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=0, stdout="HEAD\n", stderr="",
        )
        bigfoot.subprocess_mock.assert_run(
            command=["git", "rev-parse", "--short", "HEAD"],
            returncode=0, stdout="abc1234\n", stderr="",
        )
        bigfoot.subprocess_mock.assert_run(
            command=["git", "worktree", "list", "--porcelain"],
            returncode=0,
            stdout="worktree /tmp/nope\nHEAD abc1234567890\nbranch refs/heads/main\n\n",
            stderr="",
        )
