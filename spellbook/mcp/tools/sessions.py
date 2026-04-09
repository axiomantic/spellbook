"""MCP tools for session management."""

__all__ = [
    "find_session",
    "split_session",
    "list_sessions",
    "spawn_session",
    "spawn_claude_session",
]

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook.sessions.injection import inject_recovery_context
from spellbook.core.path_utils import (
    get_project_dir_from_context,
    get_project_path_from_context,
)
from spellbook.sessions.parser import list_sessions_with_samples, split_by_char_limit
from spellbook.daemon.terminal import detect_terminal, spawn_terminal_window
from spellbook.sdk.unified import get_agent_client, AgentOptions


@mcp.tool()
@inject_recovery_context
async def find_session(ctx: Context, name: str, limit: int = 10) -> List[Dict[str, Any]]:
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
    project_dir = await get_project_dir_from_context(ctx)

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
@inject_recovery_context
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
@inject_recovery_context
async def list_sessions(ctx: Context, limit: int = 5) -> List[Dict[str, Any]]:
    """
    List recent sessions for current project with rich metadata and content samples.

    Auto-detects project directory from MCP client roots.
    Returns sessions sorted by last activity (most recent first).

    Args:
        limit: Maximum sessions to return (default 5)

    Returns:
        List of session metadata dictionaries
    """
    project_dir = await get_project_dir_from_context(ctx)

    # Return empty list if project directory doesn't exist (new project)
    if not project_dir.exists():
        return []

    return list_sessions_with_samples(str(project_dir), limit)


def _validate_working_directory(wd: str, project_path: str | None) -> str:
    """Validate and resolve working directory for spawn.

    Rules:
    1. Must be an existing directory (after symlink resolution)
    2. Must resolve to a path under $HOME or the project path
    3. No symlink escape (resolve before checking)

    Raises:
        ValueError: If validation fails.

    Returns:
        Resolved absolute path as string.
    """
    resolved = Path(wd).resolve()

    if not resolved.is_dir():
        raise ValueError(f"Working directory does not exist: {wd}")

    home = Path.home().resolve()
    allowed_roots = [home]
    if project_path:
        allowed_roots.append(Path(project_path).resolve())

    if not any(resolved == root or resolved.is_relative_to(root) for root in allowed_roots):
        raise ValueError(
            f"Working directory {wd} is outside allowed scope "
            f"(must be under $HOME or project directory)"
        )

    return str(resolved)


def _get_session_id(ctx):
    """Extract session_id from Context if available."""
    if ctx is None:
        return None
    try:
        return ctx.session_id
    except RuntimeError:
        return None


@mcp.tool()
@inject_recovery_context
async def spawn_session(
    ctx: Context,
    prompt: str,
    working_directory: str = None,
    terminal: str = None,
    provider: str = None,
    headless: bool = True,
    allowed_tools: list[str] = None,
    disallowed_tools: list[str] = None,
) -> dict:
    """
    Spawn an AI assistant session, either as a terminal window or headless subprocess.

    Args:
        prompt: Initial prompt/command to send to the assistant
        working_directory: Directory to start in (defaults to client cwd)
        terminal: Terminal program (auto-detected if not specified, ignored if headless)
        provider: Provider name (claude or gemini). Auto-detected if not specified.
        headless: If true, run as a subprocess with -p flag instead of opening a terminal.
            Returns the session output directly. Useful for fractal workers and automated tasks.
        allowed_tools: List of tool names to allow in the spawned session
            (e.g. ["mcp__spellbook__fractal_claim_work", "Read", "Grep"]).
        disallowed_tools: List of tool names to deny in the spawned session.

    Returns:
        Terminal mode: {"status": "spawned", "terminal": str, "pid": int | None}
        Headless mode: {"status": "completed", "output": str, "pid": int}
    """
    # --- MCP-level security guard ---
    import sqlite3 as _sqlite3

    from spellbook.gates.check import check_tool_input as _check_tool_input
    from spellbook.core.db import get_db_path

    _db_path = str(get_db_path())
    _session_id = _get_session_id(ctx)

    # Scan prompt for injection patterns
    _check_result = _check_tool_input(
        "spawn_session",
        {"prompt": prompt},
    )

    if not _check_result["safe"]:
        _first = _check_result["findings"][0]
        return {
            "blocked": True,
            "reason": _first["message"],
            "rule_id": _first["rule_id"],
        }

    # Rate limit: max 1 call per 5 minutes
    try:
        _conn = _sqlite3.connect(_db_path, timeout=5.0)
        try:
            _now = time.time()
            _cutoff = _now - 300  # 5 minutes
            _row = _conn.execute(
                "SELECT COUNT(*) FROM spawn_rate_limit WHERE timestamp > ?",
                (_cutoff,),
            ).fetchone()

            if _row[0] > 0:
                return {
                    "blocked": True,
                    "reason": "Rate limit exceeded: max 1 spawn per 5 minutes",
                    "rule_id": "RATE-LIMIT-001",
                }

            # Record this invocation for rate limiting
            _conn.execute(
                "INSERT INTO spawn_rate_limit (timestamp, session_id) VALUES (?, ?)",
                (_now, _session_id),
            )

            # Clean up old rate limit records
            _conn.execute("DELETE FROM spawn_rate_limit WHERE timestamp < ?", (_cutoff,))

            _conn.commit()
        finally:
            _conn.close()
    except _sqlite3.Error as e:
        return {"status": "error", "error": f"Rate limit check failed: {e}. Blocking spawn for safety."}

    # --- End security guard ---

    # Also scan working_directory through security check if provided
    if working_directory:
        _wd_check = _check_tool_input(
            "spawn_session",
            {"working_directory": working_directory},
        )
        if not _wd_check["safe"]:
            _wd_first = _wd_check["findings"][0]
            return {
                "blocked": True,
                "reason": _wd_first["message"],
                "rule_id": _wd_first["rule_id"],
            }

    if working_directory is None:
        working_directory = await get_project_path_from_context(ctx)

    # Validate working_directory is a real, in-scope directory
    if working_directory:
        try:
            working_directory = _validate_working_directory(
                working_directory,
                project_path=os.environ.get("CLAUDE_PROJECT_DIR"),
            )
        except ValueError as e:
            return {"success": False, "error": str(e)}

    # Use SDK to spawn
    options = AgentOptions(
        cwd=Path(working_directory) if working_directory else Path.cwd(),
        allowed_tools=allowed_tools,
        disallowed_tools=disallowed_tools,
    )
    client = get_agent_client(provider, options)

    if headless:
        return await client.run_subprocess(prompt)
    return client.spawn_session(prompt, terminal=terminal)


@mcp.tool()
@inject_recovery_context
async def spawn_claude_session(
    ctx: Context,
    prompt: str,
    working_directory: str = None,
    terminal: str = None
) -> dict:
    """
    DEPRECATED: Use spawn_session instead.
    Open a new terminal window with an interactive Claude session.
    """
    return await spawn_session(ctx, prompt, working_directory, terminal, provider="claude")
