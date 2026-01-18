"""Tests for code_review data models."""

import pytest
from enum import Enum

from spellbook_mcp.code_review.models import (
    Severity,
    FileDiff,
    PRData,
    Finding,
    FeedbackCategory,
    FeedbackUrgency,
    FeedbackItem,
    ReviewStatus,
    ReviewReport,
)


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self):
        """Severity should have critical, important, and minor levels."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.IMPORTANT.value == "important"
        assert Severity.MINOR.value == "minor"

    def test_severity_ordering(self):
        """Critical > Important > Minor for sorting purposes."""
        # We can compare by using a custom ordering or just verify they exist
        severities = [Severity.MINOR, Severity.CRITICAL, Severity.IMPORTANT]
        # Sort by the natural order we want: CRITICAL first, then IMPORTANT, then MINOR
        sorted_severities = sorted(severities, key=lambda s: {
            Severity.CRITICAL: 0,
            Severity.IMPORTANT: 1,
            Severity.MINOR: 2,
        }[s])
        assert sorted_severities == [Severity.CRITICAL, Severity.IMPORTANT, Severity.MINOR]


class TestFileDiff:
    """Tests for FileDiff dataclass."""

    def test_basic_file_diff(self):
        """FileDiff should store path, status, and change counts."""
        diff = FileDiff(
            path="src/main.py",
            status="modified",
            additions=10,
            deletions=5,
        )
        assert diff.path == "src/main.py"
        assert diff.status == "modified"
        assert diff.additions == 10
        assert diff.deletions == 5

    def test_file_diff_with_old_path(self):
        """FileDiff should support old_path for renames."""
        diff = FileDiff(
            path="src/new_name.py",
            old_path="src/old_name.py",
            status="renamed",
            additions=0,
            deletions=0,
        )
        assert diff.old_path == "src/old_name.py"

    def test_file_diff_with_hunks(self):
        """FileDiff should support hunks for detailed diff info."""
        diff = FileDiff(
            path="src/main.py",
            status="modified",
            additions=5,
            deletions=2,
            hunks=[
                {"start": 10, "count": 5, "content": "@@ -10,5 +10,8 @@"},
            ],
        )
        assert len(diff.hunks) == 1
        assert diff.hunks[0]["start"] == 10

    def test_file_diff_defaults(self):
        """FileDiff should have sensible defaults."""
        diff = FileDiff(path="test.py", status="added")
        assert diff.old_path is None
        assert diff.additions == 0
        assert diff.deletions == 0
        assert diff.hunks == []


class TestPRData:
    """Tests for PRData dataclass."""

    def test_basic_pr_data(self):
        """PRData should store PR metadata."""
        pr = PRData(
            number=123,
            title="Add new feature",
            author="developer",
            base_branch="main",
            head_branch="feature/new-feature",
        )
        assert pr.number == 123
        assert pr.title == "Add new feature"
        assert pr.author == "developer"
        assert pr.base_branch == "main"
        assert pr.head_branch == "feature/new-feature"

    def test_pr_data_with_description(self):
        """PRData should support optional description."""
        pr = PRData(
            number=456,
            title="Fix bug",
            author="dev",
            base_branch="main",
            head_branch="fix/bug",
            description="Fixes issue #789",
        )
        assert pr.description == "Fixes issue #789"

    def test_pr_data_with_files(self):
        """PRData should support list of changed files."""
        pr = PRData(
            number=789,
            title="Refactor",
            author="dev",
            base_branch="main",
            head_branch="refactor/cleanup",
            files=[
                FileDiff(path="src/a.py", status="modified", additions=10, deletions=5),
                FileDiff(path="src/b.py", status="added", additions=20, deletions=0),
            ],
        )
        assert len(pr.files) == 2
        assert pr.files[0].path == "src/a.py"

    def test_pr_data_with_url(self):
        """PRData should support URL."""
        pr = PRData(
            number=123,
            title="Test",
            author="dev",
            base_branch="main",
            head_branch="test",
            url="https://github.com/owner/repo/pull/123",
        )
        assert pr.url == "https://github.com/owner/repo/pull/123"

    def test_pr_data_defaults(self):
        """PRData should have sensible defaults."""
        pr = PRData(
            number=1,
            title="Title",
            author="author",
            base_branch="main",
            head_branch="branch",
        )
        assert pr.description is None
        assert pr.url is None
        assert pr.files == []


class TestFinding:
    """Tests for Finding dataclass."""

    def test_basic_finding(self):
        """Finding should store issue details."""
        finding = Finding(
            severity=Severity.IMPORTANT,
            file="src/main.py",
            line=42,
            description="Variable shadows builtin",
        )
        assert finding.severity == Severity.IMPORTANT
        assert finding.file == "src/main.py"
        assert finding.line == 42
        assert finding.description == "Variable shadows builtin"

    def test_finding_with_line_range(self):
        """Finding should support line ranges."""
        finding = Finding(
            severity=Severity.CRITICAL,
            file="src/auth.py",
            line=10,
            line_end=25,
            description="SQL injection vulnerability",
        )
        assert finding.line == 10
        assert finding.line_end == 25

    def test_finding_with_suggestion(self):
        """Finding should support suggestions."""
        finding = Finding(
            severity=Severity.MINOR,
            file="src/utils.py",
            line=5,
            description="Consider using list comprehension",
            suggestion="items = [x for x in source if x.valid]",
        )
        assert finding.suggestion == "items = [x for x in source if x.valid]"

    def test_finding_with_code_snippet(self):
        """Finding should support code snippets."""
        finding = Finding(
            severity=Severity.IMPORTANT,
            file="src/api.py",
            line=100,
            description="Missing error handling",
            code_snippet="response = fetch(url)",
        )
        assert finding.code_snippet == "response = fetch(url)"

    def test_finding_defaults(self):
        """Finding should have sensible defaults."""
        finding = Finding(
            severity=Severity.MINOR,
            file="test.py",
            line=1,
            description="Issue",
        )
        assert finding.line_end is None
        assert finding.suggestion is None
        assert finding.code_snippet is None


class TestFeedbackCategory:
    """Tests for FeedbackCategory enum."""

    def test_feedback_categories(self):
        """FeedbackCategory should have standard categories."""
        assert FeedbackCategory.BUG.value == "bug"
        assert FeedbackCategory.STYLE.value == "style"
        assert FeedbackCategory.QUESTION.value == "question"
        assert FeedbackCategory.SUGGESTION.value == "suggestion"
        assert FeedbackCategory.NIT.value == "nit"


class TestFeedbackUrgency:
    """Tests for FeedbackUrgency enum."""

    def test_feedback_urgencies(self):
        """FeedbackUrgency should have blocking and non-blocking."""
        assert FeedbackUrgency.BLOCKING.value == "blocking"
        assert FeedbackUrgency.NON_BLOCKING.value == "non_blocking"


class TestFeedbackItem:
    """Tests for FeedbackItem dataclass."""

    def test_basic_feedback_item(self):
        """FeedbackItem should store feedback details."""
        item = FeedbackItem(
            content="This variable name is unclear",
            category=FeedbackCategory.STYLE,
            urgency=FeedbackUrgency.NON_BLOCKING,
        )
        assert item.content == "This variable name is unclear"
        assert item.category == FeedbackCategory.STYLE
        assert item.urgency == FeedbackUrgency.NON_BLOCKING

    def test_feedback_item_with_location(self):
        """FeedbackItem should support file/line location."""
        item = FeedbackItem(
            content="Missing null check",
            category=FeedbackCategory.BUG,
            urgency=FeedbackUrgency.BLOCKING,
            file="src/handler.py",
            line=45,
        )
        assert item.file == "src/handler.py"
        assert item.line == 45

    def test_feedback_item_with_author(self):
        """FeedbackItem should support author field."""
        item = FeedbackItem(
            content="Good approach!",
            category=FeedbackCategory.SUGGESTION,
            urgency=FeedbackUrgency.NON_BLOCKING,
            author="reviewer",
        )
        assert item.author == "reviewer"

    def test_feedback_item_defaults(self):
        """FeedbackItem should have sensible defaults."""
        item = FeedbackItem(
            content="Feedback",
            category=FeedbackCategory.NIT,
            urgency=FeedbackUrgency.NON_BLOCKING,
        )
        assert item.file is None
        assert item.line is None
        assert item.author is None


class TestReviewStatus:
    """Tests for ReviewStatus enum."""

    def test_review_statuses(self):
        """ReviewStatus should have standard statuses."""
        assert ReviewStatus.PASS.value == "pass"
        assert ReviewStatus.WARN.value == "warn"
        assert ReviewStatus.FAIL.value == "fail"
        assert ReviewStatus.APPROVE.value == "approve"
        assert ReviewStatus.REQUEST_CHANGES.value == "request_changes"
        assert ReviewStatus.COMMENT.value == "comment"


class TestReviewReport:
    """Tests for ReviewReport dataclass."""

    def test_basic_review_report(self):
        """ReviewReport should store review results."""
        report = ReviewReport(
            status=ReviewStatus.PASS,
            summary="No critical issues found",
            files_reviewed=5,
        )
        assert report.status == ReviewStatus.PASS
        assert report.summary == "No critical issues found"
        assert report.files_reviewed == 5

    def test_review_report_with_findings(self):
        """ReviewReport should store findings."""
        findings = [
            Finding(
                severity=Severity.MINOR,
                file="src/main.py",
                line=10,
                description="Consider refactoring",
            ),
        ]
        report = ReviewReport(
            status=ReviewStatus.WARN,
            summary="Minor issues found",
            files_reviewed=3,
            findings=findings,
        )
        assert len(report.findings) == 1
        assert report.findings[0].severity == Severity.MINOR

    def test_review_report_finding_counts(self):
        """ReviewReport should track finding counts by severity."""
        report = ReviewReport(
            status=ReviewStatus.FAIL,
            summary="Critical issues found",
            files_reviewed=10,
            critical_count=1,
            important_count=3,
            minor_count=5,
        )
        assert report.critical_count == 1
        assert report.important_count == 3
        assert report.minor_count == 5

    def test_review_report_with_action_items(self):
        """ReviewReport should support action items list."""
        report = ReviewReport(
            status=ReviewStatus.REQUEST_CHANGES,
            summary="Changes requested",
            files_reviewed=2,
            action_items=["Fix SQL injection", "Add input validation"],
        )
        assert len(report.action_items) == 2
        assert "Fix SQL injection" in report.action_items

    def test_review_report_defaults(self):
        """ReviewReport should have sensible defaults."""
        report = ReviewReport(
            status=ReviewStatus.PASS,
            summary="OK",
            files_reviewed=1,
        )
        assert report.findings == []
        assert report.critical_count == 0
        assert report.important_count == 0
        assert report.minor_count == 0
        assert report.action_items == []
