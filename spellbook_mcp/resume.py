"""Session resume detection and boot prompt generation."""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class ContinuationIntent(TypedDict):
    """Result of continuation intent detection.

    Attributes:
        intent: One of "continue", "fresh_start", or "neutral"
        confidence: One of "high", "medium", or "low"
        pattern: The regex pattern that matched, or None if no match
    """
    intent: str
    confidence: str
    pattern: Optional[str]


class ResumeFields(TypedDict, total=False):
    """Flattened resume fields for session_init response.

    All fields except resume_available are optional.
    """
    resume_available: bool
    resume_session_id: Optional[str]
    resume_age_hours: Optional[float]
    resume_bound_at: Optional[str]
    resume_active_skill: Optional[str]
    resume_skill_phase: Optional[str]
    resume_pending_todos: Optional[int]
    resume_todos_corrupted: Optional[bool]
    resume_workflow_pattern: Optional[str]
    resume_boot_prompt: Optional[str]


# Fresh start patterns (highest priority, override resume)
FRESH_START_PATTERNS = [
    r"^(start|begin)\s+(fresh|new|over)",
    r"^new\s+(session|task|project)",
    r"^forget\s+(previous|last|prior)",
    r"^clean\s+slate",
    r"^from\s+(scratch|beginning)",
]

# Explicit continue patterns (high confidence, match without recent session)
EXPLICIT_CONTINUE_PATTERNS = [
    r"^\s*continue\s*$",
    r"^\s*resume\s*$",
    r"^where\s+were\s+we",
    r"^pick\s+up\s+where",
    r"^let'?s\s+continue",
    r"^carry\s+on",
    r"^what\s+were\s+we\s+(doing|working)",
    r"^back\s+to\s+(it|work)",
]

# Implicit continue patterns (require recent session for medium confidence)
IMPLICIT_CONTINUE_PATTERNS = [
    r"^(ok|okay|alright|sure|ready|go)[\s,\.!]*$",
    r"^next\s*(step|task|item)?[\s,\.!]*$",
    r"^and\s+then",
    r"^also[,\s]",
]


def detect_continuation_intent(
    first_message: str,
    has_recent_session: bool
) -> ContinuationIntent:
    """Detect user's continuation intent from first message.

    Args:
        first_message: The user's first message in the session
        has_recent_session: Whether a recent (<24h) resumable session exists

    Returns:
        ContinuationIntent with intent, confidence, and matched pattern
    """
    msg = first_message.strip().lower()

    # Check fresh start patterns first (highest priority)
    for pattern in FRESH_START_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE):
            return ContinuationIntent(
                intent="fresh_start",
                confidence="high",
                pattern=pattern,
            )

    # Check explicit continue patterns (high confidence, no session required)
    for pattern in EXPLICIT_CONTINUE_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE):
            return ContinuationIntent(
                intent="continue",
                confidence="high",
                pattern=pattern,
            )

    # Check implicit patterns only if recent session exists
    if has_recent_session:
        for pattern in IMPLICIT_CONTINUE_PATTERNS:
            if re.match(pattern, msg, re.IGNORECASE):
                return ContinuationIntent(
                    intent="continue",
                    confidence="medium",
                    pattern=pattern,
                )

    return ContinuationIntent(
        intent="neutral",
        confidence="low",
        pattern=None,
    )


def count_pending_todos(todos_json: Optional[str]) -> tuple[int, bool]:
    """Count non-completed todos from JSON.

    Args:
        todos_json: JSON string of todos array, or None

    Returns:
        Tuple of (count, is_corrupted):
        - count: Number of pending todos (0 if corrupted or None)
        - is_corrupted: True if JSON was present but malformed
    """
    if todos_json is None:
        return (0, False)

    try:
        todos = json.loads(todos_json)
        if not isinstance(todos, list):
            return (0, True)  # Not an array
        pending = sum(
            1 for t in todos
            if isinstance(t, dict) and t.get("status") != "completed"
        )
        return (pending, False)
    except json.JSONDecodeError:
        return (0, True)


def _find_planning_docs(recent_files: list[str]) -> list[str]:
    """Extract planning documents from recent files.

    Looks for files matching patterns:
    - *-impl.md, *-design.md, *-plan.md
    - Files in plans/ directories

    Only includes files that still exist.

    Args:
        recent_files: List of recently accessed file paths

    Returns:
        List of existing planning doc paths (max 3)
    """
    plan_patterns = [
        r".*-impl\.md$",
        r".*-design\.md$",
        r".*-plan\.md$",
        r".*/plans/.*\.md$",
    ]

    docs = []
    missing = []

    for f in recent_files:
        for pattern in plan_patterns:
            if re.match(pattern, f):
                if os.path.exists(f):
                    docs.append(f)
                else:
                    missing.append(f)
                break

    if missing:
        logger.warning(f"Planning docs no longer exist: {missing}")

    return docs[:3]  # Limit to 3 docs
