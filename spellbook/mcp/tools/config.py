"""MCP tools for configuration management."""

__all__ = [
    "spellbook_config_get",
    "spellbook_config_set",
    "spellbook_session_init",
    "spellbook_session_mode_set",
    "spellbook_session_mode_get",
]

import logging
from typing import Any, Optional

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

logger = logging.getLogger(__name__)


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
async def spellbook_config_set(key: str, value: Any) -> dict:
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
        logger.exception("Failed to publish config.updated event")

    return result


@mcp.tool()
@inject_recovery_context
async def spellbook_session_init(
    ctx: Context,
    session_name: Optional[str] = None,
    continuation_message: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    """
    Initialize a spellbook session.

    Checks session state first (in-memory), then config file.
    Returns mode information for fun-mode or tarot-mode if enabled.

    Args:
        session_name: Reserved for future use.
        continuation_message: User's first message for resume detection.
        platform: LLM platform self-identification. The calling LLM should
            identify itself from its own system prompt. Valid values:
            "claude_code", "opencode", "codex", "gemini".

    Returns:
        {
            "mode": {"type": "fun"|"tarot"|"none"|"unset", ...mode-specific data},
            "fun_mode": "yes"|"no"|"unset",  // legacy key
            "platform": str|null,
        }
    """
    del session_name  # Reserved for future use.
    project_path = await get_project_path_from_context(ctx)
    session_id = _get_session_id(ctx) or ""

    return session_init(
        session_id or None,
        continuation_message=continuation_message,
        project_path=project_path,
        platform=platform,
    )


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


