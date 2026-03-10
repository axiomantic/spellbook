"""Git branch ancestry checks with LRU caching.

All git operations are subprocess calls with timeouts to prevent
hanging on broken git repos or network-mounted filesystems.
"""

import subprocess
from enum import Enum
from functools import lru_cache
from typing import Dict


class BranchRelationship(Enum):
    """Relationship between two git branches."""

    SAME = "same"
    ANCESTOR = "ancestor"
    DESCENDANT = "descendant"
    UNRELATED = "unrelated"
    UNKNOWN = "unknown"


# Branch weighting multipliers for recall scoring.
BRANCH_MULTIPLIERS: Dict[BranchRelationship, float] = {
    BranchRelationship.SAME: 1.5,
    BranchRelationship.ANCESTOR: 1.2,
    BranchRelationship.DESCENDANT: 1.0,
    BranchRelationship.UNRELATED: 0.8,
    BranchRelationship.UNKNOWN: 1.0,
}


def get_current_branch(repo_path: str) -> str:
    """Get the current branch name, or commit SHA prefix for detached HEAD.

    Returns:
        Branch name (e.g., "main"), or "detached:<sha8>" for detached HEAD,
        or "" if not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return ""
        branch = result.stdout.strip()
        if branch == "HEAD":
            # Detached HEAD: get short SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "--short=8", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if sha_result.returncode == 0:
                return f"detached:{sha_result.stdout.strip()}"
            return ""
        return branch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


@lru_cache(maxsize=512)
def is_ancestor(repo_path: str, potential_ancestor: str, branch: str) -> bool:
    """Check if potential_ancestor is an ancestor of branch.

    Uses git merge-base --is-ancestor. Results are cached because
    ancestry relationships are immutable for merged commits.

    Args:
        repo_path: Path to git repository root.
        potential_ancestor: Branch name to test as ancestor.
        branch: Branch name to test as descendant.

    Returns:
        True if potential_ancestor is an ancestor of branch.
    """
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", potential_ancestor, branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def get_branch_relationship(
    repo_path: str,
    current_branch: str,
    memory_branch: str,
) -> BranchRelationship:
    """Determine the relationship between current branch and a memory's branch.

    Args:
        repo_path: Path to git repository root.
        current_branch: The branch the user is currently on.
        memory_branch: The branch the memory is associated with.

    Returns:
        BranchRelationship enum value.
    """
    if not current_branch or not memory_branch:
        return BranchRelationship.UNKNOWN
    if current_branch == memory_branch:
        return BranchRelationship.SAME

    # Detached HEAD: cannot compute ancestry
    if current_branch.startswith("detached:") or memory_branch.startswith("detached:"):
        return BranchRelationship.UNKNOWN

    # Check if memory_branch is ancestor of current_branch
    # (memory was created on a branch that was later merged into current)
    if is_ancestor(repo_path, memory_branch, current_branch):
        return BranchRelationship.ANCESTOR

    # Check reverse: current is ancestor of memory's branch
    if is_ancestor(repo_path, current_branch, memory_branch):
        return BranchRelationship.DESCENDANT

    return BranchRelationship.UNRELATED


def clear_ancestry_cache() -> None:
    """Clear the LRU cache. Useful for testing or after force-push."""
    is_ancestor.cache_clear()
