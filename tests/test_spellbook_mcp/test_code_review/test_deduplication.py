"""Tests for code-review deduplication module."""

import pytest

from spellbook_mcp.code_review.deduplication import deduplicate_findings
from spellbook_mcp.code_review.models import Finding, Severity


class TestDeduplicateFindings:
    """Tests for deduplicate_findings function."""

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        result = deduplicate_findings([])
        assert result == []

    def test_no_duplicates(self) -> None:
        """Non-duplicated findings pass through unchanged."""
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Missing null check",
            ),
            Finding(
                severity=Severity.MINOR,
                file="bar.py",
                line=20,
                description="Style issue",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2
        assert result[0].file == "foo.py"
        assert result[1].file == "bar.py"

    def test_duplicate_same_file_line_severity(self) -> None:
        """Exact duplicates (same file, line, severity) are merged."""
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Issue A",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Issue B",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        # Messages should be concatenated
        assert "Issue A" in result[0].description
        assert "Issue B" in result[0].description

    def test_duplicate_keeps_highest_severity(self) -> None:
        """Duplicates at same location keep highest severity."""
        findings = [
            Finding(
                severity=Severity.MINOR,
                file="foo.py",
                line=10,
                description="Minor issue",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Critical issue",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].severity == Severity.CRITICAL

    def test_duplicate_keeps_first_suggestion(self) -> None:
        """Duplicates keep the first non-None suggestion."""
        findings = [
            Finding(
                severity=Severity.IMPORTANT,
                file="foo.py",
                line=10,
                description="Issue A",
                suggestion="Fix A",
            ),
            Finding(
                severity=Severity.IMPORTANT,
                file="foo.py",
                line=10,
                description="Issue B",
                suggestion="Fix B",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].suggestion == "Fix A"

    def test_duplicate_uses_later_suggestion_if_first_none(self) -> None:
        """If first finding has no suggestion, use the later one."""
        findings = [
            Finding(
                severity=Severity.IMPORTANT,
                file="foo.py",
                line=10,
                description="Issue A",
                suggestion=None,
            ),
            Finding(
                severity=Severity.IMPORTANT,
                file="foo.py",
                line=10,
                description="Issue B",
                suggestion="Fix B",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].suggestion == "Fix B"

    def test_different_files_not_duplicates(self) -> None:
        """Same line number but different files are not duplicates."""
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Issue in foo",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="bar.py",
                line=10,
                description="Issue in bar",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_different_lines_not_duplicates(self) -> None:
        """Same file but different lines are not duplicates."""
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Issue at line 10",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=20,
                description="Issue at line 20",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_severity_ordering_critical_highest(self) -> None:
        """CRITICAL > IMPORTANT > MINOR for severity ordering."""
        findings = [
            Finding(
                severity=Severity.MINOR,
                file="foo.py",
                line=10,
                description="Minor",
            ),
            Finding(
                severity=Severity.IMPORTANT,
                file="foo.py",
                line=10,
                description="Important",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Critical",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].severity == Severity.CRITICAL

    def test_preserves_code_snippet(self) -> None:
        """Code snippet from first finding is preserved."""
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Issue A",
                code_snippet="def foo():",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Issue B",
                code_snippet="def bar():",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].code_snippet == "def foo():"

    def test_preserves_line_end(self) -> None:
        """Line end from first finding is preserved."""
        findings = [
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                line_end=15,
                description="Issue A",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                line_end=20,
                description="Issue B",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].line_end == 15

    def test_complex_scenario(self) -> None:
        """Complex scenario with multiple duplicates and non-duplicates."""
        findings = [
            # Group 1: foo.py line 10 (3 findings)
            Finding(
                severity=Severity.MINOR,
                file="foo.py",
                line=10,
                description="Style issue",
            ),
            Finding(
                severity=Severity.CRITICAL,
                file="foo.py",
                line=10,
                description="Security bug",
                suggestion="Fix security",
            ),
            Finding(
                severity=Severity.IMPORTANT,
                file="foo.py",
                line=10,
                description="Performance issue",
            ),
            # Group 2: foo.py line 20 (1 finding)
            Finding(
                severity=Severity.MINOR,
                file="foo.py",
                line=20,
                description="Another style issue",
            ),
            # Group 3: bar.py line 10 (2 findings)
            Finding(
                severity=Severity.IMPORTANT,
                file="bar.py",
                line=10,
                description="Bug A",
            ),
            Finding(
                severity=Severity.IMPORTANT,
                file="bar.py",
                line=10,
                description="Bug B",
            ),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 3

        # Find each group's result
        foo_10 = next(f for f in result if f.file == "foo.py" and f.line == 10)
        foo_20 = next(f for f in result if f.file == "foo.py" and f.line == 20)
        bar_10 = next(f for f in result if f.file == "bar.py" and f.line == 10)

        # foo.py line 10: should be CRITICAL with merged descriptions
        assert foo_10.severity == Severity.CRITICAL
        assert "Style issue" in foo_10.description
        assert "Security bug" in foo_10.description
        assert "Performance issue" in foo_10.description
        assert foo_10.suggestion == "Fix security"

        # foo.py line 20: unchanged
        assert foo_20.severity == Severity.MINOR
        assert foo_20.description == "Another style issue"

        # bar.py line 10: merged
        assert bar_10.severity == Severity.IMPORTANT
        assert "Bug A" in bar_10.description
        assert "Bug B" in bar_10.description
