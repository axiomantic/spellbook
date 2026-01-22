"""Skill selection algorithm for Forged autonomous development.

This module provides intelligent skill selection based on current context,
feedback history, and workflow stage to ensure appropriate skills are
invoked at each step of the autonomous development process.

Selection Priority Order:
1. Handle errors/failures (test errors -> fixing-tests, merge errors -> merge-conflict-resolution)
2. Handle feedback type (code_quality -> receiving-code-review, factual_accuracy -> fact-checking)
3. Stage-based default (DISCOVER -> requirements-gathering, DESIGN -> brainstorming, etc.)
"""

from typing import Optional

from spellbook_mcp.forged.models import IterationState, Feedback


# Stage to default skill mapping
STAGE_DEFAULT_SKILLS = {
    "DISCOVER": "requirements-gathering",
    "DESIGN": "brainstorming",
    "PLAN": "writing-plans",
    "IMPLEMENT": "implementing-features",
    "COMPLETE": None,  # No skill needed for complete
    "ESCALATED": None,  # Manual intervention required
}

# Feedback classification to skill mapping
FEEDBACK_SKILL_MAPPING = {
    "test_failure": "fixing-tests",
    "merge_conflict": "merge-conflict-resolution",
    "code_quality": "receiving-code-review",
    "factual_accuracy": "fact-checking",
}

# Keywords for feedback classification
_TEST_FAILURE_KEYWORDS = [
    "test", "tests", "failed", "failing", "failure", "pytest",
    "unittest", "assertion", "assert"
]

_MERGE_CONFLICT_KEYWORDS = [
    "merge", "conflict", "rebase", "unmerged", "conflicting",
    "<<<<<<", "======", ">>>>>>"
]

_CODE_QUALITY_KEYWORDS = [
    "lint", "style", "format", "type", "typing", "mypy",
    "pylint", "flake8", "ruff", "eslint", "prettier"
]

_FACTUAL_ACCURACY_KEYWORDS = [
    "incorrect", "wrong", "false", "inaccurate", "assumption",
    "verify", "fact", "accuracy", "api", "documentation"
]


def classify_feedback(feedback_list: list[Feedback]) -> Optional[str]:
    """Classify feedback to determine appropriate skill.

    Analyzes feedback to determine the type of issue and returns
    a classification string that maps to a skill.

    Args:
        feedback_list: List of Feedback objects to analyze

    Returns:
        Classification string (test_failure, merge_conflict, code_quality,
        factual_accuracy) or None if no clear classification
    """
    if not feedback_list:
        return None

    # Sort by severity (blocking first, then significant, then minor)
    severity_order = {"blocking": 0, "significant": 1, "minor": 2}
    sorted_feedback = sorted(
        feedback_list,
        key=lambda f: severity_order.get(f.severity, 99)
    )

    # Check each feedback item for classification, prioritizing by severity
    for feedback in sorted_feedback:
        # Combine source, critique, and evidence for keyword matching
        text = " ".join([
            feedback.source.lower(),
            feedback.critique.lower(),
            feedback.evidence.lower(),
        ])

        # Check for test failures first (highest priority)
        if any(kw in text for kw in _TEST_FAILURE_KEYWORDS):
            return "test_failure"

        # Check for merge conflicts
        if any(kw in text for kw in _MERGE_CONFLICT_KEYWORDS):
            return "merge_conflict"

        # Check for code quality issues
        if any(kw in text for kw in _CODE_QUALITY_KEYWORDS):
            return "code_quality"

        # Check for factual accuracy issues
        if any(kw in text for kw in _FACTUAL_ACCURACY_KEYWORDS):
            return "factual_accuracy"

    return None


def select_skill(context: IterationState) -> str:
    """Select the appropriate skill based on current context.

    Uses a priority-based selection:
    1. If there's feedback, classify it and select corresponding skill
    2. Fall back to stage-based default skill

    Args:
        context: Current iteration state with stage and feedback history

    Returns:
        Name of the skill to invoke
    """
    # Priority 1: Check for error/feedback that needs specific handling
    if context.feedback_history:
        classification = classify_feedback(context.feedback_history)
        if classification and classification in FEEDBACK_SKILL_MAPPING:
            return FEEDBACK_SKILL_MAPPING[classification]

    # Priority 2: Stage-based default
    default_skill = STAGE_DEFAULT_SKILLS.get(context.current_stage)
    if default_skill:
        return default_skill

    # Fallback for unknown stages
    return "implementing-features"
