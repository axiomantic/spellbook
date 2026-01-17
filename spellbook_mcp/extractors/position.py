"""Extract last 10 tool actions for position tracking."""

from typing import List, Dict, Any, Optional

from .message_utils import get_tool_calls
from .types import Position, ToolAction


def _extract_primary_arg(tool: str, args: dict) -> str:
    """Extract primary argument for a tool invocation.

    Args:
        tool: Tool name
        args: Tool arguments dict

    Returns:
        Primary argument string, truncated if needed
    """
    primary = ""

    if tool in ("Read", "Edit", "Write"):
        primary = args.get("file_path", "")
    elif tool == "Bash":
        primary = args.get("command", "")
    elif tool == "Grep":
        primary = args.get("pattern", "")
    elif tool == "Glob":
        primary = args.get("pattern", "")
    elif tool == "Task":
        primary = args.get("prompt", "")
    elif tool == "WebFetch":
        primary = args.get("url", "")
    elif tool == "Skill":
        primary = args.get("skill", "")
    else:
        # Generic fallback: use first non-empty arg value
        for value in args.values():
            if isinstance(value, str) and value:
                primary = value
                break

    # Truncate long arguments
    if len(primary) > 100:
        primary = primary[:100]

    return primary


def extract_position(messages: List[Dict[str, Any]]) -> Position:
    """Extract last 10 tool invocations for position tracking.

    Args:
        messages: List of session messages

    Returns:
        List of ToolAction dicts with keys: tool, primary_arg, timestamp, success
        Limited to 10 most recent actions.
    """
    actions: List[ToolAction] = []

    for msg in messages:
        timestamp = msg.get("timestamp", "")
        tool_calls = get_tool_calls(msg)

        for call in tool_calls:
            tool = call.get("tool")
            if not tool:
                continue

            args = call.get("args", {})
            primary_arg = _extract_primary_arg(tool, args)

            # Extract success flag if present
            success: Optional[bool] = call.get("success")

            actions.append({
                "tool": tool,
                "primary_arg": primary_arg,
                "timestamp": timestamp if timestamp else "",
                "success": success
            })

    # Return last 10
    return actions[-10:]
