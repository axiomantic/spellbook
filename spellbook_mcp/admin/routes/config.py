"""Config editor API routes.

Provides endpoints for reading, updating, and introspecting spellbook
configuration keys stored in ~/.config/spellbook/spellbook.json.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.events import Event, Subsystem, event_bus
from spellbook_mcp.admin.routes.schemas import (
    ConfigBatchRequest,
    ConfigResponse,
    ConfigSetRequest,
    ErrorResponse,
    ErrorDetail,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# Known config keys with type and description
CONFIG_SCHEMA = [
    {
        "key": "tts_enabled",
        "type": "boolean",
        "description": "Enable text-to-speech announcements for long-running tool completions",
    },
    {
        "key": "tts_voice",
        "type": "string",
        "description": "Kokoro voice ID for TTS (e.g. bf_emma, af_heart)",
    },
    {
        "key": "tts_volume",
        "type": "number",
        "description": "TTS playback volume (0.0 to 1.0)",
    },
    {
        "key": "notify_enabled",
        "type": "boolean",
        "description": "Enable native OS notifications for long-running tool completions",
    },
    {
        "key": "notify_title",
        "type": "string",
        "description": "Title for OS notifications",
    },
    {
        "key": "telemetry_enabled",
        "type": "boolean",
        "description": "Enable anonymous usage telemetry",
    },
    {
        "key": "auto_update",
        "type": "boolean",
        "description": "Automatically check for and apply spellbook updates",
    },
    {
        "key": "session_mode",
        "type": "string",
        "description": "Default session mode (fun, tarot, none)",
    },
    {
        "key": "admin_enabled",
        "type": "boolean",
        "description": "Whether the admin web interface is mounted on server startup",
    },
]

KNOWN_KEYS = {entry["key"] for entry in CONFIG_SCHEMA}


def get_all_config() -> dict[str, Any]:
    """Read all config from spellbook.json."""
    from spellbook_mcp.config_tools import get_config_path

    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def set_config_value(key: str, value: Any) -> dict:
    """Set a single config value via config_set."""
    from spellbook_mcp.config_tools import config_set

    return config_set(key, value)


def batch_set_config(updates: dict[str, Any]) -> dict:
    """Set multiple config values in one atomic write."""
    from spellbook_mcp.config_tools import config_set_many

    return config_set_many(updates)


@router.get("", response_model=ConfigResponse)
async def get_config(_session_id: str = Depends(require_admin_auth)):
    """Read all config from spellbook.json."""
    config = await asyncio.to_thread(get_all_config)
    return ConfigResponse(config=config)


@router.get("/schema")
async def get_config_schema(_session_id: str = Depends(require_admin_auth)):
    """Return known config keys with types and descriptions."""
    return {"keys": CONFIG_SCHEMA}


@router.put("/{key}")
async def update_config_key(
    key: str,
    body: ConfigSetRequest,
    _session_id: str = Depends(require_admin_auth),
):
    """Update a single config key."""
    if key not in KNOWN_KEYS:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="CONFIG_KEY_UNKNOWN",
                    message=f"Unknown config key: {key}",
                )
            ).model_dump(),
        )

    result = await asyncio.to_thread(set_config_value, key, body.value)

    await event_bus.publish(
        Event(
            subsystem=Subsystem.CONFIG,
            event_type="config.updated",
            data={"key": key, "value": body.value},
        )
    )

    return {"status": "ok", "key": key, "value": body.value}


@router.put("")
async def batch_update_config(
    body: ConfigBatchRequest,
    _session_id: str = Depends(require_admin_auth),
):
    """Batch update multiple config keys."""
    # Validate all keys first
    unknown = set(body.updates.keys()) - KNOWN_KEYS
    if unknown:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="CONFIG_KEY_UNKNOWN",
                    message=f"Unknown config key(s): {', '.join(sorted(unknown))}",
                )
            ).model_dump(),
        )

    result = await asyncio.to_thread(batch_set_config, body.updates)

    for key, value in body.updates.items():
        await event_bus.publish(
            Event(
                subsystem=Subsystem.CONFIG,
                event_type="config.updated",
                data={"key": key, "value": value},
            )
        )

    return {"status": "ok", "updated": list(body.updates.keys())}
