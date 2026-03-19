"""Extract active skill from session transcript.

Scans messages for Skill tool calls and returns the skill name
from the most recent invocation.
"""

from typing import Any, Dict, List

from spellbook_mcp.extractors.message_utils import get_tool_calls
from spellbook_mcp.extractors.types import ActiveSkill


def extract_active_skill(messages: List[Dict[str, Any]]) -> ActiveSkill:
    """Extract active skill from Skill tool invocations.

    Scans messages for Skill tool calls and returns the skill name
    from the most recent invocation. If multiple Skill calls exist,
    the latest one wins.

    Args:
        messages: List of session messages

    Returns:
        Skill name string or None if no skill active
    """
    last_skill: ActiveSkill = None

    for msg in messages:
        tool_calls = get_tool_calls(msg)
        for call in tool_calls:
            if call.get("tool") == "Skill":
                args = call.get("args", {})
                if args is None:
                    continue
                skill_name = args.get("skill")
                if skill_name:
                    last_skill = skill_name

    return last_skill
