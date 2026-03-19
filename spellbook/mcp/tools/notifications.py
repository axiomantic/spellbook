"""MCP tools for TTS and notification management."""

import json

from spellbook.mcp.server import mcp
from spellbook import notify as notify_module
from spellbook import tts as tts_module
from spellbook.core.config import (
    config_get,
    config_set_many,
    notify_session_set as do_notify_session_set,
    tts_session_set as do_tts_session_set,
)
from spellbook.sessions.injection import inject_recovery_context


# --- TTS Tools ---


@mcp.tool()
@inject_recovery_context
async def kokoro_speak(
    text: str,
    voice: str = None,
    volume: float = None,
    session_id: str = None,
) -> dict:
    """
    Generate speech from text using Kokoro TTS and play it.

    Lazy-loads the Kokoro model on first call (~20-30s). Subsequent calls
    are fast (~2s). Audio plays through the default system output device.

    Args:
        text: Text to speak (required)
        voice: Kokoro voice ID (default: config or "af_heart")
        volume: Playback volume 0.0-1.0 (default: config or 0.3)
        session_id: Session identifier for settings resolution (auto-detected if omitted)

    Returns:
        {"ok": true, "elapsed": float, "wav_path": str} on success
        {"error": str} on failure
    """
    if len(text) > 5000:
        return {"error": "text exceeds 5000 character limit"}
    return await tts_module.speak(text, voice=voice, volume=volume, session_id=session_id)


@mcp.tool()
@inject_recovery_context
def kokoro_status(session_id: str = None) -> dict:
    """
    Check TTS availability and current settings.

    Args:
        session_id: Session identifier for settings resolution (auto-detected if omitted)

    Returns:
        {
            "available": bool,       # kokoro importable
            "enabled": bool,         # resolved via session > config > default
            "model_loaded": bool,    # KPipeline cached
            "voice": str,            # effective voice
            "volume": float,         # effective volume
            "error": str | None      # if not available, why
        }
    """
    return tts_module.get_status(session_id=session_id)


@mcp.tool()
@inject_recovery_context
def tts_session_set(
    enabled: bool = None,
    voice: str = None,
    volume: float = None,
    session_id: str = None,
) -> dict:
    """
    Override TTS settings for this session only (not persisted).

    Pass only the settings you want to change. Omitted settings keep current value.

    Args:
        enabled: Enable/disable TTS for this session
        voice: Override voice for this session
        volume: Override volume for this session (0.0-1.0)
        session_id: Session identifier (auto-detected if omitted)

    Returns:
        {"status": "ok", "session_tts": dict_of_current_overrides}
    """
    return do_tts_session_set(
        enabled=enabled, voice=voice, volume=volume, session_id=session_id
    )


@mcp.tool()
@inject_recovery_context
def tts_config_set(
    enabled: bool = None,
    voice: str = None,
    volume: float = None,
) -> dict:
    """
    Persistently change TTS configuration.

    Pass only the settings you want to change. Omitted settings keep current value.

    Args:
        enabled: Enable/disable TTS globally
        voice: Default voice ID (e.g., "af_heart", "bf_emma")
        volume: Default volume 0.0-1.0

    Returns:
        {"status": "ok", "config": {tts_enabled, tts_voice, tts_volume}} with
        updated keys from this call plus current values for unchanged keys.
    """
    updates = {}
    if enabled is not None:
        updates["tts_enabled"] = enabled
    if voice is not None:
        updates["tts_voice"] = voice
    if volume is not None:
        updates["tts_volume"] = volume

    if updates:
        r = config_set_many(updates)
        result_config = r.get("config", {})
    else:
        result_config = {
            "tts_enabled": config_get("tts_enabled"),
            "tts_voice": config_get("tts_voice"),
            "tts_volume": config_get("tts_volume"),
        }

    return {"status": "ok", "config": result_config}


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
