"""Tests for code-review edge case handlers."""

import pytest

from spellbook_mcp.code_review.edge_cases import (
    EdgeCaseResult,
    check_empty_diff,
    check_no_comments,
    check_diff_too_large,
)
from spellbook_mcp.code_review.models import FileDiff


class TestEdgeCaseResult:
    """Tests for EdgeCaseResult dataclass."""

    def test_edge_case_result_defaults(self) -> None:
        """EdgeCaseResult has sensible defaults."""
        result = EdgeCaseResult(detected=False)
        assert result.detected is False
        assert result.message is None
        assert result.can_continue is True
        assert result.truncate_to is None

    def test_edge_case_result_all_fields(self) -> None:
        """EdgeCaseResult accepts all fields."""
        result = EdgeCaseResult(
            detected=True,
            message="Diff too large",
            can_continue=True,
            truncate_to=50,
        )
        assert result.detected is True
        assert result.message == "Diff too large"
        assert result.can_continue is True
        assert result.truncate_to == 50

    def test_edge_case_result_blocking(self) -> None:
        """EdgeCaseResult can indicate blocking condition."""
        result = EdgeCaseResult(
            detected=True,
            message="Empty diff",
            can_continue=False,
        )
        assert result.detected is True
        assert result.can_continue is False


class TestEdgeCaseResultExtendedFields:
    """Tests for extended EdgeCaseResult fields."""

    def test_edge_case_result_with_name(self) -> None:
        """EdgeCaseResult accepts name field."""
        result = EdgeCaseResult(detected=True, name="binary_files")
        assert result.name == "binary_files"

    def test_edge_case_result_name_defaults_none(self) -> None:
        """EdgeCaseResult name defaults to None."""
        result = EdgeCaseResult(detected=False)
        assert result.name is None

    def test_edge_case_result_with_severity(self) -> None:
        """EdgeCaseResult accepts severity field."""
        result = EdgeCaseResult(detected=True, severity="warning")
        assert result.severity == "warning"

    def test_edge_case_result_severity_defaults_none(self) -> None:
        """EdgeCaseResult severity defaults to None."""
        result = EdgeCaseResult(detected=False)
        assert result.severity is None

    def test_edge_case_result_with_affected_files(self) -> None:
        """EdgeCaseResult accepts affected_files field."""
        result = EdgeCaseResult(
            detected=True,
            affected_files=["image.png", "data.bin"],
        )
        assert result.affected_files == ["image.png", "data.bin"]

    def test_edge_case_result_affected_files_defaults_none(self) -> None:
        """EdgeCaseResult affected_files defaults to None."""
        result = EdgeCaseResult(detected=False)
        assert result.affected_files is None


class TestCheckEmptyDiff:
    """Tests for check_empty_diff function."""

    def test_empty_list_detected(self) -> None:
        """Empty file list is detected."""
        result = check_empty_diff([])
        assert result.detected is True
        assert result.can_continue is False
        assert "empty" in result.message.lower() or "no" in result.message.lower()

    def test_non_empty_list_passes(self) -> None:
        """Non-empty file list passes."""
        files = [FileDiff(path="foo.py", status="modified")]
        result = check_empty_diff(files)
        assert result.detected is False
        assert result.can_continue is True

    def test_multiple_files_passes(self) -> None:
        """Multiple files pass."""
        files = [
            FileDiff(path="foo.py", status="modified"),
            FileDiff(path="bar.py", status="added"),
            FileDiff(path="baz.py", status="deleted"),
        ]
        result = check_empty_diff(files)
        assert result.detected is False


class TestCheckNoComments:
    """Tests for check_no_comments function."""

    def test_empty_comments_detected(self) -> None:
        """Empty comments list is detected."""
        result = check_no_comments([])
        assert result.detected is True
        assert result.can_continue is False
        assert "no" in result.message.lower() or "comment" in result.message.lower()

    def test_none_comments_detected(self) -> None:
        """None comments is detected."""
        result = check_no_comments(None)
        assert result.detected is True
        assert result.can_continue is False

    def test_has_comments_passes(self) -> None:
        """Non-empty comments list passes."""
        comments = [{"body": "LGTM", "author": "reviewer"}]
        result = check_no_comments(comments)
        assert result.detected is False
        assert result.can_continue is True

    def test_multiple_comments_passes(self) -> None:
        """Multiple comments pass."""
        comments = [
            {"body": "Nice!", "author": "user1"},
            {"body": "Fix this", "author": "user2"},
        ]
        result = check_no_comments(comments)
        assert result.detected is False


class TestCheckDiffTooLarge:
    """Tests for check_diff_too_large function."""

    def test_small_diff_passes(self) -> None:
        """Small diff passes threshold check."""
        files = [
            FileDiff(path="foo.py", status="modified", additions=10, deletions=5),
        ]
        result = check_diff_too_large(files, threshold=100)
        assert result.detected is False
        assert result.can_continue is True

    def test_exactly_at_threshold_passes(self) -> None:
        """Diff exactly at threshold passes."""
        files = [
            FileDiff(path="foo.py", status="modified", additions=50, deletions=50),
        ]
        result = check_diff_too_large(files, threshold=100)
        assert result.detected is False

    def test_over_threshold_detected(self) -> None:
        """Diff over threshold is detected."""
        files = [
            FileDiff(path="foo.py", status="modified", additions=100, deletions=100),
        ]
        result = check_diff_too_large(files, threshold=100)
        assert result.detected is True
        assert result.can_continue is True  # Can continue with truncation
        assert result.truncate_to is not None

    def test_multiple_files_cumulative(self) -> None:
        """Multiple files' changes are cumulative."""
        files = [
            FileDiff(path="a.py", status="modified", additions=30, deletions=10),
            FileDiff(path="b.py", status="modified", additions=30, deletions=10),
            FileDiff(path="c.py", status="modified", additions=30, deletions=10),
        ]
        # Total: 120 lines changed
        result = check_diff_too_large(files, threshold=100)
        assert result.detected is True

    def test_truncate_to_suggests_reasonable_count(self) -> None:
        """Truncation suggestion is reasonable."""
        files = [
            FileDiff(path=f"file{i}.py", status="modified", additions=50, deletions=50)
            for i in range(10)
        ]
        # Total: 1000 lines across 10 files
        result = check_diff_too_large(files, threshold=200)
        assert result.detected is True
        assert result.truncate_to is not None
        assert result.truncate_to > 0
        assert result.truncate_to < len(files)

    def test_default_threshold(self) -> None:
        """Default threshold is reasonable (1000 lines)."""
        small_files = [
            FileDiff(path="foo.py", status="modified", additions=400, deletions=400),
        ]
        result = check_diff_too_large(small_files)
        assert result.detected is False

        large_files = [
            FileDiff(path="foo.py", status="modified", additions=600, deletions=600),
        ]
        result = check_diff_too_large(large_files)
        assert result.detected is True

    def test_empty_files_passes(self) -> None:
        """Empty file list passes."""
        result = check_diff_too_large([])
        assert result.detected is False
        assert result.can_continue is True

    def test_message_includes_counts(self) -> None:
        """Message includes line counts when over threshold."""
        files = [
            FileDiff(path="big.py", status="modified", additions=500, deletions=500),
        ]
        result = check_diff_too_large(files, threshold=100)
        assert result.detected is True
        assert result.message is not None
        # Message should mention the size
        assert "1000" in result.message or "lines" in result.message.lower()
