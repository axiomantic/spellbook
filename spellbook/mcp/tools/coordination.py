"""MCP tools for swarm coordination, curator, and stint tracking."""

from spellbook.mcp.server import mcp
from spellbook_mcp.curator_tools import curator_track_prune
from spellbook_mcp.injection import inject_recovery_context
from spellbook_mcp.swarm_tools import (
    swarm_complete,
    swarm_create,
    swarm_error,
    swarm_monitor,
    swarm_progress,
    swarm_register,
)


# Swarm Coordination Tools

@mcp.tool()
@inject_recovery_context
def mcp_swarm_create(feature: str, manifest_path: str, auto_merge: bool = False) -> dict:
    """
    Create a new swarm for coordinating parallel work packets.

    Args:
        feature: Feature name for the swarm
        manifest_path: Path to manifest file with work packets
        auto_merge: Whether to auto-merge on completion (default: False)

    Returns:
        {"swarm_id": str, "status": "created"}
    """
    return swarm_create(feature, manifest_path, auto_merge)


@mcp.tool()
@inject_recovery_context
def mcp_swarm_register(
    swarm_id: str,
    packet_id: int,
    packet_name: str,
    tasks_total: int,
    worktree: str
) -> dict:
    """
    Register a worker with the swarm.

    Args:
        swarm_id: Swarm identifier
        packet_id: Packet ID number
        packet_name: Name of the work packet
        tasks_total: Total number of tasks
        worktree: Path to worker's worktree

    Returns:
        {"status": "registered", "packet_id": int}
    """
    return swarm_register(swarm_id, packet_id, packet_name, tasks_total, worktree)


@mcp.tool()
@inject_recovery_context
def mcp_swarm_progress(
    swarm_id: str,
    packet_id: int,
    task_id: str,
    task_name: str,
    status: str,
    tasks_completed: int,
    tasks_total: int,
    commit: str = None
) -> dict:
    """
    Report task progress to the swarm.

    Args:
        swarm_id: Swarm identifier
        packet_id: Packet ID number
        task_id: Task identifier
        task_name: Name of the task
        status: Task status (started, completed, failed)
        tasks_completed: Number of tasks completed
        tasks_total: Total number of tasks
        commit: Optional git commit SHA

    Returns:
        {"status": "recorded", "tasks_completed": int, "tasks_total": int}
    """
    return swarm_progress(
        swarm_id,
        packet_id,
        task_id,
        task_name,
        status,
        tasks_completed,
        tasks_total,
        commit
    )


@mcp.tool()
@inject_recovery_context
def mcp_swarm_complete(
    swarm_id: str,
    packet_id: int,
    final_commit: str,
    tests_passed: bool,
    review_passed: bool
) -> dict:
    """
    Signal worker completion.

    Args:
        swarm_id: Swarm identifier
        packet_id: Packet ID number
        final_commit: Final git commit SHA
        tests_passed: Whether tests passed
        review_passed: Whether code review passed

    Returns:
        {"status": "complete", "all_workers_done": bool}
    """
    return swarm_complete(swarm_id, packet_id, final_commit, tests_passed, review_passed)


@mcp.tool()
@inject_recovery_context
def mcp_swarm_error(
    swarm_id: str,
    packet_id: int,
    task_id: str,
    error_type: str,
    message: str,
    recoverable: bool
) -> dict:
    """
    Report an error from worker.

    Args:
        swarm_id: Swarm identifier
        packet_id: Packet ID number
        task_id: Task identifier
        error_type: Type of error (e.g., TestFailure, MergeConflict)
        message: Error message
        recoverable: Whether error is recoverable

    Returns:
        {"status": "error_recorded", "will_retry": bool}
    """
    return swarm_error(swarm_id, packet_id, task_id, error_type, message, recoverable)


@mcp.tool()
@inject_recovery_context
def mcp_swarm_monitor(swarm_id: str) -> dict:
    """
    Get current swarm status (non-blocking poll).

    Args:
        swarm_id: Swarm identifier

    Returns:
        SwarmStatus dict with workers, completion status, etc.
    """
    return swarm_monitor(swarm_id)


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
    type: str = "custom",
    purpose: str = "",
    behavioral_mode: str = "",
    success_criteria: str = "",
    metadata: dict | None = None,
) -> dict:
    """Push a new stint onto the focus stack.

    Declares entry into a new unit of work. The new stint becomes the
    current active stint. Previous top-of-stack stint is implicitly
    suspended (but not exited).

    Args:
        project_path: Absolute path to project directory
        name: Identifier for this stint (e.g., skill name, task description)
        type: "skill" | "subagent" | "custom"
        purpose: Why this stint is being entered
        behavioral_mode: HOW the session should operate (e.g., "ORCHESTRATOR: ...")
        success_criteria: What "done" looks like for this stint
        metadata: Optional key-value pairs for additional context

    Returns:
        {"success": True, "depth": int, "stack": list}
    """
    from spellbook_mcp.stint_tools import push_stint
    result = push_stint(
        project_path=project_path,
        name=name,
        stint_type=type,
        purpose=purpose,
        behavioral_mode=behavioral_mode,
        success_criteria=success_criteria,
        metadata=metadata,
    )
    try:
        from spellbook_mcp.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FOCUS,
                event_type="focus.stint_pushed",
                data={
                    "project_path": project_path,
                    "name": name,
                    "type": type,
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
    from spellbook_mcp.stint_tools import pop_stint
    result = pop_stint(project_path=project_path, name=name)
    try:
        from spellbook_mcp.admin.events import Event, Subsystem, publish_sync

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
    from spellbook_mcp.stint_tools import check_stint
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
    from spellbook_mcp.stint_tools import replace_stint
    result = replace_stint(
        project_path=project_path,
        stack=stack,
        reason=reason,
    )
    try:
        from spellbook_mcp.admin.events import Event, Subsystem, publish_sync

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
