#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastmcp",
# ]
# ///
"""
Spellbook MCP Server - Session management and swarm coordination tools for MCP-enabled clients.

Provides MCP tools:
Session Management:
- find_session: Search sessions by name (case-insensitive)
- split_session: Calculate chunk boundaries for session content
- list_sessions: List recent sessions with metadata and samples
- spawn_claude_session: Open a new terminal window with Claude session

Swarm Coordination:
- swarm_create: Create a new swarm for coordinating parallel work packets
- swarm_register: Register a worker with the swarm
- swarm_progress: Report task progress to the swarm
- swarm_complete: Signal worker completion
- swarm_error: Report an error from worker
- swarm_monitor: Get current swarm status (non-blocking poll)
"""

from fastmcp import FastMCP
from pathlib import Path
from typing import List, Dict, Any
import os
import json
import sys

# Add script directory and repo root to sys.path to allow imports when run directly.
# - current_dir: allows "from path_utils import ..." style imports
# - repo_root: allows "from spellbook_mcp.X import ..." style imports
# This fixes import issues when the server is executed as a standalone script.
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from path_utils import get_project_dir
from session_ops import (
    split_by_char_limit,
    list_sessions_with_samples,
)
from terminal_utils import detect_terminal, spawn_terminal_window
from swarm_tools import (
    swarm_create,
    swarm_register,
    swarm_progress,
    swarm_complete,
    swarm_error,
    swarm_monitor
)

mcp = FastMCP("spellbook")

@mcp.tool()
def find_session(name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Find sessions by name using case-insensitive substring matching.

    Searches both the session slug and custom title (if set via /rename).
    Returns sessions sorted by last activity (most recent first).

    Args:
        name: Search query (case-insensitive substring)
        limit: Maximum results to return (default 10)

    Returns:
        List of session metadata dictionaries matching the search query
    """
    project_dir = get_project_dir()

    # Return empty list if project directory doesn't exist (new project)
    if not project_dir.exists():
        return []

    # Load all sessions using list_sessions_with_samples
    # Use a high limit to get all sessions, then filter
    all_sessions = list_sessions_with_samples(str(project_dir), limit=1000)

    # Normalize search query
    name_lower = name.strip().lower()

    # Filter by name match in slug or custom_title
    # Empty string matches all (as per design doc)
    if not name_lower:
        matches = all_sessions
    else:
        matches = [
            s for s in all_sessions
            if (s.get('slug') and name_lower in s['slug'].lower())
            or (s.get('custom_title') and name_lower in s['custom_title'].lower())
        ]

    # Already sorted by last_activity in list_sessions_with_samples
    return matches[:limit]


@mcp.tool()
def split_session(session_path: str, start_line: int, char_limit: int) -> List[List[int]]:
    """
    Calculate chunk boundaries for a session that respect message boundaries.

    Returns list of [start_line, end_line] pairs where end_line is exclusive.
    Always splits at message boundaries (never mid-message).

    Args:
        session_path: Absolute path to .jsonl session file
        start_line: Starting line number (0-indexed)
        char_limit: Maximum characters per chunk

    Returns:
        List of [start, end] chunk boundaries

    Raises:
        FileNotFoundError: If session file doesn't exist
        ValueError: If start_line out of bounds or char_limit invalid
    """
    # Delegate to session_ops implementation
    # Already returns List[List[int]]
    return split_by_char_limit(session_path, start_line, char_limit)


@mcp.tool()
def list_sessions(limit: int = 5) -> List[Dict[str, Any]]:
    """
    List recent sessions for current project with rich metadata and content samples.

    Auto-detects project directory from current working directory.
    Returns sessions sorted by last activity (most recent first).

    Args:
        limit: Maximum sessions to return (default 5)

    Returns:
        List of session metadata dictionaries
    """
    project_dir = get_project_dir()

    # Return empty list if project directory doesn't exist (new project)
    if not project_dir.exists():
        return []

    return list_sessions_with_samples(str(project_dir), limit)

@mcp.tool()
def spawn_claude_session(
    prompt: str,
    working_directory: str = None,
    terminal: str = None
) -> dict:
    """
    Open a new terminal window with an interactive Claude session.

    Args:
        prompt: Initial prompt/command to send to Claude
        working_directory: Directory to start in (defaults to cwd)
        terminal: Terminal program (auto-detected if not specified)

    Returns:
        {"status": "spawned", "terminal": str, "pid": int | None}
    """
    if terminal is None:
        terminal = detect_terminal()

    if working_directory is None:
        working_directory = os.getcwd()

    return spawn_terminal_window(terminal, prompt, working_directory)


# Swarm Coordination Tools
@mcp.tool()
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
def mcp_swarm_monitor(swarm_id: str) -> dict:
    """
    Get current swarm status (non-blocking poll).

    Args:
        swarm_id: Swarm identifier

    Returns:
        SwarmStatus dict with workers, completion status, etc.
    """
    return swarm_monitor(swarm_id)


if __name__ == "__main__":
    mcp.run()
