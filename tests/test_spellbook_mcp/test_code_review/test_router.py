"""Tests for code-review mode router."""

import pytest

from spellbook_mcp.code_review.router import (
    ModeHandler,
    TargetType,
    route_to_handler,
)
from spellbook_mcp.code_review.arg_parser import CodeReviewArgs


class TestModeHandler:
    """Tests for ModeHandler dataclass."""

    def test_mode_handler_defaults(self) -> None:
        """ModeHandler has sensible defaults."""
        handler = ModeHandler(name="self")
        assert handler.name == "self"
        assert handler.requires_diff is True
        assert handler.requires_feedback is False
        assert handler.target is None
        assert handler.target_type is None
        assert handler.repo is None
        assert handler.scope is None
        assert handler.parallel is False

    def test_mode_handler_all_fields(self) -> None:
        """ModeHandler accepts all fields."""
        handler = ModeHandler(
            name="give",
            requires_diff=True,
            requires_feedback=False,
            target="https://github.com/owner/repo/pull/123",
            target_type=TargetType.URL,
            repo="owner/repo",
            scope="security",
            parallel=True,
        )
        assert handler.name == "give"
        assert handler.target_type == TargetType.URL
        assert handler.repo == "owner/repo"
        assert handler.scope == "security"
        assert handler.parallel is True


class TestTargetType:
    """Tests for TargetType enum."""

    def test_target_types_exist(self) -> None:
        """TargetType has expected values."""
        assert TargetType.PR_NUMBER.value == "pr_number"
        assert TargetType.URL.value == "url"
        assert TargetType.BRANCH.value == "branch"


class TestRouteToHandler:
    """Tests for route_to_handler function."""

    def test_self_mode_default(self) -> None:
        """Default args routes to self mode."""
        args = CodeReviewArgs()
        handler = route_to_handler(args)

        assert handler.name == "self"
        assert handler.requires_diff is True
        assert handler.requires_feedback is False
        assert handler.parallel is False

    def test_self_mode_explicit(self) -> None:
        """Explicit --self routes to self mode."""
        args = CodeReviewArgs(self_review=True)
        handler = route_to_handler(args)

        assert handler.name == "self"
        assert handler.requires_diff is True

    def test_self_mode_with_pr(self) -> None:
        """Self mode with --pr populates target."""
        args = CodeReviewArgs(self_review=True, pr=123)
        handler = route_to_handler(args)

        assert handler.name == "self"
        assert handler.target == "123"
        assert handler.target_type == TargetType.PR_NUMBER

    def test_feedback_mode(self) -> None:
        """--feedback routes to feedback mode."""
        args = CodeReviewArgs(self_review=False, feedback=True)
        handler = route_to_handler(args)

        assert handler.name == "feedback"
        assert handler.requires_diff is False
        assert handler.requires_feedback is True

    def test_feedback_mode_with_pr(self) -> None:
        """Feedback mode with --pr populates target."""
        args = CodeReviewArgs(self_review=False, feedback=True, pr=456)
        handler = route_to_handler(args)

        assert handler.name == "feedback"
        assert handler.target == "456"
        assert handler.target_type == TargetType.PR_NUMBER

    def test_give_mode_with_pr_number(self) -> None:
        """--give with PR number routes correctly."""
        args = CodeReviewArgs(self_review=False, give="789")
        handler = route_to_handler(args)

        assert handler.name == "give"
        assert handler.requires_diff is True
        assert handler.requires_feedback is False
        assert handler.target == "789"
        assert handler.target_type == TargetType.PR_NUMBER

    def test_give_mode_with_url(self) -> None:
        """--give with URL routes correctly."""
        args = CodeReviewArgs(
            self_review=False,
            give="https://github.com/owner/repo/pull/123",
        )
        handler = route_to_handler(args)

        assert handler.name == "give"
        assert handler.target == "https://github.com/owner/repo/pull/123"
        assert handler.target_type == TargetType.URL
        assert handler.repo == "owner/repo"

    def test_give_mode_with_branch(self) -> None:
        """--give with branch name routes correctly."""
        args = CodeReviewArgs(self_review=False, give="feature/my-branch")
        handler = route_to_handler(args)

        assert handler.name == "give"
        assert handler.target == "feature/my-branch"
        assert handler.target_type == TargetType.BRANCH

    def test_audit_mode(self) -> None:
        """--audit routes to audit mode."""
        args = CodeReviewArgs(self_review=False, audit=True)
        handler = route_to_handler(args)

        assert handler.name == "audit"
        assert handler.requires_diff is True
        assert handler.requires_feedback is False
        assert handler.parallel is True  # Audit enables parallel by default

    def test_audit_mode_with_scope(self) -> None:
        """--audit with scope sets scope field."""
        args = CodeReviewArgs(self_review=False, audit=True, audit_scope="security")
        handler = route_to_handler(args)

        assert handler.name == "audit"
        assert handler.scope == "security"
        assert handler.parallel is True

    def test_audit_mode_with_file_scope(self) -> None:
        """--audit with file path scope."""
        args = CodeReviewArgs(
            self_review=False,
            audit=True,
            audit_scope="src/main.py",
        )
        handler = route_to_handler(args)

        assert handler.name == "audit"
        assert handler.scope == "src/main.py"

    def test_tarot_modifier_preserved(self) -> None:
        """--tarot modifier flows through all modes."""
        args = CodeReviewArgs(self_review=True, tarot=True)
        handler = route_to_handler(args)

        # tarot is not a handler field, but we verify it doesn't break routing
        assert handler.name == "self"


class TestTargetTypeParsing:
    """Tests for target type detection."""

    def test_numeric_string_is_pr_number(self) -> None:
        """Pure numeric string is detected as PR number."""
        args = CodeReviewArgs(self_review=False, give="42")
        handler = route_to_handler(args)
        assert handler.target_type == TargetType.PR_NUMBER

    def test_github_pr_url_parsed(self) -> None:
        """GitHub PR URL is detected and repo extracted."""
        args = CodeReviewArgs(
            self_review=False,
            give="https://github.com/myorg/myrepo/pull/555",
        )
        handler = route_to_handler(args)
        assert handler.target_type == TargetType.URL
        assert handler.repo == "myorg/myrepo"

    def test_github_short_url(self) -> None:
        """Short GitHub URL detected."""
        args = CodeReviewArgs(
            self_review=False,
            give="github.com/org/repo/pull/1",
        )
        handler = route_to_handler(args)
        assert handler.target_type == TargetType.URL
        assert handler.repo == "org/repo"

    def test_branch_with_slashes(self) -> None:
        """Branch names with slashes are branches, not URLs."""
        args = CodeReviewArgs(
            self_review=False,
            give="feature/add-login/oauth",
        )
        handler = route_to_handler(args)
        assert handler.target_type == TargetType.BRANCH

    def test_simple_branch_name(self) -> None:
        """Simple branch name without slashes."""
        args = CodeReviewArgs(self_review=False, give="main")
        handler = route_to_handler(args)
        assert handler.target_type == TargetType.BRANCH

    def test_hyphenated_branch(self) -> None:
        """Hyphenated branch name."""
        args = CodeReviewArgs(self_review=False, give="fix-bug-123")
        handler = route_to_handler(args)
        assert handler.target_type == TargetType.BRANCH


class TestModeHandlerWarnings:
    """Tests for ModeHandler warnings field."""

    def test_warnings_defaults_empty_list(self) -> None:
        """ModeHandler warnings defaults to empty list."""
        handler = ModeHandler(name="self")
        assert handler.warnings == []

    def test_warnings_can_be_set(self) -> None:
        """ModeHandler warnings can be populated."""
        handler = ModeHandler(
            name="self",
            warnings=["'old-skill' is deprecated. Use 'new-skill' instead."],
        )
        assert len(handler.warnings) == 1
        assert "deprecated" in handler.warnings[0]

    def test_warnings_multiple(self) -> None:
        """ModeHandler can hold multiple warnings."""
        handler = ModeHandler(
            name="self",
            warnings=["Warning 1", "Warning 2", "Warning 3"],
        )
        assert len(handler.warnings) == 3


class TestDeprecationWarnings:
    """Tests for deprecation warning emission."""

    def test_requesting_code_review_deprecated(self) -> None:
        """Emits warning when invoked from requesting-code-review skill."""
        args = CodeReviewArgs(self_review=True)
        result = route_to_handler(args, source_skill="requesting-code-review")
        assert len(result.warnings) == 1
        assert "requesting-code-review" in result.warnings[0]
        assert "deprecated" in result.warnings[0].lower()
        assert "code-review --self" in result.warnings[0]

    def test_receiving_code_review_deprecated(self) -> None:
        """Emits warning when invoked from receiving-code-review skill."""
        args = CodeReviewArgs(feedback=True)
        result = route_to_handler(args, source_skill="receiving-code-review")
        assert len(result.warnings) == 1
        assert "receiving-code-review" in result.warnings[0]
        assert "code-review --feedback" in result.warnings[0]

    def test_code_review_not_deprecated(self) -> None:
        """No warning when invoked from code-review skill."""
        args = CodeReviewArgs(self_review=True)
        result = route_to_handler(args, source_skill="code-review")
        assert result.warnings == []

    def test_no_source_skill_no_warning(self) -> None:
        """No warning when source_skill is None."""
        args = CodeReviewArgs(self_review=True)
        result = route_to_handler(args, source_skill=None)
        assert result.warnings == []

    def test_no_source_skill_default_no_warning(self) -> None:
        """No warning when source_skill is not provided (default)."""
        args = CodeReviewArgs(self_review=True)
        result = route_to_handler(args)
        assert result.warnings == []

    def test_unknown_skill_no_warning(self) -> None:
        """No warning for unknown source skills."""
        args = CodeReviewArgs(self_review=True)
        result = route_to_handler(args, source_skill="some-other-skill")
        assert result.warnings == []

    def test_deprecation_warning_with_give_mode(self) -> None:
        """Deprecation warning works with give mode."""
        args = CodeReviewArgs(give="123")
        result = route_to_handler(args, source_skill="requesting-code-review")
        assert result.name == "give"
        assert len(result.warnings) == 1
        assert "requesting-code-review" in result.warnings[0]
