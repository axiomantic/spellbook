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
