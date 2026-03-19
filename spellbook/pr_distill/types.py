"""Type definitions for PR distillation."""

from typing import TypedDict, Literal, Optional


class DiffLine(TypedDict):
    """A single line in a diff hunk."""
    type: Literal["add", "remove", "context"]
    content: str
    old_line_num: Optional[int]
    new_line_num: Optional[int]


class Hunk(TypedDict):
    """A contiguous changed section in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine]


class FileDiff(TypedDict):
    """A file's complete diff information."""
    path: str
    old_path: Optional[str]
    status: Literal["added", "modified", "deleted", "renamed"]
    hunks: list[Hunk]
    additions: int
    deletions: int


class PatternDefinition(TypedDict):
    """A heuristic pattern for categorizing changes."""
    id: str
    confidence: int
    default_category: str
    description: str
    priority: Literal["always_review", "high", "medium"]
    match_file: Optional[str]
    match_line: Optional[str]


class PatternMatch(TypedDict):
    """Result of matching a pattern against files."""
    pattern_id: str
    confidence: int
    matched_files: list[str]
    matched_lines: list[tuple[str, int]]
    first_occurrence_file: str
