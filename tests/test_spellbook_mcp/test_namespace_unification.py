"""Tests for namespace unification via resolve_repo_root."""

import os
import subprocess

import pytest

from spellbook_mcp.path_utils import encode_cwd, resolve_repo_root


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return str(repo)


@pytest.fixture
def git_repo_with_worktree(git_repo, tmp_path):
    """Create a git repo with a worktree."""
    worktree_path = str(tmp_path / "worktree")
    subprocess.run(
        ["git", "worktree", "add", worktree_path, "-b", "feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    return git_repo, worktree_path


class TestResolveRepoRoot:
    def test_main_repo(self, git_repo):
        """resolve_repo_root on main repo returns the repo root path."""
        assert resolve_repo_root(git_repo) == git_repo

    def test_worktree_resolves_to_main(self, git_repo_with_worktree):
        """resolve_repo_root on worktree returns the main repo root."""
        main_repo, worktree = git_repo_with_worktree
        assert resolve_repo_root(worktree) == main_repo

    def test_subdirectory_of_repo(self, git_repo):
        """resolve_repo_root on a subdirectory returns the repo root."""
        subdir = os.path.join(git_repo, "src")
        os.makedirs(subdir)
        assert resolve_repo_root(subdir) == git_repo

    def test_no_git_repo(self, tmp_path):
        """resolve_repo_root on non-git dir returns the input path."""
        non_repo = str(tmp_path / "not_a_repo")
        os.makedirs(non_repo)
        assert resolve_repo_root(non_repo) == non_repo

    def test_nonexistent_path(self):
        """resolve_repo_root on nonexistent path returns input path."""
        result = resolve_repo_root("/nonexistent/path/xyz")
        assert result == "/nonexistent/path/xyz"

    def test_worktree_subdirectory_resolves_to_main(self, git_repo_with_worktree):
        """resolve_repo_root on a subdir inside a worktree still resolves to main repo root."""
        main_repo, worktree = git_repo_with_worktree
        subdir = os.path.join(worktree, "lib")
        os.makedirs(subdir)
        assert resolve_repo_root(subdir) == main_repo


class TestEncodeCwdWithGitRoot:
    def test_worktrees_produce_same_namespace(self, git_repo_with_worktree):
        """encode_cwd on main repo and its worktree produce identical namespaces."""
        main_repo, worktree = git_repo_with_worktree
        assert encode_cwd(main_repo) == encode_cwd(worktree)

    def test_resolve_git_root_false_preserves_old_behavior(
        self, git_repo_with_worktree
    ):
        """encode_cwd with resolve_git_root=False preserves old path-based encoding."""
        main_repo, worktree = git_repo_with_worktree
        # With resolve_git_root=False, different paths produce different namespaces
        assert encode_cwd(main_repo, resolve_git_root=False) != encode_cwd(
            worktree, resolve_git_root=False
        )

    def test_non_git_dir_unchanged(self, tmp_path):
        """encode_cwd on non-git dir still encodes the path correctly."""
        path = str(tmp_path / "plain_dir")
        os.makedirs(path)
        # Should encode the path as-is (resolve_repo_root falls back to input)
        expected = path.replace("/", "-").lstrip("-")
        result = encode_cwd(path)
        assert result == expected

    def test_resolve_git_root_true_encodes_repo_root(self, git_repo):
        """encode_cwd with resolve_git_root=True encodes the repo root, not a subdir."""
        subdir = os.path.join(git_repo, "src", "deep")
        os.makedirs(subdir)
        expected = git_repo.replace("/", "-").lstrip("-")
        assert encode_cwd(subdir) == expected

    def test_resolve_git_root_false_encodes_exact_path(self, git_repo):
        """encode_cwd with resolve_git_root=False encodes the exact path given."""
        subdir = os.path.join(git_repo, "src")
        os.makedirs(subdir)
        expected = subdir.replace("/", "-").lstrip("-")
        assert encode_cwd(subdir, resolve_git_root=False) == expected
