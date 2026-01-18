"""Tests for pr_distill type definitions."""

from spellbook_mcp.pr_distill.types import (
    DiffLine,
    Hunk,
    FileDiff,
    PatternDefinition,
    PatternMatch,
)


class TestDiffLine:
    def test_add_line(self):
        line: DiffLine = {
            "type": "add",
            "content": "new code",
            "old_line_num": None,
            "new_line_num": 10,
        }
        assert line["type"] == "add"
        assert line["new_line_num"] == 10

    def test_remove_line(self):
        line: DiffLine = {
            "type": "remove",
            "content": "old code",
            "old_line_num": 5,
            "new_line_num": None,
        }
        assert line["type"] == "remove"
        assert line["old_line_num"] == 5

    def test_context_line(self):
        line: DiffLine = {
            "type": "context",
            "content": "unchanged",
            "old_line_num": 3,
            "new_line_num": 3,
        }
        assert line["type"] == "context"


class TestHunk:
    def test_hunk_structure(self):
        hunk: Hunk = {
            "old_start": 10,
            "old_count": 5,
            "new_start": 10,
            "new_count": 7,
            "lines": [],
        }
        assert hunk["old_start"] == 10
        assert hunk["new_count"] == 7


class TestFileDiff:
    def test_added_file(self):
        fd: FileDiff = {
            "path": "src/new.py",
            "old_path": None,
            "status": "added",
            "hunks": [],
            "additions": 10,
            "deletions": 0,
        }
        assert fd["status"] == "added"

    def test_renamed_file(self):
        fd: FileDiff = {
            "path": "src/new_name.py",
            "old_path": "src/old_name.py",
            "status": "renamed",
            "hunks": [],
            "additions": 1,
            "deletions": 1,
        }
        assert fd["old_path"] == "src/old_name.py"


class TestPatternDefinition:
    def test_pattern_with_file_match(self):
        pattern: PatternDefinition = {
            "id": "migration-file",
            "confidence": 15,
            "default_category": "REVIEW_REQUIRED",
            "description": "Database migrations",
            "priority": "always_review",
            "match_file": r"/migrations/.*\.py$",
            "match_line": None,
        }
        assert pattern["priority"] == "always_review"


class TestPatternMatch:
    def test_pattern_match(self):
        match: PatternMatch = {
            "pattern_id": "migration-file",
            "confidence": 15,
            "matched_files": ["migrations/0001.py"],
            "matched_lines": [],
            "first_occurrence_file": "migrations/0001.py",
        }
        assert match["pattern_id"] == "migration-file"
