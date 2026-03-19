"""Extract recently accessed files from session transcript."""

from typing import List, Dict, Any

from spellbook_mcp.extractors.message_utils import get_tool_calls
from spellbook_mcp.extractors.types import RecentFiles


def extract_recent_files(messages: List[Dict[str, Any]], limit: int = 50) -> RecentFiles:
    """Extract file paths from Read/Edit/Write tool calls.

    Scans last N tool calls for file operations and returns unique paths.

    Args:
        messages: List of session messages
        limit: Maximum tool calls to scan (default 50)

    Returns:
        List of unique file paths, ordered by first appearance
    """
    file_paths: List[str] = []
    seen: set[str] = set()
    tool_count = 0

    # Scan messages in reverse to get recent files first
    for msg in reversed(messages):
        if tool_count >= limit:
            break

        tool_calls = get_tool_calls(msg)
        for call in tool_calls:
            tool = call.get("tool")
            if tool in ("Read", "Edit", "Write"):
                tool_count += 1
                args = call.get("args", {})
                if not isinstance(args, dict):
                    continue
                file_path = args.get("file_path")

                if file_path and file_path not in seen:
                    file_paths.append(file_path)
                    seen.add(file_path)

    # Reverse to get chronological order
    return list(reversed(file_paths))
