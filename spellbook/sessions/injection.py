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
import logging
import os
import threading
from functools import wraps
from typing import Any, Optional

from spellbook.core.db import get_db_path
from spellbook.sessions.watcher import is_heartbeat_fresh

logger = logging.getLogger(__name__)

# Field length limits for DB-sourced recovery context fields
_FIELD_LENGTH_LIMITS = {
    "persona": 200,
    "active_skill": 100,
    "skill_phase": 100,
    "todos": 500,        # per item
    "recent_files": 500,  # per item
    "exact_position": 500,  # per item (serialized)
}


def _sanitize_field(field_name: str, value: str, max_length: int) -> Optional[str]:
    """Sanitize a single DB-sourced field for injection patterns and length.

    Args:
        field_name: Name of the field (for logging).
        value: The field value to sanitize.
        max_length: Maximum allowed length.

    Returns:
        Sanitized value, or None if the field contains injection patterns.
    """
    if not value:
        return value

    # Truncate to length limit
    if len(value) > max_length:
        value = value[:max_length]

    # Check for injection patterns using the security detection
    try:
        from spellbook.security.tools import do_detect_injection

        result = do_detect_injection(value)
        if result["is_injection"]:
            logger.warning(
                "Injection pattern detected in recovery context field '%s', "
                "omitting from context",
                field_name,
            )
            return None
    except ImportError:
        # Security module not installed; still apply length limits
        pass
    except Exception as e:
        # Unexpected error during security check: fail closed by omitting
        # the field rather than silently passing potentially dangerous input
        logger.warning(
            "Security check failed for field '%s', omitting as precaution: %s",
            field_name,
            type(e).__name__,
        )
        return None

    return value


# Module state for injection control
_injection_cache: Optional[dict] = None
_call_counter: int = 0
_pending_compaction: bool = False
_state_lock: threading.Lock = threading.Lock()


def _reset_state() -> None:
    """Reset module state. Used for testing."""
    global _injection_cache, _call_counter, _pending_compaction
    with _state_lock:
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
    with _state_lock:
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

    with _state_lock:
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
    from sqlalchemy import select
    from spellbook.db.engines import get_sync_session
    from spellbook.db.spellbook_models import Soul

    with get_sync_session(db_path) as session:
        stmt = (
            select(Soul)
            .where(Soul.project_path == project_path)
            .order_by(Soul.bound_at.desc())
            .limit(1)
        )
        soul = session.execute(stmt).scalars().first()

    if not soul:
        return None

    persona = soul.persona
    active_skill = soul.active_skill
    skill_phase = soul.skill_phase
    todos_json = soul.todos
    files_json = soul.recent_files
    position_json = soul.exact_position

    # Parse JSON fields with error handling for corrupted data
    try:
        todos = json.loads(todos_json) if todos_json else []
    except json.JSONDecodeError:
        todos = []

    try:
        recent_files = json.loads(files_json) if files_json else []
    except json.JSONDecodeError:
        recent_files = []

    try:
        exact_position = json.loads(position_json) if position_json else []
    except json.JSONDecodeError:
        exact_position = []

    # Sanitize scalar fields through injection detection and length limits
    persona = _sanitize_field("persona", persona, _FIELD_LENGTH_LIMITS["persona"])
    active_skill = _sanitize_field("active_skill", active_skill, _FIELD_LENGTH_LIMITS["active_skill"])
    skill_phase = _sanitize_field("skill_phase", skill_phase, _FIELD_LENGTH_LIMITS["skill_phase"])

    # Sanitize list fields per-item
    if todos:
        sanitized_todos = []
        for t in todos[:5]:
            content = t.get("content", "")
            sanitized_content = _sanitize_field("todo item", content, _FIELD_LENGTH_LIMITS["todos"])
            if sanitized_content is not None:
                sanitized_todos.append({**t, "content": sanitized_content})
        todos = sanitized_todos

    if exact_position:
        sanitized_positions = []
        for a in exact_position[-5:]:
            # Sanitize the serialized representation of each position item
            item_str = f"{a.get('tool', '')}: {a.get('primary_arg', '')}"
            sanitized_item = _sanitize_field("exact_position item", item_str, _FIELD_LENGTH_LIMITS["exact_position"])
            if sanitized_item is not None:
                # Truncate individual fields within the position item
                truncated_a = dict(a)
                if len(truncated_a.get("primary_arg", "")) > _FIELD_LENGTH_LIMITS["exact_position"]:
                    truncated_a["primary_arg"] = truncated_a["primary_arg"][:_FIELD_LENGTH_LIMITS["exact_position"]]
                sanitized_positions.append(truncated_a)
        exact_position = sanitized_positions

    if recent_files:
        sanitized_files = []
        for f in recent_files:
            item_str = str(f) if not isinstance(f, str) else f
            sanitized_item = _sanitize_field("recent_files item", item_str, _FIELD_LENGTH_LIMITS["recent_files"])
            if sanitized_item is not None:
                sanitized_files.append(f)
        recent_files = sanitized_files

    # Build context parts (only include non-empty sections)
    parts = []

    if todos:
        todo_lines = [f"- {t['content']} ({t['status']})" for t in todos]
        parts.append("**Active TODOs:**\n" + "\n".join(todo_lines))

    if active_skill:
        parts.append(f"**Active Skill:** {active_skill}")

    if skill_phase:
        parts.append(f"**Skill Phase:** {skill_phase}")

    if persona:
        parts.append(f"**Session Persona:** {persona}")

    if exact_position:
        pos_lines = [f"- {a['tool']}: {a['primary_arg']}" for a in exact_position]
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

    Wraps MCP tool handlers (sync or async). On each call:
    1. Executes the original tool function
    2. Checks if injection is needed (compaction or periodic)
    3. If needed, fetches context from database
    4. Wraps result with <system-reminder> tag

    Usage:
        @mcp.tool()
        @inject_recovery_context
        def my_tool():
            return {"status": "ok"}

        @mcp.tool()
        @inject_recovery_context
        async def my_async_tool():
            return {"status": "ok"}

    Note: The decorator order matters - @inject_recovery_context should be
    closest to the function definition (applied first, runs last).
    """
    import asyncio

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute original tool
            result = await func(*args, **kwargs)

            # Check if injection needed
            if should_inject():
                project_path = os.getcwd()
                context = get_recovery_context(project_path)

                if context:
                    result = wrap_with_reminder(result, context)

            return result

        return async_wrapper
    else:
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
