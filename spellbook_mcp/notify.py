"""Native OS notification integration - platform detection with async-safe wrappers.

All public functions are designed to be called from async context.
Synchronous subprocess calls are wrapped in asyncio.to_thread().
"""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from typing import Any, Optional

from spellbook_mcp import config_tools
from spellbook_mcp.config_tools import NOTIFY_DEFAULT_ENABLED, NOTIFY_DEFAULT_TITLE

logger = logging.getLogger(__name__)

# Module-level state
_notification_available: Optional[bool] = None  # None = not checked yet
_platform: Optional[str] = None  # "macos", "linux", "windows", or None
_unavailable_reason: Optional[str] = None  # Human-readable reason if unavailable


def _detect_platform() -> tuple[Optional[str], Optional[str]]:
    """Detect the notification platform.

    Detection order: container check first (a Docker container running Linux
    has notify-send but no display server), then SSH/headless check, then
    platform-specific tool detection.

    Returns:
        (platform, reason) where platform is "macos"/"linux"/"windows" or None,
        and reason is None on success or a diagnostic string on failure.
    """
    # Container detection (check before platform, as containers may report linux)
    if os.path.exists("/.dockerenv") or os.environ.get("container"):
        return None, "Running in a container (no display server)"

    # SSH/headless detection
    if os.environ.get("SSH_TTY"):
        # SSH session: only available if X11/Wayland forwarding is active
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return None, "SSH session without X11/Wayland forwarding"

    if sys.platform == "darwin":
        if shutil.which("osascript"):
            return "macos", None
        return None, "macOS: osascript not found"
    elif sys.platform == "linux":
        if not shutil.which("notify-send"):
            return None, "Linux: notify-send not found (install libnotify-bin or libnotify)"
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return None, "Linux: no DISPLAY or WAYLAND_DISPLAY set (headless session)"
        return "linux", None
    elif sys.platform == "win32":
        if shutil.which("pwsh") or shutil.which("powershell"):
            return "windows", None
        return None, "Windows: neither pwsh nor powershell found"

    return None, "Unknown platform or missing notification tools"


def check_availability() -> dict:
    """Check if system notifications are available on this platform.

    Caches result after first call. On macOS, sends a test notification
    to trigger the OS permission dialog (osascript display notification
    requires explicit user permission grant).

    Returns:
        Dict with available, platform, reason keys.
    """
    global _notification_available, _platform, _unavailable_reason

    if _notification_available is not None:
        return {
            "available": _notification_available,
            "platform": _platform,
            "reason": _unavailable_reason,
        }

    _platform, _unavailable_reason = _detect_platform()

    if _platform is None:
        _notification_available = False
        return {
            "available": False,
            "platform": None,
            "reason": _unavailable_reason,
        }

    # macOS: send a test notification to trigger permission dialog
    if _platform == "macos":
        try:
            subprocess.run(
                ["osascript", "-e",
                 'display notification "Spellbook notifications enabled" '
                 'with title "Spellbook"'],
                capture_output=True, timeout=5, check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            _notification_available = False
            _unavailable_reason = f"macOS notification test failed: {e}"
            logger.warning(_unavailable_reason)
            return {
                "available": False,
                "platform": _platform,
                "reason": _unavailable_reason,
            }

    _notification_available = True
    _unavailable_reason = None
    return {
        "available": True,
        "platform": _platform,
        "reason": None,
    }


def _resolve_setting(
    key: str,
    explicit_value: Any = None,
    session_id: Optional[str] = None,
) -> Any:
    """Resolve a notification setting using the priority chain.

    Priority: explicit parameter > session override > persistent config > default.

    Args:
        key: Setting key ("enabled", "title").
        explicit_value: Value passed directly to a tool call.
        session_id: Session ID for session override lookup.

    Returns:
        The resolved setting value.
    """
    if explicit_value is not None:
        return explicit_value

    # Check session override
    session = config_tools._get_session_state(session_id)
    session_value = session.get("notify", {}).get(key)
    if session_value is not None:
        return session_value

    # Check persistent config
    config_value = config_tools.config_get(f"notify_{key}")
    if config_value is not None:
        return config_value

    # Default
    defaults = {
        "enabled": NOTIFY_DEFAULT_ENABLED,
        "title": NOTIFY_DEFAULT_TITLE,
    }
    return defaults.get(key)


def _send_sync(title: str, body: str) -> None:
    """Send a notification using the detected platform tool. Blocking call.

    Args:
        title: Notification title.
        body: Notification body text.

    Raises:
        subprocess.CalledProcessError: If the notification command fails.
        subprocess.TimeoutExpired: If the notification command times out.
        RuntimeError: If no notification platform is detected.
    """
    # Normalize newlines to spaces (notification UIs don't handle \n well)
    title = title.replace("\n", " ").strip()
    body = body.replace("\n", " ").strip()

    if _platform == "macos":
        # Escape backslash and double-quote for AppleScript
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{safe_body}" with title "{safe_title}"'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=5, check=True,
        )
    elif _platform == "linux":
        subprocess.run(
            ["notify-send", title, body],
            capture_output=True, timeout=5, check=True,
        )
    elif _platform == "windows":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        # Escape single quotes for PowerShell string literals
        ps_title = title.replace("'", "''")
        ps_body = body.replace("'", "''")
        # Use BurntToast if available, fall back to .NET toast API
        ps_script = (
            f"try {{ New-BurntToastNotification -Text '{ps_title}','{ps_body}' }} "
            f"catch {{ "
            f"[Windows.UI.Notifications.ToastNotificationManager, "
            f"Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
            f"$xml = [Windows.UI.Notifications.ToastNotificationManager]"
            f"::GetTemplateContent(1); "
            f"$text = $xml.GetElementsByTagName('text'); "
            f"$text[0].AppendChild($xml.CreateTextNode('{ps_title}')) | Out-Null; "
            f"$text[1].AppendChild($xml.CreateTextNode('{ps_body}')) | Out-Null; "
            f"$notifier = [Windows.UI.Notifications.ToastNotificationManager]"
            f"::CreateToastNotifier('Spellbook'); "
            f"$notifier.Show([Windows.UI.Notifications.ToastNotification]"
            f"::new($xml)) }}"
        )
        subprocess.run(
            [shell, "-Command", ps_script],
            capture_output=True, timeout=10, check=True,
        )
    else:
        raise RuntimeError(f"No notification platform detected (platform={_platform})")


def get_status(session_id: Optional[str] = None) -> dict:
    """Get notification availability and current settings.

    Triggers availability check on first call. Safe to call at any time.

    Args:
        session_id: Session ID for settings resolution.

    Returns:
        Dict with available, enabled, platform, title, error keys.
    """
    result = check_availability()
    available = result["available"]
    return {
        "available": available,
        "enabled": _resolve_setting("enabled", session_id=session_id),
        "platform": _platform,
        "title": _resolve_setting("title", session_id=session_id),
        "error": _unavailable_reason if not available else None,
    }


async def send_notification(
    title: str = None,
    body: str = "",
    session_id: Optional[str] = None,
) -> dict:
    """Send a system notification. Main async entry point.

    Args:
        title: Notification title (default: resolved from config).
        body: Notification body text.
        session_id: Session ID for settings resolution.

    Returns:
        {"ok": True} on success.
        {"error": str} on failure.
    """
    if not check_availability()["available"]:
        return {"error": f"Notifications not available. {_unavailable_reason}"}

    effective_enabled = _resolve_setting("enabled", session_id=session_id)
    if not effective_enabled:
        return {
            "error": "Notifications disabled. Enable with notify_config_set(enabled=true) "
            "or notify_session_set(enabled=true)"
        }

    effective_title = _resolve_setting(
        "title", explicit_value=title, session_id=session_id
    )

    try:
        await asyncio.to_thread(_send_sync, effective_title, body)
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Notification failed: {e}")
        return {"error": f"Notification failed: {e}"}
