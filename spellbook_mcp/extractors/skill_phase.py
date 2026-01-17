"""Extract skill phase from session transcript.

Scans messages for implementing-features skill invocations and tracks
the highest phase reached based on assistant output patterns.
"""

import re
from typing import Any, Dict, List, Optional

from spellbook_mcp.extractors.types import SkillPhase

# Phase patterns to detect in assistant messages
# Order matters - later phases should have higher indices
# Patterns match the implementing-features skill phases
PHASE_PATTERNS = [
    # Phase 0: Configuration Wizard
    (r"Phase\s+0[:\s]+Configuration(?:\s+Wizard)?", "Phase 0: Configuration Wizard"),
    # Phase 1: Research (use negative lookahead to avoid matching 1.5)
    (r"Phase\s+1(?!\.)[:\s]+Research", "Phase 1: Research"),
    # Phase 1.5: Informed Discovery
    (r"Phase\s+1\.5[:\s]+Informed\s+Discovery", "Phase 1.5: Informed Discovery"),
    # Phase 2: Design (including subphases like 2.1, 2.2, 2.3)
    (r"Phase\s+2(?:\.\d+)?[:\s]+(?:Design|Review\s+Design)", "Phase 2: Design"),
    # Phase 3: Implementation Planning
    (r"Phase\s+3[:\s]+Implementation\s+Planning", "Phase 3: Implementation Planning"),
    # Phase 4: Implementation
    (r"Phase\s+4[:\s]+Implementation", "Phase 4: Implementation"),
]

# Phase ordering for priority comparison
PHASE_ORDER = [
    "Phase 0: Configuration Wizard",
    "Phase 1: Research",
    "Phase 1.5: Informed Discovery",
    "Phase 2: Design",
    "Phase 3: Implementation Planning",
    "Phase 4: Implementation",
]


def _get_phase_order(phase: str) -> int:
    """Get numeric order of a phase for comparison."""
    try:
        return PHASE_ORDER.index(phase)
    except ValueError:
        return -1


def _find_skill_invocation_index(messages: List[Dict[str, Any]]) -> Optional[int]:
    """Find the index of the most recent implementing-features skill invocation."""
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            if tc.get("tool") == "Skill" and tc.get("args", {}).get("skill") == "implementing-features":
                return i
    return None


def _extract_phase_from_text(text: str) -> Optional[str]:
    """Extract phase from text content."""
    for pattern, phase_name in PHASE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return phase_name
    return None


def _get_text_from_content(content: Any) -> str:
    """Extract text from content which may be a string or list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle content blocks like [{"type": "text", "text": "..."}]
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def extract_skill_phase(messages: List[Dict[str, Any]]) -> SkillPhase:
    """Extract skill phase from session messages.

    Finds the most recent implementing-features skill invocation and
    scans subsequent messages for phase markers to determine how far
    the skill progressed.

    Args:
        messages: List of session messages

    Returns:
        Phase string (e.g., "Phase 2: Design") or None if no skill active
    """
    # Find the most recent implementing-features invocation
    invocation_idx = _find_skill_invocation_index(messages)
    if invocation_idx is None:
        return None

    # Scan messages after the invocation for phase markers
    highest_phase: Optional[str] = None
    highest_order = -1

    for msg in messages[invocation_idx:]:
        content = msg.get("content", "")
        if not content:
            continue

        # Extract text from content (handles both string and block format)
        text = _get_text_from_content(content)
        if not text:
            continue

        phase = _extract_phase_from_text(text)
        if phase:
            order = _get_phase_order(phase)
            if order > highest_order:
                highest_phase = phase
                highest_order = order

    return highest_phase
