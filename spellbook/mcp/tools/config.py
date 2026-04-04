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

import asyncio
import logging
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
# detect_git_context, derive_messaging_alias, and message_bus are referenced
# via their source modules (_path_utils, _bus) so that asyncio.to_thread()
# picks up test mocks patched on the source module (bigfoot patches module
# attrs, not caller-local references).
import spellbook.core.path_utils as _path_utils
import spellbook.messaging.bus as _bus

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
async def spellbook_session_init(
    ctx: Context,
    session_name: Optional[str] = None,
    continuation_message: Optional[str] = None,
) -> dict:
    """
    Initialize a spellbook session.

    Checks session state first (in-memory), then config file.
    Returns mode information for fun-mode or tarot-mode if enabled.
    Automatically registers the session for cross-session messaging.

    Args:
        session_name: Optional explicit alias for this session. If provided,
            used as-is (after slugify) instead of git-derived alias.
        continuation_message: User's first message for resume detection.

    Returns:
        {
            "mode": {"type": "fun"|"tarot"|"none"|"unset", ...mode-specific data},
            "fun_mode": "yes"|"no"|"unset",  // legacy key
            "messaging": {"registered": bool, "alias": str|None, ...}
        }
    """
    project_path = await get_project_path_from_context(ctx)
    session_id = _get_session_id(ctx) or ""

    # 1. Core session init (sync, unchanged)
    result = session_init(
        session_id or None,
        continuation_message=continuation_message,
        project_path=project_path,
    )

    # 2. Auto-register for messaging (async, best-effort)
    try:
        # detect_git_context() runs sync subprocess calls.
        # Wrap in asyncio.to_thread() to avoid blocking the event loop.
        try:
            git_ctx = await asyncio.to_thread(
                _path_utils.detect_git_context, project_path
            )
        except Exception:
            logger.debug("Git context detection failed", exc_info=True)
            git_ctx = None

        # derive_messaging_alias uses git_context.repo_root (populated by
        # detect_git_context above) so it avoids subprocess calls in the
        # common case. No need for asyncio.to_thread here.
        base_alias = _path_utils.derive_messaging_alias(
            project_path,
            session_name=session_name,
            git_context=git_ctx,
        )

        actual_alias, was_replaced = await _bus.message_bus.register_with_suffix(
            base_alias=base_alias,
            session_id=session_id,
            enable_sse=True,
        )

        result["messaging"] = {
            "registered": True,
            "alias": actual_alias,
            "was_compaction": was_replaced,
        }

    except Exception as exc:
        logger.warning("Messaging auto-register failed: %s", exc)
        result["messaging"] = {
            "registered": False,
            "error": str(exc),
        }

    return result


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
