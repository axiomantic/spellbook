"""Message parsing utilities for consistent transcript handling.

ALL Phase 2 extractors MUST use these utilities for:
- Extracting tool calls from messages
- Getting message content (handles string and list formats)
- Getting timestamps

This ensures consistent handling of missing/null/malformed fields.
"""

from typing import Any, Dict, List, Optional


def get_tool_calls(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool calls, handling None/missing/non-list cases.

    Args:
        msg: Message dict from transcript

    Returns:
        List of tool call dicts, empty list if none found
    """
    tool_calls = msg.get("tool_calls")
    if tool_calls is None or not isinstance(tool_calls, list):
        return []
    return tool_calls


def get_content(msg: Dict[str, Any]) -> str:
    """Extract content as string, handling structured blocks.

    Args:
        msg: Message dict from transcript

    Returns:
        Content as string, empty string if missing
    """
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle array of content blocks
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
        )
    return str(content) if content else ""


def get_timestamp(msg: Dict[str, Any]) -> Optional[str]:
    """Extract timestamp from message.

    Args:
        msg: Message dict from transcript

    Returns:
        ISO timestamp string or None if missing
    """
    return msg.get("timestamp")


def get_role(msg: Dict[str, Any]) -> str:
    """Extract role from message.

    Args:
        msg: Message dict from transcript

    Returns:
        Role string ("user", "assistant", "system") or empty string
    """
    return msg.get("role", "")


def is_assistant_message(msg: Dict[str, Any]) -> bool:
    """Check if message is from assistant."""
    return get_role(msg) == "assistant"


def is_user_message(msg: Dict[str, Any]) -> bool:
    """Check if message is from user."""
    return get_role(msg) == "user"
