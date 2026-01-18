"""End-to-end tests for code-review skill workflows.

Tests the complete flow from argument parsing through routing and edge case handling.
"""

import pytest

from spellbook_mcp.code_review.arg_parser import parse_args
from spellbook_mcp.code_review.router import route_to_handler, TargetType
from spellbook_mcp.code_review.edge_cases import (
    check_empty_diff,
    check_no_comments,
    check_diff_too_large,
)
from spellbook_mcp.code_review.models import FileDiff


class TestSelfModeWorkflow:
    """E2E tests for --self mode (pre-PR self-review)."""

    def test_self_mode_default_workflow(self) -> None:
        """Default invocation routes to self mode correctly."""
        # Parse args (no args = self mode)
        args = parse_args("")
        assert args.self_review is True

        # Route to handler
        handler = route_to_handler(args)
        assert handler.name == "self"
        assert handler.requires_diff is True
        assert handler.requires_feedback is False

        # Edge case: has files
        files = [FileDiff(path="foo.py", status="modified", additions=10)]
        empty_check = check_empty_diff(files)
        assert empty_check.detected is False
        assert empty_check.can_continue is True

    def test_self_mode_with_pr_workflow(self) -> None:
        """--self --pr 123 provides PR number for diff source."""
        args = parse_args("--self --pr 123")
        handler = route_to_handler(args)

        assert handler.name == "self"
        assert handler.target == "123"
        assert handler.target_type == TargetType.PR_NUMBER

    def test_self_mode_empty_diff_blocks(self) -> None:
        """Self mode with empty diff cannot continue."""
        args = parse_args("--self")
        handler = route_to_handler(args)

        # No files changed
        empty_check = check_empty_diff([])
        assert empty_check.detected is True
        assert empty_check.can_continue is False


class TestFeedbackModeWorkflow:
    """E2E tests for --feedback mode (process received feedback)."""

    def test_feedback_mode_workflow(self) -> None:
        """--feedback routes correctly and requires comments."""
        args = parse_args("--feedback")
        assert args.feedback is True
        assert args.self_review is False

        handler = route_to_handler(args)
        assert handler.name == "feedback"
        assert handler.requires_diff is False
        assert handler.requires_feedback is True

    def test_feedback_mode_with_pr(self) -> None:
        """--feedback --pr 456 fetches comments from specific PR."""
        args = parse_args("--feedback --pr 456")
        handler = route_to_handler(args)

        assert handler.name == "feedback"
        assert handler.target == "456"
        assert handler.target_type == TargetType.PR_NUMBER

    def test_feedback_mode_no_comments_blocks(self) -> None:
        """Feedback mode with no comments cannot continue."""
        args = parse_args("--feedback")
        handler = route_to_handler(args)

        # No comments
        no_comments_check = check_no_comments([])
        assert no_comments_check.detected is True
        assert no_comments_check.can_continue is False

    def test_feedback_mode_has_comments_continues(self) -> None:
        """Feedback mode with comments can continue."""
        args = parse_args("--feedback")
        handler = route_to_handler(args)

        comments = [{"body": "Please fix this", "author": "reviewer"}]
        no_comments_check = check_no_comments(comments)
        assert no_comments_check.detected is False
        assert no_comments_check.can_continue is True


class TestGiveModeWorkflow:
    """E2E tests for --give mode (review someone else's code)."""

    def test_give_mode_with_pr_number(self) -> None:
        """--give 789 with PR number."""
        args = parse_args("--give 789")
        assert args.give == "789"
        assert args.self_review is False

        handler = route_to_handler(args)
        assert handler.name == "give"
        assert handler.target == "789"
        assert handler.target_type == TargetType.PR_NUMBER

    def test_give_mode_with_url(self) -> None:
        """--give with GitHub PR URL extracts repo."""
        args = parse_args("--give https://github.com/owner/repo/pull/123")
        handler = route_to_handler(args)

        assert handler.name == "give"
        assert handler.target_type == TargetType.URL
        assert handler.repo == "owner/repo"

    def test_give_mode_with_branch(self) -> None:
        """--give with branch name."""
        args = parse_args("--give feature/my-feature")
        handler = route_to_handler(args)

        assert handler.name == "give"
        assert handler.target == "feature/my-feature"
        assert handler.target_type == TargetType.BRANCH

    def test_give_mode_large_diff_warns(self) -> None:
        """Give mode with large diff warns but can continue."""
        args = parse_args("--give 123")
        handler = route_to_handler(args)

        # Large diff
        files = [
            FileDiff(path=f"file{i}.py", status="modified", additions=200, deletions=0)
            for i in range(10)
        ]
        large_check = check_diff_too_large(files, threshold=500)
        assert large_check.detected is True
        assert large_check.can_continue is True  # Can continue with warning
        assert large_check.truncate_to is not None


class TestAuditModeWorkflow:
    """E2E tests for --audit mode (comprehensive multi-pass review)."""

    def test_audit_mode_enables_parallel(self) -> None:
        """--audit enables parallel processing by default."""
        args = parse_args("--audit")
        assert args.audit is True
        assert args.self_review is False

        handler = route_to_handler(args)
        assert handler.name == "audit"
        assert handler.parallel is True
        assert handler.requires_diff is True

    def test_audit_mode_with_scope(self) -> None:
        """--audit security scopes the review."""
        args = parse_args("--audit security")
        handler = route_to_handler(args)

        assert handler.name == "audit"
        assert handler.scope == "security"
        assert handler.parallel is True

    def test_audit_mode_with_file_scope(self) -> None:
        """--audit src/main.py scopes to specific file."""
        args = parse_args("--audit src/main.py")
        handler = route_to_handler(args)

        assert handler.name == "audit"
        assert handler.scope == "src/main.py"


class TestTarotModifierWorkflow:
    """E2E tests for --tarot modifier."""

    def test_tarot_with_self_mode(self) -> None:
        """--self --tarot preserves tarot flag."""
        args = parse_args("--self --tarot")
        assert args.tarot is True
        assert args.self_review is True

        handler = route_to_handler(args)
        assert handler.name == "self"
        # tarot flag is preserved in args, not handler

    def test_tarot_with_audit_mode(self) -> None:
        """--audit --tarot combines audit with tarot dialogue."""
        args = parse_args("--audit --tarot")
        assert args.tarot is True
        assert args.audit is True

        handler = route_to_handler(args)
        assert handler.name == "audit"
        assert handler.parallel is True


class TestDeprecationRouting:
    """E2E tests for deprecated skill argument routing.

    Old skills (requesting-code-review, receiving-code-review) should
    be translatable to new modes.
    """

    def test_old_requesting_code_review_maps_to_self(self) -> None:
        """Old requesting-code-review behavior maps to --self.

        When a user invokes the old skill with no special args,
        it should route to self mode.
        """
        # Old skill invocation: no args or just a target
        args = parse_args("")
        handler = route_to_handler(args)
        assert handler.name == "self"

    def test_old_receiving_code_review_maps_to_feedback(self) -> None:
        """Old receiving-code-review behavior maps to --feedback.

        When translating, --feedback should be added.
        """
        args = parse_args("--feedback")
        handler = route_to_handler(args)
        assert handler.name == "feedback"


class TestEdgeCaseIntegration:
    """E2E tests for edge case detection across modes."""

    def test_empty_diff_detected_in_give_mode(self) -> None:
        """Empty diff blocks give mode."""
        args = parse_args("--give 123")
        handler = route_to_handler(args)
        assert handler.requires_diff is True

        empty_check = check_empty_diff([])
        assert empty_check.detected is True
        assert empty_check.can_continue is False

    def test_large_diff_in_self_mode(self) -> None:
        """Large diff in self mode suggests truncation."""
        args = parse_args("--self")
        handler = route_to_handler(args)

        files = [
            FileDiff(path="huge.py", status="modified", additions=2000, deletions=0)
        ]
        large_check = check_diff_too_large(files, threshold=1000)
        assert large_check.detected is True
        assert large_check.can_continue is True
        assert "2000" in large_check.message or "lines" in large_check.message.lower()

    def test_no_comments_not_checked_in_self_mode(self) -> None:
        """Self mode doesn't require comments, so check is irrelevant.

        This test documents that the check exists but is mode-appropriate.
        """
        args = parse_args("--self")
        handler = route_to_handler(args)
        assert handler.requires_feedback is False

        # Even if we check, it's not blocking for self mode
        # (the orchestrator would skip this check)
        no_comments = check_no_comments([])
        assert no_comments.detected is True  # Check still works
        # But self mode wouldn't call this check
