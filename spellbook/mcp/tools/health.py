"""MCP tools for health checks."""

__all__ = [
    "spellbook_health_check",
]

import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import List

from spellbook.mcp.server import mcp
from spellbook.mcp import state as _state
from spellbook.core.config import get_spellbook_dir
from spellbook.core.db import get_db_path
from spellbook.health.checker import run_health_check
from spellbook.sessions.injection import inject_recovery_context
from spellbook.core.path_utils import get_spellbook_config_dir

# Use shared state from spellbook.mcp.state for health check tracking


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


def get_tool_names() -> List[str]:
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
            tools_available=get_tool_names(),
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
