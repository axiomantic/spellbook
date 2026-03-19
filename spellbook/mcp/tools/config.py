"""MCP tools for configuration management."""

__all__ = [
    "spellbook_config_get",
    "spellbook_config_set",
    "spellbook_session_init",
    "spellbook_session_mode_set",
    "spellbook_session_mode_get",
    "spellbook_telemetry_enable",
    "spellbook_telemetry_disable",
    "spellbook_telemetry_status",
]

from typing import Optional

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook.core.config import (
    config_get,
    config_set,
    session_init,
    session_mode_get,
    session_mode_set,
)
from spellbook.sessions.injection import inject_recovery_context
from spellbook.core.path_utils import get_project_path_from_context


def _get_session_id(ctx: Optional[Context]) -> Optional[str]:
    """Extract session_id from Context if available.

    Returns None if ctx is None or request_context is not available,
    which signals to use default session for backward compatibility.
    """
    if ctx is None:
        return None
    try:
        return ctx.session_id
    except RuntimeError:
        # MCP session not established yet
        return None


@mcp.tool()
@inject_recovery_context
def spellbook_config_get(key: str):
    """
    Read a config value from spellbook configuration.

    Reads from ~/.config/spellbook/spellbook.json.

    Args:
        key: The config key to read (e.g., "fun_mode", "theme")

    Returns:
        The value for the key, or null if not set or file missing
    """
    return config_get(key)


@mcp.tool()
@inject_recovery_context
def spellbook_config_set(key: str, value) -> dict:
    """
    Write a config value to spellbook configuration.

    Writes to ~/.config/spellbook/spellbook.json.
    Creates the file and parent directories if they don't exist.
    Preserves other config values (read-modify-write).

    Args:
        key: The config key to set
        value: The value to set (any JSON-serializable value)

    Returns:
        {"status": "ok", "config": <full updated config>}
    """
    result = config_set(key, value)
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.CONFIG,
                event_type="config.updated",
                data={"key": key, "value": str(value)[:200]},
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def spellbook_session_init(ctx: Context) -> dict:
    """
    Initialize a spellbook session.

    Checks session state first (in-memory), then config file.
    Returns mode information for fun-mode or tarot-mode if enabled.

    Returns:
        {
            "mode": {"type": "fun"|"tarot"|"none"|"unset", ...mode-specific data},
            "fun_mode": "yes"|"no"|"unset"  // legacy key
        }
    """
    project_path = await get_project_path_from_context(ctx)
    return session_init(_get_session_id(ctx), project_path=project_path)


@mcp.tool()
@inject_recovery_context
def spellbook_session_mode_set(ctx: Context, mode: str, permanent: bool = False) -> dict:
    """
    Set session mode, optionally persisting to config.

    Args:
        mode: Mode to set ("fun", "tarot", "none")
        permanent: If True, save to config file. If False, session-only (resets on server restart).

    Returns:
        {"status": "ok", "mode": str, "permanent": bool}
    """
    return session_mode_set(mode, permanent, _get_session_id(ctx))


@mcp.tool()
@inject_recovery_context
def spellbook_session_mode_get(ctx: Context) -> dict:
    """
    Get current session mode state.

    Returns:
        {
            "mode": "fun"|"tarot"|"none"|null,
            "source": "session"|"config"|"config_legacy"|"unset",
            "permanent": bool
        }
    """
    return session_mode_get(_get_session_id(ctx))


@mcp.tool()
@inject_recovery_context
def spellbook_telemetry_enable(endpoint_url: str = None) -> dict:
    """Enable anonymous telemetry aggregation.

    Telemetry is opt-in and privacy-preserving:
    - No session IDs, project paths, or user data
    - No corrections (require content inspection)
    - Only bucketed durations and token counts
    - Minimum 5 samples before any aggregate is shared

    Args:
        endpoint_url: Custom endpoint (optional, future use)

    Returns:
        {"status": "enabled", "endpoint_url": str|None}
    """
    from spellbook.core.config import telemetry_enable as do_telemetry_enable

    return do_telemetry_enable(endpoint_url=endpoint_url)


@mcp.tool()
@inject_recovery_context
def spellbook_telemetry_disable() -> dict:
    """Disable telemetry. Local persistence continues unaffected.

    Returns:
        {"status": "disabled"}
    """
    from spellbook.core.config import telemetry_disable as do_telemetry_disable

    return do_telemetry_disable()


@mcp.tool()
@inject_recovery_context
def spellbook_telemetry_status() -> dict:
    """Get current telemetry configuration.

    Returns:
        {"enabled": bool, "endpoint_url": str|None, "last_sync": str|None}
    """
    from spellbook.core.config import telemetry_status as do_telemetry_status

    return do_telemetry_status()
