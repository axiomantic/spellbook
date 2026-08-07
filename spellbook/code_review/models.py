"""Data models for code-review skill."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Severity levels for review findings.

    Unified on the seven-level review vocabulary shared with the
    advanced-code-review skill and its phase commands. The members here must
    agree key for key with that skill's ``SEVERITY_ORDER`` dict; a member
    missing here makes ``Severity(<value>)`` raise on JSON ingestion of a
    finding the skill considers legal.

    Ordering: CRITICAL > HIGH > MEDIUM > LOW > NIT > QUESTION > PRAISE
    - CRITICAL: Data loss, security vulnerabilities, production outage
    - HIGH: Bugs and broken functionality. Bugs are HIGH, never CRITICAL.
    - MEDIUM: Quality concern, technical debt
    - LOW: Minor improvement, optimization
    - NIT: Purely stylistic
    - QUESTION: Needs author input before a judgment can be made
    - PRAISE: Noteworthy positive

    ``QUESTION`` also exists as a :class:`FeedbackCategory` member. They are
    distinct enums serving distinct axes (severity vs. category) and neither
    substitutes for the other.

    IMPORTANT and MINOR are retained as ALIASES of HIGH and LOW so existing
    ``Severity.IMPORTANT`` / ``Severity.MINOR`` call sites keep working. Being
    aliases, they resolve to the canonical member: ``Severity.MINOR.name`` is
    ``"LOW"`` and ``Severity.MINOR.value`` is ``"low"``.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NIT = "nit"
    QUESTION = "question"
    PRAISE = "praise"

    # Back-compat aliases (not distinct members). The duplicate values are the
    # mechanism that makes them aliases, so PIE796 is suppressed deliberately.
    IMPORTANT = "high"  # noqa: PIE796
    MINOR = "low"  # noqa: PIE796


class FeedbackCategory(Enum):
    """Categories for feedback items.

    - BUG: Actual bug or incorrect behavior
    - STYLE: Style/formatting issues
    - QUESTION: Clarification needed
    - SUGGESTION: Improvement idea
    - NIT: Minor nitpick
    """

    BUG = "bug"
    STYLE = "style"
    QUESTION = "question"
    SUGGESTION = "suggestion"
    NIT = "nit"


class FeedbackUrgency(Enum):
    """Urgency levels for feedback.

    - BLOCKING: Must address before merge
    - NON_BLOCKING: Nice to address but not required
    """

    BLOCKING = "blocking"
    NON_BLOCKING = "non_blocking"


class ReviewStatus(Enum):
    """Status of a code review.

    Self-review statuses:
    - PASS: No critical issues
    - WARN: Has important issues
    - FAIL: Has critical issues

    Give-review statuses:
    - APPROVE: Ready to merge
    - REQUEST_CHANGES: Blocking issues
    - COMMENT: Non-blocking feedback only
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    COMMENT = "comment"


@dataclass
class FileDiff:
    """Represents a diff for a single file.

    Attributes:
        path: Current file path
        status: File status (added, modified, deleted, renamed)
        additions: Number of lines added
        deletions: Number of lines deleted
        old_path: Previous path for renamed files
        hunks: List of diff hunks with detailed line info
        binary: True if this is a binary file (cannot be meaningfully diffed)
    """

    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    old_path: str | None = None
    hunks: list[dict[str, Any]] = field(default_factory=list)
    binary: bool = False


@dataclass
class PRData:
    """Pull request metadata and content.

    Attributes:
        number: PR number
        title: PR title
        author: PR author username
        base_branch: Target branch (e.g., main)
        head_branch: Source branch
        description: PR body/description
        url: Full URL to PR
        files: List of file diffs
    """

    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    description: str | None = None
    url: str | None = None
    files: list[FileDiff] = field(default_factory=list)


@dataclass
class Finding:
    """A single review finding/issue.

    Attributes:
        severity: Issue severity level
        file: File path where issue was found
        line: Starting line number
        description: What's wrong and why
        line_end: Ending line number for ranges
        suggestion: How to fix (code or description)
        code_snippet: Relevant code from the file
    """

    severity: Severity
    file: str
    line: int
    description: str
    line_end: int | None = None
    suggestion: str | None = None
    code_snippet: str | None = None


@dataclass
class FeedbackItem:
    """A single piece of feedback from a reviewer.

    Attributes:
        content: The feedback text
        category: Type of feedback
        urgency: Whether blocking or not
        file: File the feedback relates to
        line: Line number if applicable
        author: Who gave the feedback
    """

    content: str
    category: FeedbackCategory
    urgency: FeedbackUrgency
    file: str | None = None
    line: int | None = None
    author: str | None = None


@dataclass
class ReviewReport:
    """Complete review report with findings and status.

    Attributes:
        status: Overall review status
        summary: Executive summary
        files_reviewed: Number of files reviewed
        findings: List of individual findings
        critical_count: Number of CRITICAL findings
        important_count: Number of HIGH findings (IMPORTANT is an alias of HIGH)
        minor_count: Number of LOW findings (MINOR is an alias of LOW)
        action_items: Prioritized list of things to fix
    """

    status: ReviewStatus
    summary: str
    files_reviewed: int
    findings: list[Finding] = field(default_factory=list)
    critical_count: int = 0
    important_count: int = 0
    minor_count: int = 0
    action_items: list[str] = field(default_factory=list)
