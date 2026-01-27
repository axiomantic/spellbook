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

    # Check explicit continue patterns (high confidence, no session required)
    for pattern in EXPLICIT_CONTINUE_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE):
            return ContinuationIntent(
                intent="continue",
                confidence="high",
                pattern=pattern,
            )

    return ContinuationIntent(
        intent="neutral",
        confidence="low",
        pattern=None,
    )
