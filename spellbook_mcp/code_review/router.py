"""Mode router for code-review skill.

Routes parsed arguments to the appropriate handler configuration.
"""

import re
from dataclasses import dataclass
from enum import Enum

from .arg_parser import CodeReviewArgs


class TargetType(Enum):
    """Type of target for give mode.

    - PR_NUMBER: Numeric PR number (e.g., "123")
    - URL: Full GitHub PR URL
    - BRANCH: Branch name (e.g., "feature/foo")
    """

    PR_NUMBER = "pr_number"
    URL = "url"
    BRANCH = "branch"


@dataclass
class ModeHandler:
    """Handler configuration for a code-review mode.

    Attributes:
        name: Mode name (self, feedback, give, audit)
        requires_diff: Whether this mode needs diff data
        requires_feedback: Whether this mode needs PR comments
        target: Target identifier (PR number, URL, or branch)
        target_type: Type of target if present
        repo: Repository in owner/repo format if detected from URL
        scope: Scope for audit mode (file, directory, 'security', 'all')
        parallel: Whether to enable parallel processing
    """

    name: str
    requires_diff: bool = True
    requires_feedback: bool = False
    target: str | None = None
    target_type: TargetType | None = None
    repo: str | None = None
    scope: str | None = None
    parallel: bool = False


# Regex patterns for target type detection
_GITHUB_PR_URL = re.compile(
    r"(?:https?://)?github\.com/([^/]+/[^/]+)/pull/(\d+)",
    re.IGNORECASE,
)


def _detect_target_type(target: str) -> tuple[TargetType, str | None]:
    """Detect the type of a target string.

    Args:
        target: The target string to analyze

    Returns:
        Tuple of (target_type, repo) where repo is only populated for URLs
    """
    # Check if it's a pure number (PR number)
    if target.isdigit():
        return TargetType.PR_NUMBER, None

    # Check if it's a GitHub PR URL
    match = _GITHUB_PR_URL.search(target)
    if match:
        repo = match.group(1)
        return TargetType.URL, repo

    # Default to branch
    return TargetType.BRANCH, None


def route_to_handler(args: CodeReviewArgs) -> ModeHandler:
    """Route parsed arguments to appropriate handler configuration.

    Args:
        args: Parsed CodeReviewArgs from argument parser

    Returns:
        ModeHandler configured for the selected mode
    """
    # Handle give mode
    if args.give is not None:
        target_type, repo = _detect_target_type(args.give)
        return ModeHandler(
            name="give",
            requires_diff=True,
            requires_feedback=False,
            target=args.give,
            target_type=target_type,
            repo=repo,
        )

    # Handle audit mode
    if args.audit:
        return ModeHandler(
            name="audit",
            requires_diff=True,
            requires_feedback=False,
            scope=args.audit_scope,
            parallel=True,
        )

    # Handle feedback mode
    if args.feedback:
        target = str(args.pr) if args.pr else None
        target_type = TargetType.PR_NUMBER if args.pr else None
        return ModeHandler(
            name="feedback",
            requires_diff=False,
            requires_feedback=True,
            target=target,
            target_type=target_type,
        )

    # Default: self mode
    target = str(args.pr) if args.pr else None
    target_type = TargetType.PR_NUMBER if args.pr else None
    return ModeHandler(
        name="self",
        requires_diff=True,
        requires_feedback=False,
        target=target,
        target_type=target_type,
    )
