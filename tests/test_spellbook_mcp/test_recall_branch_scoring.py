"""Tests for branch-weighted recall scoring and branch helper functions."""

import subprocess

import pytest

from spellbook.core.db import get_connection, init_db, close_all_connections
from spellbook.memory.store import (
    insert_branch_association,
    insert_memory,
    get_branch_associations,
    recall_by_query,
    recall_by_file_path,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path
    close_all_connections()


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo with main and feature-x branches.

    Branch topology:
        main: init commit
        feature-x: init commit -> feature commit (feature-x is descendant of main)
    So main is ANCESTOR of feature-x, and feature-x is DESCENDANT of main.
    """
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
    subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=repo,
                    check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "feature"], cwd=repo,
                    check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True,
                    capture_output=True)
    return str(repo)


@pytest.fixture
def db_with_memories(db_path):
    """Create DB with memories on different branches for scoring tests."""
    # Memory on main branch
    insert_memory(
        db_path=db_path,
        content="Authentication uses JWT tokens for API access",
        memory_type="fact",
        namespace="test-project",
        tags=["auth", "jwt"],
        citations=[{"file_path": "auth.py"}],
        branch="main",
    )
    # Memory on feature-x branch
    insert_memory(
        db_path=db_path,
        content="Authentication requires OAuth2 for third-party integrations",
        memory_type="fact",
        namespace="test-project",
        tags=["auth", "oauth"],
        citations=[{"file_path": "auth.py"}],
        branch="feature-x",
    )
    # Memory with no branch
    insert_memory(
        db_path=db_path,
        content="Authentication module handles user login and session management",
        memory_type="fact",
        namespace="test-project",
        tags=["auth", "login"],
        citations=[{"file_path": "auth.py"}],
        branch="",
    )
    return db_path


class TestInsertBranchAssociation:
    def test_insert_association(self, db_path):
        """insert_branch_association creates a branch association record."""
        mem_id = insert_memory(
            db_path=db_path, content="Test content for association",
            memory_type="fact", namespace="ns", tags=[], citations=[],
        )
        insert_branch_association(db_path, mem_id, "main", "manual")
        assocs = get_branch_associations(db_path, mem_id)
        assert len(assocs) == 1
        assert assocs[0]["branch"] == "main"
        assert assocs[0]["type"] == "manual"

    def test_insert_association_idempotent(self, db_path):
        """Inserting the same association twice should not create duplicates."""
        mem_id = insert_memory(
            db_path=db_path, content="Test idempotent association",
            memory_type="fact", namespace="ns", tags=[], citations=[],
        )
        insert_branch_association(db_path, mem_id, "main", "origin")
        insert_branch_association(db_path, mem_id, "main", "origin")
        assocs = get_branch_associations(db_path, mem_id)
        assert len(assocs) == 1


class TestGetBranchAssociations:
    def test_multiple_associations(self, db_path):
        """A memory can have associations with multiple branches."""
        mem_id = insert_memory(
            db_path=db_path, content="Multi-branch memory",
            memory_type="fact", namespace="ns", tags=[], citations=[],
            branch="feature-a",
        )
        insert_branch_association(db_path, mem_id, "main", "ancestor")
        assocs = get_branch_associations(db_path, mem_id)
        branches = {a["branch"] for a in assocs}
        assert branches == {"feature-a", "main"}

    def test_no_associations(self, db_path):
        """A memory with no branch has no associations."""
        mem_id = insert_memory(
            db_path=db_path, content="No branch memory",
            memory_type="fact", namespace="ns", tags=[], citations=[],
        )
        assocs = get_branch_associations(db_path, mem_id)
        assert assocs == []


class TestRecallByQueryBranch:
    def test_same_branch_boosted(self, db_with_memories, git_repo):
        """Memories on same branch should score higher (1.5x multiplier)."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()
        results = recall_by_query(
            db_path=db_with_memories,
            query="authentication",
            namespace="test-project",
            limit=10,
            branch="main",
            repo_path=git_repo,
        )
        # All 3 memories match "authentication"
        assert len(results) >= 2
        # First result should be the main-branch memory (1.5x SAME boost)
        assert results[0]["branch"] == "main"
        assert results[0]["branch_relationship"] == "same"
        # Verify ordering: same-branch memory must rank above unrelated-branch memory
        unrelated = [r for r in results if r["branch_relationship"] == "unrelated"]
        if unrelated:
            same_idx = next(i for i, r in enumerate(results) if r["branch_relationship"] == "same")
            unrelated_idx = next(i for i, r in enumerate(results) if r["branch_relationship"] == "unrelated")
            assert same_idx < unrelated_idx, (
                f"same-branch memory (idx {same_idx}) should rank above "
                f"unrelated memory (idx {unrelated_idx})"
            )

    def test_ancestor_branch_boosted(self, db_with_memories, git_repo):
        """Memories on ancestor branch get 1.2x boost when recalling from descendant."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()
        # Recall from feature-x: main is ANCESTOR of feature-x
        results = recall_by_query(
            db_path=db_with_memories,
            query="authentication",
            namespace="test-project",
            limit=10,
            branch="feature-x",
            repo_path=git_repo,
        )
        assert len(results) >= 2
        # feature-x memory gets SAME (1.5x), main memory gets ANCESTOR (1.2x)
        feature_results = [r for r in results if r["branch"] == "feature-x"]
        main_results = [r for r in results if r["branch"] == "main"]
        assert len(feature_results) >= 1
        assert feature_results[0]["branch_relationship"] == "same"
        assert len(main_results) >= 1
        assert main_results[0]["branch_relationship"] == "ancestor"
        # Verify ordering: ancestor (1.2x) must rank above unrelated (0.8x)
        ancestor_idx = next(i for i, r in enumerate(results) if r["branch_relationship"] == "ancestor")
        unrelated_results = [i for i, r in enumerate(results) if r["branch_relationship"] == "unrelated"]
        if unrelated_results:
            assert ancestor_idx < unrelated_results[0], (
                f"ancestor memory (idx {ancestor_idx}) should rank above "
                f"unrelated memory (idx {unrelated_results[0]})"
            )

    def test_no_branch_neutral(self, db_with_memories):
        """Recall without branch should not apply weighting (no branch_relationship field)."""
        results = recall_by_query(
            db_path=db_with_memories,
            query="authentication",
            namespace="test-project",
            limit=10,
        )
        assert len(results) >= 1
        # Without branch/repo_path, no branch_relationship should be added
        for r in results:
            assert "branch_relationship" not in r

    def test_returns_branch_field(self, db_with_memories, git_repo):
        """Results should include the branch field from the memory with exact expected values."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()
        results = recall_by_query(
            db_path=db_with_memories,
            query="authentication",
            namespace="test-project",
            limit=10,
            branch="main",
            repo_path=git_repo,
        )
        branches_in_results = {r["branch"] for r in results}
        # db_with_memories inserts memories on "main", "feature-x", and "" (empty)
        assert branches_in_results == {"main", "feature-x", ""}

    def test_lazy_junction_population_on_ancestor(self, db_with_memories, git_repo):
        """When recall finds ANCESTOR relationship, it should insert ancestor association."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()
        # Recall from feature-x: main is ancestor of feature-x
        recall_by_query(
            db_path=db_with_memories,
            query="authentication",
            namespace="test-project",
            limit=10,
            branch="feature-x",
            repo_path=git_repo,
        )
        # The main-branch memory should now have an ancestor association for feature-x
        conn = get_connection(db_with_memories)
        # Find the main-branch memory
        cursor = conn.execute(
            "SELECT id FROM memories WHERE branch = 'main' AND namespace = 'test-project'"
        )
        main_mem_id = cursor.fetchone()[0]
        assocs = get_branch_associations(db_with_memories, main_mem_id)
        assoc_map = {a["branch"]: a["type"] for a in assocs}
        assert "feature-x" in assoc_map
        assert assoc_map["feature-x"] == "ancestor"


class TestRecallBranchOrderingWithEqualBaseScores:
    """Prove branch multipliers change result ordering when base scores are equal."""

    def test_same_branch_ranks_above_unrelated_equal_importance(self, db_path, git_repo):
        """With equal importance, same-branch (1.5x) must rank above unrelated (0.8x)."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()

        # Create an unrelated branch in the git repo
        subprocess.run(["git", "checkout", "--orphan", "orphan-branch"], cwd=git_repo,
                        check=True, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "orphan"], cwd=git_repo,
                        check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=git_repo,
                        check=True, capture_output=True)

        # Insert two memories with identical content/importance but different branches.
        # Using empty-query recall so base score = importance (equal for both).
        insert_memory(
            db_path=db_path,
            content="Database connection pooling configuration",
            memory_type="fact",
            namespace="ordering-test",
            tags=["db"],
            citations=[],
            branch="main",
        )
        insert_memory(
            db_path=db_path,
            content="Database connection timeout settings",
            memory_type="fact",
            namespace="ordering-test",
            tags=["db"],
            citations=[],
            branch="orphan-branch",
        )

        results = recall_by_query(
            db_path=db_path,
            query="database connection",
            namespace="ordering-test",
            limit=10,
            branch="main",
            repo_path=git_repo,
        )
        assert len(results) == 2
        # same-branch memory must come first due to 1.5x vs 0.8x multiplier
        assert results[0]["branch"] == "main"
        assert results[0]["branch_relationship"] == "same"
        assert results[1]["branch"] == "orphan-branch"
        assert results[1]["branch_relationship"] == "unrelated"


class TestRecallByFilePathBranch:
    def test_file_path_recall_with_branch(self, db_with_memories, git_repo):
        """recall_by_file_path should apply branch weighting when repo_path is provided."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()
        results = recall_by_file_path(
            db_path=db_with_memories,
            file_path="auth.py",
            namespace="test-project",
            limit=10,
            branch="main",
            repo_path=git_repo,
        )
        assert len(results) >= 2
        # First result should be main-branch memory (1.5x SAME boost)
        assert results[0]["branch"] == "main"
        assert results[0]["branch_relationship"] == "same"

    def test_file_path_recall_without_repo_path(self, db_with_memories):
        """recall_by_file_path without repo_path should not apply branch weighting."""
        results = recall_by_file_path(
            db_path=db_with_memories,
            file_path="auth.py",
            namespace="test-project",
            limit=10,
            branch="main",
        )
        assert len(results) >= 1
        # Without repo_path, no branch_relationship
        for r in results:
            assert "branch_relationship" not in r

    def test_file_path_recall_lazy_junction_population(self, db_with_memories, git_repo):
        """recall_by_file_path should lazily populate junction for ancestor relationships."""
        from spellbook.branch_ancestry import clear_ancestry_cache
        clear_ancestry_cache()
        recall_by_file_path(
            db_path=db_with_memories,
            file_path="auth.py",
            namespace="test-project",
            limit=10,
            branch="feature-x",
            repo_path=git_repo,
        )
        # The main-branch memory should now have ancestor association for feature-x
        conn = get_connection(db_with_memories)
        cursor = conn.execute(
            "SELECT id FROM memories WHERE branch = 'main' AND namespace = 'test-project'"
        )
        main_mem_id = cursor.fetchone()[0]
        assocs = get_branch_associations(db_with_memories, main_mem_id)
        assoc_map = {a["branch"]: a["type"] for a in assocs}
        assert "feature-x" in assoc_map
        assert assoc_map["feature-x"] == "ancestor"
