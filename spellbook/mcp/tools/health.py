"""MCP tools for health checks."""

import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import List

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook.mcp import state as _state
from spellbook_mcp.compaction_detector import (
    check_for_compaction,
    get_pending_context,
    get_recovery_reminder,
    mark_context_injected,
)
from spellbook_mcp.config_tools import (
    config_get,
    get_spellbook_dir,
    session_init,
    session_mode_get,
)
from spellbook_mcp.db import get_db_path
from spellbook_mcp.health import run_health_check
from spellbook_mcp.injection import inject_recovery_context
from spellbook_mcp.path_utils import get_project_path_from_context, get_spellbook_config_dir

# Use shared state from spellbook.mcp.state for health check tracking


def _get_session_id(ctx):
    """Extract session_id from Context if available."""
    if ctx is None:
        return None
    try:
        return ctx.session_id
    except RuntimeError:
        return None


def _get_version() -> str:
    """Read version from .version file.

    Returns version string or "unknown" if file not found.
    """
    try:
        # Try relative to this file (spellbook/mcp/tools/)
        version_path = Path(__file__).parent.parent.parent.parent / ".version"
        if version_path.exists():
            return version_path.read_text(encoding="utf-8").strip()

        # Fallback: try SPELLBOOK_DIR if set
        spellbook_dir = os.environ.get("SPELLBOOK_DIR")
        if spellbook_dir:
            version_path = Path(spellbook_dir) / ".version"
            if version_path.exists():
                return version_path.read_text(encoding="utf-8").strip()

        return "unknown"
    except OSError:
        return "unknown"


def _get_tool_names() -> List[str]:
    """Get list of registered MCP tool names.

    Supports both FastMCP v2 and v3:
    - v2: tools stored in mcp._tool_manager._tools dict
    - v3: tools stored in mcp._local_provider._components dict with 'tool:name@' keys
    """
    # FastMCP v2: tools in _tool_manager._tools dict
    try:
        return list(mcp._tool_manager._tools.keys())
    except AttributeError:
        pass

    # FastMCP v3: tools in _local_provider._components dict
    try:
        components = mcp._local_provider._components
        return [
            key.split(":", 1)[1].rsplit("@", 1)[0]
            for key in components
            if key.startswith("tool:")
        ]
    except AttributeError:
        return []


@mcp.tool()
@inject_recovery_context
async def spellbook_check_compaction(ctx: Context) -> dict:
    """
    Check for recent compaction events in the current session.

    Scans the current project's Claude Code session file for compaction
    markers and returns any pending context that should be recovered.

    Returns:
        {
            "compaction_detected": bool,
            "pending_context": dict | None,
            "session_file": str | None
        }
    """
    project_path = await get_project_path_from_context(ctx)

    # Check for new compaction events
    event = check_for_compaction(project_path)

    # Get any pending context
    pending = get_pending_context(project_path)

    return {
        "compaction_detected": event is not None,
        "pending_context": pending,
        "project_path": project_path,
    }


@mcp.tool()
@inject_recovery_context
async def spellbook_context_ping(ctx: Context) -> str:
    """
    Ping tool that checks for pending compaction recovery context.

    This tool can be called periodically or after any operation to check
    if context recovery is needed. If compaction was detected, it returns
    a <system-reminder> with recovery context.

    This is a TEST tool to validate whether <system-reminder> tags in
    MCP tool results are honored by Claude Code.

    Returns:
        String with <system-reminder> if recovery needed, otherwise simple ack
    """
    project_path = await get_project_path_from_context(ctx)

    # First, check for any new compaction events
    check_for_compaction(project_path)

    # Get pending context
    pending = get_pending_context(project_path)

    if pending:
        # Get current mode info for context (use session-isolated state)
        sid = _get_session_id(ctx)
        mode_info = session_mode_get(sid)
        mode_data = None

        if mode_info.get('mode') in ('fun', 'tarot'):
            # Fetch full mode info including persona
            init_result = session_init(sid)
            mode_data = init_result.get('mode', {})

        # Generate recovery reminder
        reminder = get_recovery_reminder(mode_data)

        # Mark as injected
        mark_context_injected(project_path)

        return f"Context recovery triggered.\n\n{reminder}"

    return "pong - no pending context recovery"


@mcp.tool()
@inject_recovery_context
def spellbook_health_check(full: bool = False) -> dict:
    """
    Check the health of the spellbook MCP server.

    Returns server status, version, available tools, and uptime.

    Useful for verifying the server is running and responsive.

    Automatically runs a full check:
    - On the first call after server start
    - Every 5 minutes (configurable via FULL_HEALTH_CHECK_INTERVAL_SECONDS)

    Args:
        full: If True, force comprehensive readiness check on all domains.
              If False (default), run quick liveness check unless auto-full triggers.

    Returns:
        {
            "status": "healthy",
            "version": "0.2.1",
            "tools_available": ["spellbook_session_init", ...],
            "uptime_seconds": 123.4,
            "domains": {...},  # Present when full check runs
            "checked_at": "2026-02-09T12:00:00Z"
        }
    """
    _server_start_time = _state.server_start_time

    # Determine if we should run a full check and why
    check_mode = "quick"
    run_full = False

    if full:
        # Explicit request always honored
        run_full = True
        check_mode = "full_explicit"
    elif not _state.first_health_check_done:
        # First check after server start should be full
        run_full = True
        check_mode = "full_first_call"
    elif (time.time() - _state.last_full_health_check_time) >= _state.FULL_HEALTH_CHECK_INTERVAL_SECONDS:
        # Periodic full check (every FULL_HEALTH_CHECK_INTERVAL_SECONDS)
        run_full = True
        check_mode = "full_periodic"

    # Get paths from environment or defaults
    config_dir = str(get_spellbook_config_dir())
    data_dir = os.environ.get(
        "SPELLBOOK_DATA_DIR",
        os.path.expanduser("~/.local/spellbook")
    )
    spellbook_dir = str(get_spellbook_dir())
    skills_dir = os.path.join(spellbook_dir, "skills")

    try:
        # Run health check
        result = run_health_check(
            db_path=get_db_path(),
            config_dir=config_dir,
            data_dir=data_dir,
            skills_dir=skills_dir,
            server_uptime=time.time() - _server_start_time,
            version=_get_version(),
            tools_available=_get_tool_names(),
            quick=not run_full,  # run_full=True means quick=False
        )

        # Update tracking state if we ran a full check
        if run_full:
            _state.first_health_check_done = True
            _state.last_full_health_check_time = time.time()

        # Convert dataclass to dict for JSON serialization
        result_dict = asdict(result)
        result_dict["uptime_seconds"] = round(result.uptime_seconds, 1)
        result_dict["check_mode"] = check_mode
        return result_dict
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": _get_version(),
            "uptime_seconds": round(time.time() - _server_start_time, 1),
        }
