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

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.admin.routes.schemas import (
    ConfigBatchRequest,
    ConfigResponse,
    ConfigSetRequest,
    ErrorResponse,
    ErrorDetail,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# Known config keys with type, description, and defaults
CONFIG_SCHEMA = [
    {
        "key": "notify_enabled",
        "type": "boolean",
        "description": "Enable native OS notifications for long-running tool completions",
        "default": True,
    },
    {
        "key": "notify_title",
        "type": "string",
        "description": "Title for OS notifications",
        "default": "Spellbook",
    },
    {
        "key": "telemetry_enabled",
        "type": "boolean",
        "description": "Enable anonymous usage telemetry",
        "default": False,
    },
    {
        "key": "auto_update",
        "type": "boolean",
        "description": "Automatically check for and apply spellbook updates",
        "default": True,
    },
    {
        "key": "session_mode",
        "type": "string",
        "description": "Default session mode (fun, tarot, none)",
        "default": "none",
    },
    {
        "key": "admin_enabled",
        "type": "boolean",
        "description": "Whether the admin web interface is mounted on server startup",
        "default": True,
    },
    {
        "key": "profile.default",
        "type": "string",
        "description": (
            "Default session profile slug loaded at session_init "
            "(empty = no profile). Profiles live under "
            "skills/profiles/*/PROFILE.md."
        ),
        "default": "",
    },
    {
        "key": "worker_llm_base_url",
        "type": "string",
        "description": "OpenAI-compatible base URL, e.g., http://localhost:11434/v1",
        "default": "",
    },
    {
        "key": "worker_llm_model",
        "type": "string",
        "description": "Model id to send in worker LLM requests (e.g., qwen2.5-coder:7b)",
        "default": "",
    },
    {
        "key": "worker_llm_api_key",
        "type": "string",
        "description": "Bearer token for the worker LLM endpoint (plaintext; often empty for local servers)",
        "default": "",
    },
    {
        "key": "worker_llm_timeout_s",
        "type": "number",
        "description": "Per-call timeout in seconds for worker LLM requests",
        "default": 10.0,
    },
    {
        "key": "worker_llm_max_tokens",
        "type": "number",
        "description": "Max completion tokens per worker LLM request",
        "default": 1024,
    },
    {
        "key": "worker_llm_tool_safety_timeout_s",
        "type": "number",
        "description": "Short separate timeout (seconds) for PreToolUse tool-safety sniff",
        "default": 1.5,
    },
    {
        "key": "worker_llm_transcript_harvest_mode",
        "type": "string",
        "description": "Stop-hook harvest mode: 'replace' (worker supersedes regex) or 'merge'",
        "default": "replace",
    },
    {
        "key": "worker_llm_allow_prompt_overrides",
        "type": "boolean",
        "description": "Allow override prompts in ~/.local/spellbook/worker_prompts/*.md",
        "default": True,
    },
    {
        "key": "worker_llm_read_claude_memory",
        "type": "boolean",
        "description": (
            "Include Claude Code's ~/.claude/projects/<proj>/memory/ when recalling "
            "memories. Opt-in toggle; independent of worker LLM endpoint. Default "
            "False to preserve zero-change behavior for unconfigured users."
        ),
        "default": False,
    },
    {
        "key": "worker_llm_feature_transcript_harvest",
        "type": "boolean",
        "description": "Enable worker-LLM semantic Stop-hook memory harvest",
        "default": False,
    },
    {
        "key": "worker_llm_feature_roundtable",
        "type": "boolean",
        "description": "Enable local MCP roundtable execution via forge_roundtable_convene_local",
        "default": False,
    },
    {
        "key": "worker_llm_feature_memory_rerank",
        "type": "boolean",
        "description": "Enable worker-LLM reranking of memory_recall candidates",
        "default": False,
    },
    {
        "key": "worker_llm_feature_tool_safety",
        "type": "boolean",
        "description": "Enable worker-LLM PreToolUse tool-safety sniff (OK/WARN/BLOCK)",
        "default": False,
    },
    {
        "key": "worker_llm_safety_cache_ttl_s",
        "type": "number",
        "description": "Tool-safety verdict cache TTL (seconds)",
        "default": 300,
    },
]

CONFIG_DEFAULTS = {entry["key"]: entry["default"] for entry in CONFIG_SCHEMA}

KNOWN_KEYS = {entry["key"] for entry in CONFIG_SCHEMA}


# Per-key validators. Rejected values produce HTTP 400 with a machine-
# readable error code so admin UIs / scripted callers can surface the
# problem. Keep the dispatch table tiny — most keys are plain str/bool/
# number and need no additional validation beyond the schema type.
_ALLOWED_TRANSCRIPT_HARVEST_MODES = ("replace", "merge", "skip")


def _validate_config_value(key: str, value: Any) -> str | None:
    """Return an error string if ``value`` is invalid for ``key``, else None.

    M4 (Chunk 4 cleanup): ``worker_llm_transcript_harvest_mode`` only accepts
    ``replace`` | ``merge`` | ``skip``. A typo (e.g. ``replce``) would
    otherwise silently degrade the Stop hook to regex-only behavior because
    the consumer's default branch falls through to the regex path. Reject
    typos at config-set time so the operator sees the problem immediately.
    """
    if key == "worker_llm_transcript_harvest_mode":
        if not isinstance(value, str):
            return (
                "worker_llm_transcript_harvest_mode must be a string; got "
                f"{type(value).__name__}"
            )
        if value not in _ALLOWED_TRANSCRIPT_HARVEST_MODES:
            return (
                f"worker_llm_transcript_harvest_mode={value!r} is not one of "
                f"{list(_ALLOWED_TRANSCRIPT_HARVEST_MODES)}"
            )
    return None


def get_all_config() -> dict[str, Any]:
    """Read all config from spellbook.json."""
    from spellbook.core.config import get_config_path

    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def set_config_value(key: str, value: Any) -> dict:
    """Set a single config value via config_set."""
    from spellbook.core.config import config_set

    return config_set(key, value)


def batch_set_config(updates: dict[str, Any]) -> dict:
    """Set multiple config values in one atomic write."""
    from spellbook.core.config import config_set_many

    return config_set_many(updates)


@router.get("", response_model=ConfigResponse)
async def get_config(_session_id: str = Depends(require_admin_auth)):
    """Read all config from spellbook.json, with defaults filled in."""
    explicit = await asyncio.to_thread(get_all_config)
    config = {**CONFIG_DEFAULTS, **explicit}
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

    validation_error = _validate_config_value(key, body.value)
    if validation_error:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="CONFIG_VALUE_INVALID",
                    message=validation_error,
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

    # Per-key value validation. Reject the whole batch atomically on the
    # first invalid value so a partial apply never lands.
    for _k, _v in body.updates.items():
        _err = _validate_config_value(_k, _v)
        if _err:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="CONFIG_VALUE_INVALID",
                        message=_err,
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
