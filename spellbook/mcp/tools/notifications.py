"""MCP tools for OS notification management."""

__all__ = [
    "notify_send",
    "notify_status",
    "notify_session_set",
    "notify_config_set",
]

import json

from spellbook.mcp.server import mcp
from spellbook.notifications import notify as notify_module
from spellbook.core.config import (
    config_get,
    config_set_many,
    notify_session_set as do_notify_session_set,
)
from spellbook.sessions.injection import inject_recovery_context


# --- Notification Tools ---


@mcp.tool()
@inject_recovery_context
async def notify_send(body: str, title: str = None) -> str:
    """Send a system notification.

    Sends a native OS notification (macOS Notification Center, Linux notify-send,
    Windows toast). Use for manual notifications or testing.

    Args:
        body: Notification body text
        title: Notification title (default: resolved from config, usually "Spellbook")
    """
    result = await notify_module.send_notification(title=title, body=body)
    return json.dumps(result)


@mcp.tool()
@inject_recovery_context
async def notify_status() -> str:
    """Check notification system availability and current settings.

    Returns platform detection results, current enabled/title settings,
    and their resolution sources (session, config, or default).
    """
    result = notify_module.get_status()
    return json.dumps(result)


@mcp.tool()
@inject_recovery_context
async def notify_session_set(enabled: bool = None, title: str = None) -> str:
    """Override notification settings for this session only (in-memory).

    Changes persist until session ends. Use notify_config_set for permanent changes.

    Args:
        enabled: Enable/disable notifications for this session
        title: Override notification title for this session
    """
    result = do_notify_session_set(enabled=enabled, title=title)
    return json.dumps(result)


@mcp.tool()
@inject_recovery_context
async def notify_config_set(enabled: bool = None, title: str = None) -> str:
    """Change persistent notification settings (saved to spellbook.json).

    Changes persist across sessions. Use notify_session_set for temporary overrides.

    Args:
        enabled: Enable/disable notifications permanently
        title: Set default notification title permanently
    """
    updates = {}
    if enabled is not None:
        updates["notify_enabled"] = enabled
    if title is not None:
        updates["notify_title"] = title
    if updates:
        config_set_many(updates)

    current = {
        "notify_enabled": config_get("notify_enabled"),
        "notify_title": config_get("notify_title"),
    }
    return json.dumps({"status": "ok", "config": current})
