"""Extract session persona (fun mode, tarot mode) from transcript.

Scans messages for fun mode or tarot mode markers and returns the
appropriate persona string.
"""

import re
from typing import Any, Dict, List

from spellbook_mcp.extractors.message_utils import get_content
from spellbook_mcp.extractors.types import Persona


def extract_persona(messages: List[Dict[str, Any]]) -> Persona:
    """Extract session persona/mode from messages.

    Searches for fun mode or tarot mode markers in message content.
    Fun mode is identified by "PERSONA: name" pattern.
    Tarot mode is identified by "tarot mode active" text (case insensitive).

    Args:
        messages: List of session messages

    Returns:
        Persona string:
        - "fun:{name}" for fun mode with persona name
        - "tarot" for tarot mode
        - None for standard mode
    """
    persona: Persona = None

    for msg in messages:
        content = get_content(msg)
        if not content:
            continue

        # Check for tarot mode (case insensitive)
        if "tarot mode active" in content.lower():
            persona = "tarot"

        # Check for fun mode - PERSONA: pattern takes precedence if found later
        fun_match = re.search(r"PERSONA:\s*([^\n]+)", content)
        if fun_match:
            persona_name = fun_match.group(1).strip()
            persona = f"fun:{persona_name}"

    return persona
