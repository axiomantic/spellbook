"""MCP tools for update checking."""

__all__ = [
    "spellbook_check_for_updates",
    "spellbook_get_update_status",
]

from spellbook.mcp.server import mcp
from spellbook.core.config import get_spellbook_dir
from spellbook.sessions.injection import inject_recovery_context
from spellbook.updates.tools import (
    apply_update as do_apply_update,
    check_for_updates as do_check_for_updates,
    get_update_status as do_get_update_status,
)


@mcp.tool()
@inject_recovery_context
def spellbook_check_for_updates(
    auto_apply: bool = False,
) -> dict:
    """
    Check for spellbook updates and optionally apply them.

    Performs a git fetch to check if a newer version of spellbook is
    available. If auto_apply is True and an update is available (and not
    a major version bump), applies it immediately.

    Args:
        auto_apply: If True, apply the update if available and not a
                    major version bump (default: False).

    Returns:
        {
            "update_available": bool,
            "current_version": str,
            "remote_version": str | None,
            "is_major_bump": bool,
            "changelog": str | None,
            "applied": bool,
            "error": str | None,
        }
    """
    spellbook_dir = get_spellbook_dir()
    result = do_check_for_updates(spellbook_dir)
    result["applied"] = False

    if (
        auto_apply
        and result.get("update_available")
        and not result.get("is_major_bump")
        and not result.get("error")
    ):
        apply_result = do_apply_update(spellbook_dir)
        result["applied"] = apply_result.get("success", False)
        if not apply_result.get("success"):
            result["error"] = apply_result.get("error")

    return result


@mcp.tool()
@inject_recovery_context
def spellbook_get_update_status() -> dict:
    """
    Get the current update status without triggering a new check.

    Aggregates all update-related config keys into a single response.

    Returns:
        {
            "auto_update_enabled": bool,
            "auto_update_paused": bool,
            "current_version": str,
            "available_update": dict | None,
            "pending_major_update": dict | None,
            "last_auto_update": dict | None,
            "pre_update_sha": str | None,
            "last_check": str | None,
            "check_failures": int,
        }
    """
    spellbook_dir = get_spellbook_dir()
    return do_get_update_status(spellbook_dir)
