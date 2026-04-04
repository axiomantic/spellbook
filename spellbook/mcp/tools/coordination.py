"""MCP tools for curator and stint tracking."""

__all__ = [
    "mcp_curator_track_prune",
    "stint_push",
    "stint_pop",
    "stint_check",
    "stint_replace",
]

from spellbook.mcp.server import mcp
from spellbook.coordination.curator import curator_track_prune
from spellbook.sessions.injection import inject_recovery_context


# Context Curator Tools

@mcp.tool()
@inject_recovery_context
async def mcp_curator_track_prune(
    session_id: str,
    tool_ids: list,
    tokens_saved: int,
    strategy: str,
) -> dict:
    """
    Track a pruning event for analytics.

    Args:
        session_id: The session identifier
        tool_ids: List of tool IDs that were pruned
        tokens_saved: Estimated tokens saved by this prune
        strategy: The strategy that triggered the prune

    Returns:
        Status dict with event_id
    """
    return await curator_track_prune(session_id, tool_ids, tokens_saved, strategy)


# Stint Stack Tools (Zeigarnik focus tracking)

@mcp.tool()
@inject_recovery_context
def stint_push(
    project_path: str,
    name: str,
    type: str = "",
    purpose: str = "",
    behavioral_mode: str = "",
    metadata: dict | None = None,
) -> dict:
    """Push a new stint onto the focus stack.

    Declares entry into a new unit of work. The new stint becomes the
    current active stint. Previous top-of-stack stint is implicitly
    suspended (but not exited).

    Args:
        project_path: Absolute path to project directory
        name: Identifier for this stint (e.g., task description, work context)
        type: Deprecated. Accepted but ignored for backward compatibility.
        purpose: Why this stint is being entered
        behavioral_mode: HOW the session should operate (e.g., "ORCHESTRATOR: ...")
        metadata: Optional key-value pairs for additional context

    Returns:
        {"success": True, "depth": int, "stack": list}
    """
    from spellbook.coordination.stint import push_stint
    result = push_stint(
        project_path=project_path,
        name=name,
        stint_type=type,
        purpose=purpose,
        behavioral_mode=behavioral_mode,
        metadata=metadata,
    )
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FOCUS,
                event_type="focus.stint_pushed",
                data={
                    "project_path": project_path,
                    "name": name,
                    "depth": result.get("depth"),
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
def stint_pop(
    project_path: str,
    name: str | None = None,
) -> dict:
    """Pop the top stint from the focus stack.

    Marks the top stint as completed. If name is provided, verifies it
    matches the top of stack. A mismatch logs a correction event but
    still pops (LLM intent takes priority).

    Args:
        project_path: Absolute path to project directory
        name: Optional name to verify matches top of stack

    Returns:
        {"success": True, "popped": dict, "depth": int, "mismatch": bool}
    """
    from spellbook.coordination.stint import pop_stint
    result = pop_stint(project_path=project_path, name=name)
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        popped = result.get("popped", {})
        publish_sync(
            Event(
                subsystem=Subsystem.FOCUS,
                event_type="focus.stint_popped",
                data={
                    "project_path": project_path,
                    "name": popped.get("name") if isinstance(popped, dict) else name,
                    "depth": result.get("depth"),
                    "mismatch": result.get("mismatch", False),
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
def stint_check(
    project_path: str,
) -> dict:
    """Return the current stint stack for verification.

    No side effects. Use to verify tracked state matches actual
    working context.

    Args:
        project_path: Absolute path to project directory

    Returns:
        {"success": True, "depth": int, "stack": list}
    """
    from spellbook.coordination.stint import check_stint
    return check_stint(project_path=project_path)


@mcp.tool()
@inject_recovery_context
def stint_replace(
    project_path: str,
    stack: list[dict],
    reason: str = "",
) -> dict:
    """Replace the entire stint stack with a corrected version.

    The LLM is the authority over its own focus state. When tracked
    state diverges from reality, this tool corrects it. Logs a
    correction event with classification.

    Args:
        project_path: Absolute path to project directory
        stack: New stack state (list of stint entry dicts)
        reason: Why the correction was needed

    Returns:
        {"success": True, "depth": int, "correction_logged": True}
    """
    from spellbook.coordination.stint import replace_stint
    result = replace_stint(
        project_path=project_path,
        stack=stack,
        reason=reason,
    )
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FOCUS,
                event_type="focus.stint_replaced",
                data={
                    "project_path": project_path,
                    "reason": reason[:200] if reason else "",
                    "depth": result.get("depth"),
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result
