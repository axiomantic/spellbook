"""Edge case handlers for code-review skill.

Provides early detection of conditions that affect review workflow.
"""

from dataclasses import dataclass
from typing import Any

from .models import FileDiff


@dataclass
class EdgeCaseResult:
    """Result of an edge case check.

    Attributes:
        detected: Whether the edge case was detected
        message: Human-readable description of the edge case
        can_continue: Whether the workflow can continue
        truncate_to: Suggested number of files to review if truncation needed
        name: Identifier for this edge case type (e.g., "binary_files")
        severity: Severity level ("warning", "error") if detected
        affected_files: List of file paths affected by this edge case
    """

    detected: bool
    message: str | None = None
    can_continue: bool = True
    truncate_to: int | None = None
    name: str | None = None
    severity: str | None = None
    affected_files: list[str] | None = None


def check_empty_diff(files: list[FileDiff]) -> EdgeCaseResult:
    """Check if the diff is empty (no files changed).

    Args:
        files: List of file diffs to check

    Returns:
        EdgeCaseResult indicating whether diff is empty
    """
    if not files:
        return EdgeCaseResult(
            detected=True,
            message="No files changed. Nothing to review.",
            can_continue=False,
        )
    return EdgeCaseResult(detected=False)


def check_no_comments(comments: list[dict[str, Any]] | None) -> EdgeCaseResult:
    """Check if there are no review comments.

    Args:
        comments: List of comment dictionaries or None

    Returns:
        EdgeCaseResult indicating whether there are no comments
    """
    if comments is None or len(comments) == 0:
        return EdgeCaseResult(
            detected=True,
            message="No review comments found. Nothing to address.",
            can_continue=False,
        )
    return EdgeCaseResult(detected=False)


def check_diff_too_large(
    files: list[FileDiff],
    threshold: int = 1000,
) -> EdgeCaseResult:
    """Check if the diff exceeds a size threshold.

    Args:
        files: List of file diffs to check
        threshold: Maximum total lines changed before warning (default 1000)

    Returns:
        EdgeCaseResult with truncation suggestion if too large
    """
    if not files:
        return EdgeCaseResult(detected=False)

    total_lines = sum(f.additions + f.deletions for f in files)

    if total_lines <= threshold:
        return EdgeCaseResult(detected=False)

    # Calculate how many files to suggest for truncation
    # Goal: suggest enough files to stay under threshold
    cumulative = 0
    suggested_count = 0
    for f in files:
        cumulative += f.additions + f.deletions
        suggested_count += 1
        if cumulative >= threshold:
            break

    # Ensure at least 1 file and less than total
    truncate_to = max(1, min(suggested_count, len(files) - 1))

    return EdgeCaseResult(
        detected=True,
        message=f"Diff is large ({total_lines} lines across {len(files)} files). "
        f"Consider reviewing in batches.",
        can_continue=True,
        truncate_to=truncate_to,
    )
