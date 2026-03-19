"""Builtin heuristic patterns for PR change analysis.

Patterns are matched in precedence order: always_review > high > medium.
Ported from lib/pr-distill/patterns.js.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class Pattern:
    """A heuristic pattern for categorizing changes."""
    id: str
    confidence: int
    default_category: str
    description: str
    priority: str  # "always_review" | "high" | "medium"
    match_file: Optional[re.Pattern] = None
    match_line: Optional[re.Pattern] = None


# ALWAYS REVIEW patterns (confidence 10-25, REVIEW_REQUIRED)
ALWAYS_REVIEW_PATTERNS = [
    Pattern(
        id="migration-file",
        confidence=15,
        default_category="REVIEW_REQUIRED",
        description="Database migration files require careful review for schema safety",
        priority="always_review",
        match_file=re.compile(r"/migrations/.*\.py$"),
    ),
    Pattern(
        id="permission-change",
        confidence=20,
        default_category="REVIEW_REQUIRED",
        description="Permission or authorization changes require security review",
        priority="always_review",
        match_line=re.compile(r"Permission|permission_classes"),
    ),
    Pattern(
        id="model-change",
        confidence=15,
        default_category="REVIEW_REQUIRED",
        description="Model changes can affect database schema and data integrity",
        priority="always_review",
        match_file=re.compile(r"models\.py$"),
    ),
    Pattern(
        id="signal-handler",
        confidence=20,
        default_category="REVIEW_REQUIRED",
        description="Signal handlers have implicit side effects that need careful review",
        priority="always_review",
        match_line=re.compile(r"@receiver|Signal\("),
    ),
    Pattern(
        id="endpoint-change",
        confidence=25,
        default_category="REVIEW_REQUIRED",
        description="API endpoint changes can affect external consumers",
        priority="always_review",
        match_file=re.compile(r"urls\.py$|views\.py$"),
    ),
    Pattern(
        id="settings-change",
        confidence=10,
        default_category="REVIEW_REQUIRED",
        description="Settings changes can affect application behavior globally",
        priority="always_review",
        match_file=re.compile(r"/settings/"),
    ),
]

# HIGH CONFIDENCE patterns (confidence 95, SAFE_TO_SKIP)
HIGH_CONFIDENCE_PATTERNS = [
    Pattern(
        id="query-count-json",
        confidence=95,
        default_category="SAFE_TO_SKIP",
        description="Query count snapshots are auto-generated test artifacts",
        priority="high",
        match_file=re.compile(r"/query-counts/.*-query-counts\.json$"),
    ),
    Pattern(
        id="debug-print-removal",
        confidence=95,
        default_category="SAFE_TO_SKIP",
        description="Matches lines containing print statements",
        priority="high",
        match_line=re.compile(r"^\s*print\("),
    ),
    Pattern(
        id="import-cleanup",
        confidence=95,
        default_category="SAFE_TO_SKIP",
        description="Matches lines containing import statements",
        priority="high",
        match_line=re.compile(r"^(import |from .+ import )"),
    ),
    Pattern(
        id="gitignore-addition",
        confidence=95,
        default_category="SAFE_TO_SKIP",
        description="Matches changes to .gitignore files",
        priority="high",
        match_file=re.compile(r"\.gitignore$"),
    ),
    Pattern(
        id="backfill-command-deletion",
        confidence=95,
        default_category="SAFE_TO_SKIP",
        description="Matches changes to management command files",
        priority="high",
        match_file=re.compile(r"/management/commands/"),
    ),
]

# MEDIUM CONFIDENCE patterns (confidence 70-85, LIKELY_SKIP)
MEDIUM_CONFIDENCE_PATTERNS = [
    Pattern(
        id="decorator-removal",
        confidence=75,
        default_category="LIKELY_SKIP",
        description="Matches lines containing decorator syntax",
        priority="medium",
        match_line=re.compile(r"^\s*@\w+"),
    ),
    Pattern(
        id="factory-setup",
        confidence=80,
        default_category="LIKELY_SKIP",
        description="Matches lines containing Factory calls (typically test setup)",
        priority="medium",
        match_line=re.compile(r"Factory\("),
    ),
    Pattern(
        id="test-rename",
        confidence=70,
        default_category="LIKELY_SKIP",
        description="Matches lines containing test function definitions",
        priority="medium",
        match_line=re.compile(r"^\s*def test_"),
    ),
    Pattern(
        id="test-assertion-addition",
        confidence=85,
        default_category="LIKELY_SKIP",
        description="Matches lines containing test assertions",
        priority="medium",
        match_line=re.compile(r"assert_|self\.assert"),
    ),
]

# All builtin patterns, sorted by priority
BUILTIN_PATTERNS: list[Pattern] = (
    ALWAYS_REVIEW_PATTERNS +
    HIGH_CONFIDENCE_PATTERNS +
    MEDIUM_CONFIDENCE_PATTERNS
)


def get_pattern_by_id(pattern_id: str) -> Optional[Pattern]:
    """Look up pattern by ID."""
    for pattern in BUILTIN_PATTERNS:
        if pattern.id == pattern_id:
            return pattern
    return None


def get_all_pattern_ids() -> list[str]:
    """Get all builtin pattern IDs."""
    return [p.id for p in BUILTIN_PATTERNS]
