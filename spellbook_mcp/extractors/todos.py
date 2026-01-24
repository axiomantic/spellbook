"""Extract active todos from session transcript."""

from typing import List, Dict, Any

from spellbook_mcp.extractors.message_utils import get_tool_calls
from spellbook_mcp.extractors.types import TodoList


def extract_todos(messages: List[Dict[str, Any]]) -> TodoList:
    """Extract active todos from TodoWrite tool calls.

    Scans messages for TodoWrite tool calls and returns todos with
    status != 'completed'. If multiple TodoWrite calls exist, the
    latest one wins.

    Args:
        messages: List of session messages

    Returns:
        List of active (non-completed) todo items
    """
    last_todos = None

    for msg in messages:
        tool_calls = get_tool_calls(msg)
        for call in tool_calls:
            if call.get("tool") == "TodoWrite":
                args = call.get("args", {})
                todos = args.get("todos", [])
                if todos:
                    last_todos = todos

    if last_todos is None:
        return []

    # Filter out completed todos
    return [todo for todo in last_todos if todo.get("status") != "completed"]
