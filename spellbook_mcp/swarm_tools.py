"""MCP tools for swarm coordination.

These tools allow orchestrators to:
- Create and manage swarms
- Register workers
- Report progress, completion, and errors
- Monitor swarm status

All tools are synchronous wrappers around async backend operations.
"""
import asyncio
from typing import Dict, Any, Optional
from spellbook_mcp.preferences import (
    load_coordination_config,
    CoordinationConfig,
    CoordinationBackend
)
from spellbook_mcp.coordination.backends.base import CoordinationBackend as BackendInterface
from spellbook_mcp.coordination.backends.mcp_streamable_http import MCPStreamableHTTPBackend


def _get_backend(config: CoordinationConfig) -> BackendInterface:
    """
    Get backend instance from configuration.

    Args:
        config: Coordination configuration

    Returns:
        Backend instance

    Raises:
        ValueError: If backend is NONE or unsupported
    """
    if config.backend == CoordinationBackend.NONE:
        raise ValueError("No coordination backend configured. Set backend in preferences.")

    if config.backend == CoordinationBackend.MCP_STREAMABLE_HTTP:
        if config.mcp_sse is None:
            raise ValueError("MCP backend requires mcp_sse configuration")

        return MCPStreamableHTTPBackend({
            "host": config.mcp_sse.host,
            "port": config.mcp_sse.port
        })

    # Future backends can be added here
    # elif config.backend == CoordinationBackend.N8N:
    #     return N8NBackend(config.n8n)

    raise ValueError(f"Unsupported backend type: {config.backend.value}")


def _run_async(coro):
    """
    Run an async coroutine in a sync context.

    Args:
        coro: Coroutine to run

    Returns:
        Result of the coroutine
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, create new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def swarm_create(feature: str, manifest_path: str, auto_merge: bool = False) -> Dict[str, Any]:
    """
    Create a new swarm for coordinating parallel work packets.

    Args:
        feature: Feature name for the swarm
        manifest_path: Path to manifest file with work packets
        auto_merge: Whether to auto-merge on completion (default: False)

    Returns:
        {"swarm_id": str, "status": "created"}

    Raises:
        ValueError: If no backend configured
    """
    config = load_coordination_config()
    backend = _get_backend(config)

    swarm_id = _run_async(backend.create_swarm(feature, manifest_path, auto_merge))

    return {
        "swarm_id": swarm_id,
        "status": "created"
    }


def swarm_register(
    swarm_id: str,
    packet_id: int,
    packet_name: str,
    tasks_total: int,
    worktree: str
) -> Dict[str, Any]:
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

    Raises:
        ValueError: If no backend configured
    """
    config = load_coordination_config()
    backend = _get_backend(config)

    response = _run_async(backend.register_worker(
        swarm_id,
        packet_id,
        packet_name,
        tasks_total,
        worktree
    ))

    return response


def swarm_progress(
    swarm_id: str,
    packet_id: int,
    task_id: str,
    task_name: str,
    status: str,
    tasks_completed: int,
    tasks_total: int,
    commit: Optional[str] = None
) -> Dict[str, Any]:
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

    Raises:
        ValueError: If no backend configured
    """
    config = load_coordination_config()
    backend = _get_backend(config)

    response = _run_async(backend.report_progress(
        swarm_id,
        packet_id,
        task_id,
        task_name,
        status,
        tasks_completed,
        tasks_total,
        commit
    ))

    return response


def swarm_complete(
    swarm_id: str,
    packet_id: int,
    final_commit: str,
    tests_passed: bool,
    review_passed: bool
) -> Dict[str, Any]:
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

    Raises:
        ValueError: If no backend configured
    """
    config = load_coordination_config()
    backend = _get_backend(config)

    response = _run_async(backend.report_complete(
        swarm_id,
        packet_id,
        final_commit,
        tests_passed,
        review_passed
    ))

    return response


def swarm_error(
    swarm_id: str,
    packet_id: int,
    task_id: str,
    error_type: str,
    message: str,
    recoverable: bool
) -> Dict[str, Any]:
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

    Raises:
        ValueError: If no backend configured
    """
    config = load_coordination_config()
    backend = _get_backend(config)

    response = _run_async(backend.report_error(
        swarm_id,
        packet_id,
        task_id,
        error_type,
        message,
        recoverable
    ))

    return response


def swarm_monitor(swarm_id: str) -> Dict[str, Any]:
    """
    Get current swarm status (non-blocking poll).

    Args:
        swarm_id: Swarm identifier

    Returns:
        SwarmStatus dict with workers, completion status, etc.

    Raises:
        ValueError: If no backend configured
    """
    config = load_coordination_config()
    backend = _get_backend(config)

    status = _run_async(backend.get_status(swarm_id))

    return status
