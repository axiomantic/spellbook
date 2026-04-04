"""Tests for path_utils: slugify_alias, derive_messaging_alias, detect_git_context."""

import hashlib
import re

import bigfoot
import pytest

from spellbook.core.path_utils import (
    slugify_alias,
    derive_messaging_alias,
    GitContext,
    MAX_ALIAS_BASE,
    HASH_LEN,
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
