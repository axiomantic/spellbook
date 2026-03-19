"""Tests for branch ancestry module."""

import subprocess

import pytest

from spellbook.branch_ancestry import (
    BRANCH_MULTIPLIERS,
    BranchRelationship,
    clear_ancestry_cache,
    get_branch_relationship,
    get_current_branch,
    is_ancestor,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo with main and feature-x branches.

    Structure:
        init (main) --> feature commit (feature-x)
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", "feature-x"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "feature work"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=repo, check=True, capture_output=True,
    )
    clear_ancestry_cache()
    return str(repo)


@pytest.fixture
def git_repo_with_sibling(git_repo):
    """Extend git_repo with a sibling branch (no ancestry with feature-x)."""
    subprocess.run(
        ["git", "checkout", "-b", "feature-y"],
        cwd=git_repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "sibling work"],
        cwd=git_repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=git_repo, check=True, capture_output=True,
    )
    return git_repo


class TestGetCurrentBranch:
    def test_on_main_branch(self, git_repo):
        assert get_current_branch(git_repo) == "main"

    def test_on_feature_branch(self, git_repo):
        subprocess.run(
            ["git", "checkout", "feature-x"],
            cwd=git_repo, check=True, capture_output=True,
        )
        assert get_current_branch(git_repo) == "feature-x"

    def test_detached_head(self, git_repo):
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=git_repo, capture_output=True, text=True, check=True,
        )
        short_sha = result.stdout.strip()
        # Detach HEAD at current commit
        full_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo, capture_output=True, text=True, check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "checkout", full_sha],
            cwd=git_repo, check=True, capture_output=True,
        )
        assert get_current_branch(git_repo) == f"detached:{short_sha}"

    def test_no_git_repo(self, tmp_path):
        assert get_current_branch(str(tmp_path)) == ""

    def test_nonexistent_path(self):
        assert get_current_branch("/nonexistent/path/xyz") == ""


class TestIsAncestor:
    def test_main_is_ancestor_of_feature(self, git_repo):
        clear_ancestry_cache()
        assert is_ancestor(git_repo, "main", "feature-x") is True

    def test_feature_is_not_ancestor_of_main(self, git_repo):
        clear_ancestry_cache()
        assert is_ancestor(git_repo, "feature-x", "main") is False

    def test_branch_is_ancestor_of_itself(self, git_repo):
        clear_ancestry_cache()
        assert is_ancestor(git_repo, "main", "main") is True

    def test_nonexistent_branch(self, git_repo):
        clear_ancestry_cache()
        assert is_ancestor(git_repo, "nonexistent", "main") is False

    def test_cache_prevents_repeated_git_calls(self, git_repo, monkeypatch):
        clear_ancestry_cache()
        call_count = 0
        original_run = subprocess.run

        def counting_run(*args, **kwargs):
            nonlocal call_count
            if args and isinstance(args[0], list) and "merge-base" in args[0]:
                call_count += 1
            return original_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", counting_run)
        # First call: hits git
        result1 = is_ancestor(git_repo, "main", "feature-x")
        assert result1 is True
        assert call_count == 1
        # Second call: should hit cache, no additional git call
        result2 = is_ancestor(git_repo, "main", "feature-x")
        assert result2 is True
        assert call_count == 1  # No additional git call


class TestGetBranchRelationship:
    def test_same_branch(self, git_repo):
        assert get_branch_relationship(git_repo, "main", "main") == BranchRelationship.SAME

    def test_ancestor(self, git_repo):
        clear_ancestry_cache()
        # From feature-x's perspective, memory on "main" is an ANCESTOR
        # (main was merged into / is ancestor of feature-x)
        assert get_branch_relationship(
            git_repo, "feature-x", "main"
        ) == BranchRelationship.ANCESTOR

    def test_descendant(self, git_repo):
        clear_ancestry_cache()
        # From main's perspective, memory on "feature-x" is a DESCENDANT
        # (feature-x descends from main but hasn't merged back)
        assert get_branch_relationship(
            git_repo, "main", "feature-x"
        ) == BranchRelationship.DESCENDANT

    def test_unrelated_sibling_branches(self, git_repo_with_sibling):
        clear_ancestry_cache()
        assert get_branch_relationship(
            git_repo_with_sibling, "feature-x", "feature-y"
        ) == BranchRelationship.UNRELATED

    def test_unknown_empty_current_branch(self, git_repo):
        assert get_branch_relationship(git_repo, "", "main") == BranchRelationship.UNKNOWN

    def test_unknown_empty_memory_branch(self, git_repo):
        assert get_branch_relationship(git_repo, "main", "") == BranchRelationship.UNKNOWN

    def test_unknown_detached_current(self, git_repo):
        assert get_branch_relationship(
            git_repo, "detached:abc12345", "main"
        ) == BranchRelationship.UNKNOWN

    def test_unknown_detached_memory(self, git_repo):
        assert get_branch_relationship(
            git_repo, "main", "detached:abc12345"
        ) == BranchRelationship.UNKNOWN


class TestClearAncestryCache:
    def test_clear_resets_cache(self, git_repo):
        # Populate cache
        is_ancestor(git_repo, "main", "feature-x")
        info_before = is_ancestor.cache_info()
        assert info_before.hits + info_before.misses > 0
        # Clear
        clear_ancestry_cache()
        info_after = is_ancestor.cache_info()
        assert info_after.hits == 0
        assert info_after.misses == 0


class TestBranchMultipliers:
    def test_multiplier_values(self):
        """BRANCH_MULTIPLIERS should map every BranchRelationship to the correct float."""
        assert BRANCH_MULTIPLIERS == {
            BranchRelationship.SAME: 1.5,
            BranchRelationship.ANCESTOR: 1.2,
            BranchRelationship.DESCENDANT: 1.0,
            BranchRelationship.UNRELATED: 0.8,
            BranchRelationship.UNKNOWN: 1.0,
        }

    def test_all_relationships_have_multipliers(self):
        """Every BranchRelationship value must have a multiplier."""
        for rel in BranchRelationship:
            assert rel in BRANCH_MULTIPLIERS, f"Missing multiplier for {rel}"
