"""MCP tool injection decorator for recovery context.

Provides automatic injection of session state recovery context into MCP tool
responses after compaction events are detected.

Key functions:
- should_inject(): Determines if injection should occur on this call
- wrap_with_reminder(): Wraps tool results with <system-reminder> tags
- build_recovery_context(): Builds human-readable context from database
- inject_recovery_context(): Decorator for MCP tool functions
"""

import json
import os
from functools import wraps
from typing import Any, Optional

from .db import get_connection, get_db_path
from .watcher import is_heartbeat_fresh


# Module state for injection control
_injection_cache: Optional[dict] = None
_call_counter: int = 0
_pending_compaction: bool = False


def _reset_state() -> None:
    """Reset module state. Used for testing."""
    global _injection_cache, _call_counter, _pending_compaction
    _injection_cache = None
    _call_counter = 0
    _pending_compaction = False


def _set_pending_compaction(pending: bool) -> None:
    """Set pending compaction flag.

    Called by the watcher when compaction is detected.

    Args:
        pending: True to trigger injection on next tool call
    """
    global _pending_compaction
    _pending_compaction = pending


def should_inject() -> bool:
    """Determine if injection should occur on this call.

    Injection triggers:
    - First call after compaction detection (resets counter)
    - Every 10th call thereafter (periodic refresh)

    Returns:
        True if injection should occur on this call
    """
    global _call_counter, _pending_compaction

    # Check for pending compaction (highest priority)
    if _pending_compaction:
        _call_counter = 0
        _pending_compaction = False
        return True

    # Increment counter and check for periodic injection
    _call_counter += 1
    if _call_counter % 10 == 0:
        return True

    return False


def wrap_with_reminder(result: Any, context: Optional[str]) -> Any:
    """Wrap result with system reminder tag.

    Handles different MCP return types:
    - str: Prepend reminder followed by newlines
    - dict: Add __system_reminder key preserving existing keys
    - list: Wrap in dict with items key
    - other: Convert to string and prepend reminder

    Args:
        result: Original tool result
        context: Recovery context to inject. If empty/None, returns original.

    Returns:
        Wrapped result with same or compatible type
    """
    if not context:
        return result

    reminder = f"<system-reminder>\n{context}\n</system-reminder>"

    if isinstance(result, str):
        return f"{reminder}\n\n{result}"
    elif isinstance(result, dict):
        return {"__system_reminder": reminder, **result}
    elif isinstance(result, list):
        return {"__system_reminder": reminder, "items": result}
    else:
        # Fallback: convert to string
        return f"{reminder}\n\n{str(result)}"


def build_recovery_context(
    db_path: str, project_path: str, max_tokens: int = 500
) -> Optional[str]:
    """Build human-readable recovery context from database.

    Queries database for latest soul matching the project path and formats
    the extracted state for injection into tool responses.

    Args:
        db_path: Path to SQLite database file
        project_path: Current project path to match against souls
        max_tokens: Maximum tokens for context (default 500, ~2000 chars)

    Returns:
        Formatted context string, or None if no soul found or soul is empty
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Get latest soul for this project (most recently bound)
    cursor.execute(
        """
        SELECT persona, active_skill, todos, recent_files, exact_position, workflow_pattern
        FROM souls
        WHERE project_path = ?
        ORDER BY bound_at DESC
        LIMIT 1
    """,
        (project_path,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    persona, active_skill, todos_json, files_json, position_json, workflow = row

    # Parse JSON fields with null safety
    todos = json.loads(todos_json) if todos_json else []
    recent_files = json.loads(files_json) if files_json else []
    exact_position = json.loads(position_json) if position_json else []

    # Build context parts (only include non-empty sections)
    parts = []

    if todos:
        todo_lines = [f"- {t['content']} ({t['status']})" for t in todos[:5]]
        parts.append("**Active TODOs:**\n" + "\n".join(todo_lines))

    if active_skill:
        parts.append(f"**Active Skill:** {active_skill}")

    if persona:
        parts.append(f"**Session Persona:** {persona}")

    if exact_position:
        pos_lines = [f"- {a['tool']}: {a['primary_arg']}" for a in exact_position[-5:]]
        parts.append("**Last Actions:**\n" + "\n".join(pos_lines))

    if not parts:
        return None

    context = "\n\n".join(parts)

    # Truncate if over token budget (rough estimate: 4 chars per token)
    max_chars = max_tokens * 4
    if len(context) > max_chars:
        context = context[:max_chars] + "..."

    return context


def get_recovery_context(project_path: str) -> Optional[str]:
    """Get recovery context with heartbeat check.

    High-level function that checks if the watcher is alive (via heartbeat)
    before querying the database for recovery context.

    Args:
        project_path: Current project path

    Returns:
        Recovery context string, or None if watcher not running or no context
    """
    db_path = str(get_db_path())

    # Verify watcher is running via heartbeat
    if not is_heartbeat_fresh(db_path):
        return None

    return build_recovery_context(db_path, project_path)


def inject_recovery_context(func):
    """Decorator for MCP tools to inject recovery context.

    Wraps synchronous MCP tool handlers. On each call:
    1. Executes the original tool function
    2. Checks if injection is needed (compaction or periodic)
    3. If needed, fetches context from database
    4. Wraps result with <system-reminder> tag

    Usage:
        @mcp.tool()
        @inject_recovery_context
        def my_tool():
            return {"status": "ok"}

    Note: The decorator order matters - @inject_recovery_context should be
    closest to the function definition (applied first, runs last).
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Execute original tool
        result = func(*args, **kwargs)

        # Check if injection needed
        if should_inject():
            project_path = os.getcwd()
            context = get_recovery_context(project_path)

            if context:
                result = wrap_with_reminder(result, context)

        return result

    return wrapper
