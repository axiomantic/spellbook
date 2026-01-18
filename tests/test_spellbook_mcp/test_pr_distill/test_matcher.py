"""Tests for pr_distill pattern matching."""

import re
import pytest

from spellbook_mcp.pr_distill.matcher import (
    check_pattern_match,
    match_patterns,
    sort_patterns_by_precedence,
)
from spellbook_mcp.pr_distill.patterns import Pattern
from spellbook_mcp.pr_distill.types import FileDiff, Hunk, DiffLine


def make_file_diff(
    path: str,
    status: str = "modified",
    hunks: list[Hunk] = None,
) -> FileDiff:
    """Helper to create FileDiff test fixtures."""
    return FileDiff(
        path=path,
        old_path=None,
        status=status,
        hunks=hunks or [],
        additions=0,
        deletions=0,
    )


def make_hunk_with_lines(lines: list[tuple[str, str]]) -> Hunk:
    """Create a hunk with specified lines. lines = [(type, content), ...]"""
    diff_lines = []
    old_num = 1
    new_num = 1
    for line_type, content in lines:
        if line_type == "add":
            diff_lines.append(DiffLine(
                type="add",
                content=content,
                old_line_num=None,
                new_line_num=new_num,
            ))
            new_num += 1
        elif line_type == "remove":
            diff_lines.append(DiffLine(
                type="remove",
                content=content,
                old_line_num=old_num,
                new_line_num=None,
            ))
            old_num += 1
        else:
            diff_lines.append(DiffLine(
                type="context",
                content=content,
                old_line_num=old_num,
                new_line_num=new_num,
            ))
            old_num += 1
            new_num += 1

    return Hunk(
        old_start=1,
        old_count=old_num - 1,
        new_start=1,
        new_count=new_num - 1,
        lines=diff_lines,
    )


class TestCheckPatternMatch:
    """Test the check_pattern_match function."""

    def test_file_pattern_match(self):
        """Pattern matches by file path."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        file = make_file_diff("src/main.py")

        result = check_pattern_match(pattern, file)

        assert result is not None
        assert result["lines"] == []

    def test_file_pattern_no_match(self):
        """Pattern doesn't match non-matching file path."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        file = make_file_diff("src/main.js")

        result = check_pattern_match(pattern, file)

        assert result is None

    def test_line_pattern_match(self):
        """Pattern matches by line content."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_line=re.compile(r"print\("),
        )
        hunk = make_hunk_with_lines([
            ("add", "print('hello')"),
            ("context", "other line"),
        ])
        file = make_file_diff("file.py", hunks=[hunk])

        result = check_pattern_match(pattern, file)

        assert result is not None
        assert len(result["lines"]) == 1
        assert result["lines"][0] == ("file.py", 1)

    def test_line_pattern_only_matches_add_remove(self):
        """Line patterns only match add/remove lines, not context."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_line=re.compile(r"print\("),
        )
        hunk = make_hunk_with_lines([
            ("context", "print('context')"),  # Should not match
        ])
        file = make_file_diff("file.py", hunks=[hunk])

        result = check_pattern_match(pattern, file)

        assert result is None

    def test_line_pattern_no_match(self):
        """Pattern doesn't match if line content doesn't match."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_line=re.compile(r"print\("),
        )
        hunk = make_hunk_with_lines([
            ("add", "console.log('hello')"),
        ])
        file = make_file_diff("file.py", hunks=[hunk])

        result = check_pattern_match(pattern, file)

        assert result is None

    def test_file_and_line_pattern(self):
        """Pattern with both file and line constraints."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_file=re.compile(r"\.py$"),
            match_line=re.compile(r"print\("),
        )

        # Matching file, matching line
        hunk = make_hunk_with_lines([("add", "print('hi')")])
        file1 = make_file_diff("test.py", hunks=[hunk])
        assert check_pattern_match(pattern, file1) is not None

        # Non-matching file
        file2 = make_file_diff("test.js", hunks=[hunk])
        assert check_pattern_match(pattern, file2) is None

        # Matching file, non-matching line
        hunk2 = make_hunk_with_lines([("add", "console.log('hi')")])
        file3 = make_file_diff("test.py", hunks=[hunk2])
        assert check_pattern_match(pattern, file3) is None

    def test_removed_line_uses_old_line_num(self):
        """Removed lines report old_line_num in match."""
        pattern = Pattern(
            id="test-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test pattern",
            priority="high",
            match_line=re.compile(r"print\("),
        )
        hunk = make_hunk_with_lines([
            ("remove", "print('removed')"),
        ])
        file = make_file_diff("file.py", hunks=[hunk])

        result = check_pattern_match(pattern, file)

        assert result is not None
        assert len(result["lines"]) == 1
        # For removed lines, we use old_line_num
        assert result["lines"][0] == ("file.py", 1)


class TestSortPatternsByPrecedence:
    """Test pattern precedence sorting."""

    def test_always_review_first(self):
        """always_review patterns come before high and medium."""
        always_review = Pattern(
            id="always",
            confidence=10,
            default_category="REVIEW_REQUIRED",
            description="Always review",
            priority="always_review",
            match_file=re.compile(r".*"),
        )
        high = Pattern(
            id="high",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="High",
            priority="high",
            match_file=re.compile(r".*"),
        )
        medium = Pattern(
            id="medium",
            confidence=70,
            default_category="LIKELY_SKIP",
            description="Medium",
            priority="medium",
            match_file=re.compile(r".*"),
        )

        # Pass patterns in wrong order
        result = sort_patterns_by_precedence(
            patterns=[medium, high, always_review],
            blessed_pattern_ids=[],
        )

        assert result[0].id == "always"
        assert result[1].id == "high"
        assert result[2].id == "medium"

    def test_blessed_patterns_elevated(self):
        """Blessed patterns come after always_review but before other high."""
        always_review = Pattern(
            id="always",
            confidence=10,
            default_category="REVIEW_REQUIRED",
            description="Always review",
            priority="always_review",
            match_file=re.compile(r".*"),
        )
        high = Pattern(
            id="high",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="High",
            priority="high",
            match_file=re.compile(r".*"),
        )
        medium_blessed = Pattern(
            id="blessed-medium",
            confidence=70,
            default_category="LIKELY_SKIP",
            description="Medium (blessed)",
            priority="medium",
            match_file=re.compile(r".*"),
        )

        result = sort_patterns_by_precedence(
            patterns=[high, medium_blessed, always_review],
            blessed_pattern_ids=["blessed-medium"],
        )

        # Order: always_review, blessed, high
        assert result[0].id == "always"
        assert result[1].id == "blessed-medium"
        assert result[2].id == "high"


class TestMatchPatterns:
    """Test the main pattern matching function."""

    def test_single_file_single_pattern(self):
        """Match a single file against a single pattern."""
        pattern = Pattern(
            id="py-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Python files",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        files = [make_file_diff("main.py")]

        result = match_patterns(files, [pattern])

        assert len(result["matched"]) == 1
        assert "py-files" in result["matched"]
        match = result["matched"]["py-files"]
        assert match["pattern_id"] == "py-files"
        assert match["confidence"] == 95
        assert "main.py" in match["matched_files"]
        assert len(result["unmatched"]) == 0

    def test_multiple_files_same_pattern(self):
        """Multiple files matching same pattern are grouped."""
        pattern = Pattern(
            id="py-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Python files",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        files = [
            make_file_diff("main.py"),
            make_file_diff("util.py"),
            make_file_diff("test.py"),
        ]

        result = match_patterns(files, [pattern])

        assert len(result["matched"]) == 1
        match = result["matched"]["py-files"]
        assert len(match["matched_files"]) == 3
        assert set(match["matched_files"]) == {"main.py", "util.py", "test.py"}

    def test_unmatched_files(self):
        """Files not matching any pattern go to unmatched."""
        pattern = Pattern(
            id="py-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Python files",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        files = [
            make_file_diff("main.py"),
            make_file_diff("script.js"),
        ]

        result = match_patterns(files, [pattern])

        assert len(result["matched"]) == 1
        assert len(result["unmatched"]) == 1
        assert result["unmatched"][0]["path"] == "script.js"

    def test_first_pattern_wins(self):
        """First matching pattern wins (precedence)."""
        pattern1 = Pattern(
            id="always-review",
            confidence=10,
            default_category="REVIEW_REQUIRED",
            description="Always review",
            priority="always_review",
            match_file=re.compile(r"\.py$"),
        )
        pattern2 = Pattern(
            id="py-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Python files",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        files = [make_file_diff("main.py")]

        result = match_patterns(files, [pattern1, pattern2])

        # File should only match first pattern
        assert len(result["matched"]) == 1
        assert "always-review" in result["matched"]
        assert "py-files" not in result["matched"]

    def test_different_files_different_patterns(self):
        """Different files can match different patterns."""
        py_pattern = Pattern(
            id="py-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Python files",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        js_pattern = Pattern(
            id="js-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="JavaScript files",
            priority="high",
            match_file=re.compile(r"\.js$"),
        )
        files = [
            make_file_diff("main.py"),
            make_file_diff("app.js"),
        ]

        result = match_patterns(files, [py_pattern, js_pattern])

        assert len(result["matched"]) == 2
        assert "py-files" in result["matched"]
        assert "js-files" in result["matched"]
        assert result["matched"]["py-files"]["matched_files"] == ["main.py"]
        assert result["matched"]["js-files"]["matched_files"] == ["app.js"]

    def test_blessed_patterns_have_precedence(self):
        """Blessed pattern_ids elevate those patterns in precedence."""
        # High priority pattern
        high_pattern = Pattern(
            id="high-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="High priority",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        # Medium priority pattern that will be blessed
        medium_pattern = Pattern(
            id="blessed-pattern",
            confidence=70,
            default_category="LIKELY_SKIP",
            description="Medium (will be blessed)",
            priority="medium",
            match_file=re.compile(r"\.py$"),
        )
        files = [make_file_diff("main.py")]

        # Without blessing, high wins
        result1 = match_patterns(files, [high_pattern, medium_pattern])
        assert "high-pattern" in result1["matched"]

        # With blessing, blessed pattern wins
        result2 = match_patterns(
            files, [high_pattern, medium_pattern],
            blessed_pattern_ids=["blessed-pattern"],
        )
        assert "blessed-pattern" in result2["matched"]
        assert "high-pattern" not in result2["matched"]

    def test_line_matches_accumulated(self):
        """Line matches from multiple hunks are accumulated."""
        pattern = Pattern(
            id="print-pattern",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Print statements",
            priority="high",
            match_line=re.compile(r"print\("),
        )
        hunk1 = make_hunk_with_lines([("add", "print('one')")])
        hunk2 = make_hunk_with_lines([("add", "print('two')")])
        file = FileDiff(
            path="test.py",
            old_path=None,
            status="modified",
            hunks=[hunk1, hunk2],
            additions=2,
            deletions=0,
        )

        result = match_patterns([file], [pattern])

        assert len(result["matched"]) == 1
        match = result["matched"]["print-pattern"]
        # Should have 2 line matches
        assert len(match["matched_lines"]) == 2

    def test_empty_files_list(self):
        """Empty files list returns empty results."""
        pattern = Pattern(
            id="test",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Test",
            priority="high",
            match_file=re.compile(r".*"),
        )

        result = match_patterns([], [pattern])

        assert result["matched"] == {}
        assert result["unmatched"] == []

    def test_no_patterns(self):
        """No patterns means all files are unmatched."""
        files = [make_file_diff("main.py")]

        result = match_patterns(files, [])

        assert result["matched"] == {}
        assert len(result["unmatched"]) == 1

    def test_first_occurrence_file_tracked(self):
        """first_occurrence_file is set to first file that matched."""
        pattern = Pattern(
            id="py-files",
            confidence=95,
            default_category="SAFE_TO_SKIP",
            description="Python files",
            priority="high",
            match_file=re.compile(r"\.py$"),
        )
        files = [
            make_file_diff("first.py"),
            make_file_diff("second.py"),
            make_file_diff("third.py"),
        ]

        result = match_patterns(files, [pattern])

        assert result["matched"]["py-files"]["first_occurrence_file"] == "first.py"
