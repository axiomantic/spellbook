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
        "description": (
            "Stop-hook harvest mode: 'replace' (worker supersedes regex), "
            "'merge' (combine worker + regex), or 'skip' (disable worker "
            "harvest; regex-only)"
        ),
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
    # Worker LLM observability — design §7. The purge loop and threshold
    # notifier read these via config_get; schema entries surface them to the
    # admin UI.
    {
        "key": "worker_llm_observability_retention_hours",
        "type": "number",
        "description": (
            "Retention window (hours) for worker_llm_calls rows before the "
            "batched purge loop deletes them"
        ),
        "default": 24,
    },
    {
        "key": "worker_llm_observability_max_rows",
        "type": "number",
        "description": (
            "Hard ceiling on the number of worker_llm_calls rows kept; the "
            "count-cap branch of the purge loop trims overflow above this"
        ),
        "default": 10000,
    },
    {
        "key": "worker_llm_observability_purge_interval_seconds",
        "type": "number",
        "description": (
            "Sleep interval (seconds) between purge loop iterations; "
            "clamped to a minimum of 10s inside the loop"
        ),
        "default": 300,
    },
    {
        "key": "worker_llm_observability_notify_enabled",
        "type": "boolean",
        "description": (
            "Enable edge-triggered OS notifications when the worker-LLM "
            "success rate crosses the breach/recovery threshold"
        ),
        "default": False,
    },
    {
        "key": "worker_llm_observability_notify_threshold",
        "type": "number",
        "description": (
            "Success-rate floor (0.0-1.0) for the threshold notifier; "
            "falling below triggers a breach, recovering above triggers a "
            "recovery notification"
        ),
        "default": 0.8,
    },
    {
        "key": "worker_llm_observability_notify_window",
        "type": "number",
        "description": (
            "Number of most-recent worker_llm_calls rows evaluated when "
            "computing the success rate for the threshold notifier; "
            "evaluations with fewer rows are skipped"
        ),
        "default": 20,
    },
    {
        "key": "worker_llm_observability_notify_eval_interval_seconds",
        "type": "number",
        "description": (
            "Sleep interval (seconds) between threshold-evaluator "
            "iterations; clamped to a minimum of 10s inside the loop"
        ),
        "default": 60,
    },
    # Worker LLM async queue (fire-and-forget). When enabled, the daemon
    # spawns a background consumer that drains queued tasks so callers like
    # the Stop-hook transcript_harvest do not block on the worker endpoint.
    {
        "key": "worker_llm_queue_enabled",
        "type": "boolean",
        "description": (
            "Opt-in async enqueue of fire-and-forget worker-LLM calls. "
            "When True, the daemon runs a consumer task that drains the "
            "queue; callers (transcript_harvest, tool_safety warm probe) "
            "return immediately instead of blocking on client.call_sync."
        ),
        "default": False,
    },
    {
        "key": "worker_llm_queue_max_depth",
        "type": "number",
        "description": (
            "Bound on the async queue depth. When full, the OLDEST task is "
            "dropped (the incoming task is the most recent signal); each "
            "drop publishes a call event with status='dropped' so overflow "
            "is observable."
        ),
        "default": 256,
    },
    {
        "key": "worker_llm_tool_safety_cold_threshold_s",
        "type": "number",
        "description": (
            "If the last successful worker-LLM call is older than this, "
            "treat siesta as cold: PreToolUse tool_safety returns fail-open "
            "immediately and kicks off a background warmup via the queue."
        ),
        "default": 45.0,
    },
    # --- General / session -------------------------------------------------
    {
        "key": "fun_mode",
        "type": "boolean",
        "description": (
            "Legacy fun-mode flag. Honored by session_init when ``session_mode`` "
            "is unset; prefer ``session_mode`` for new installs."
        ),
        "default": False,
    },
    {
        "key": "persona",
        "type": "string",
        "description": (
            "Free-form persona directive carried into fun-mode session greetings."
        ),
        "default": "",
    },
    # --- Security / Spotlighting ------------------------------------------
    {
        "key": "security.spotlighting.enabled",
        "type": "boolean",
        "description": "Enable spotlighting (prompt-injection delimiters around untrusted content).",
        "default": True,
    },
    {
        "key": "security.spotlighting.tier",
        "type": "string",
        "description": (
            "Spotlighting aggressiveness tier. One of: basic, standard, strict."
        ),
        "default": "standard",
    },
    {
        "key": "security.spotlighting.mcp_wrap",
        "type": "boolean",
        "description": "Wrap MCP tool results in spotlighting delimiters before returning to the model.",
        "default": True,
    },
    {
        "key": "security.spotlighting.custom_prefix",
        "type": "string",
        "description": "Optional custom prefix prepended to spotlighting envelopes.",
        "default": "",
    },
    # --- Security / Crypto -------------------------------------------------
    {
        "key": "security.crypto.enabled",
        "type": "boolean",
        "description": "Enable crypto-signed workflow and config gate verification.",
        "default": True,
    },
    {
        "key": "security.crypto.keys_dir",
        "type": "string",
        "description": "Directory holding spellbook signing keys.",
        "default": "~/.local/spellbook/keys",
    },
    {
        "key": "security.crypto.gate_spawn_session",
        "type": "boolean",
        "description": "Require a valid signature before spawn_session accepts workflow state.",
        "default": True,
    },
    {
        "key": "security.crypto.gate_workflow_save",
        "type": "boolean",
        "description": "Require a valid signature before workflow save operations are accepted.",
        "default": True,
    },
    {
        "key": "security.crypto.gate_config_writes",
        "type": "boolean",
        "description": "Require a valid signature for config writes (off by default; noisy).",
        "default": False,
    },
    {
        "key": "security.crypto.auto_sign_on_install",
        "type": "boolean",
        "description": "Automatically sign installed artifacts during spellbook install.",
        "default": True,
    },
    # --- Security / Sleuth -------------------------------------------------
    {
        "key": "security.sleuth.enabled",
        "type": "boolean",
        "description": "Enable Sleuth LLM-based prompt-injection classifier.",
        "default": False,
    },
    {
        "key": "security.sleuth.api_key",
        "type": "string",
        "description": "API key for the Sleuth backend (stored in plaintext; masked in GET responses).",
        "default": "",
        "secret": True,
    },
    {
        "key": "security.sleuth.max_content_bytes",
        "type": "number",
        "description": "Maximum bytes of content sent to Sleuth per check.",
        "default": 50000,
    },
    {
        "key": "security.sleuth.max_tokens_per_check",
        "type": "number",
        "description": "Maximum completion tokens per Sleuth check.",
        "default": 1024,
    },
    {
        "key": "security.sleuth.calls_per_session",
        "type": "number",
        "description": "Hard cap on Sleuth calls per session before falling back.",
        "default": 50,
    },
    {
        "key": "security.sleuth.confidence_threshold",
        "type": "number",
        "description": "Minimum classifier confidence (0.0 - 1.0) to act on a Sleuth verdict.",
        "default": 0.8,
    },
    {
        "key": "security.sleuth.cache_ttl_seconds",
        "type": "number",
        "description": "TTL (seconds) for cached Sleuth verdicts.",
        "default": 3600,
    },
    {
        "key": "security.sleuth.timeout_seconds",
        "type": "number",
        "description": "Per-call timeout (seconds) for Sleuth requests.",
        "default": 5,
    },
    {
        "key": "security.sleuth.fallback_on_budget_exceeded",
        "type": "string",
        "description": (
            "Behaviour when Sleuth budget is exhausted. Typically 'regex_only' "
            "(fall back to regex scanner) or 'allow'."
        ),
        "default": "regex_only",
    },
    # --- Security / LODO ---------------------------------------------------
    {
        "key": "security.lodo.datasets_dir",
        "type": "string",
        "description": "Directory containing LODO (leave-one-dataset-out) evaluation datasets.",
        "default": "tests/test_security/datasets",
    },
    {
        "key": "security.lodo.min_detection_rate",
        "type": "number",
        "description": "Minimum detection rate (0.0 - 1.0) required by LODO evaluation gates.",
        "default": 0.85,
    },
    {
        "key": "security.lodo.max_false_positive_rate",
        "type": "number",
        "description": "Maximum false-positive rate (0.0 - 1.0) tolerated by LODO evaluation gates.",
        "default": 0.05,
    },
]

CONFIG_DEFAULTS = {entry["key"]: entry["default"] for entry in CONFIG_SCHEMA}

KNOWN_KEYS = {entry["key"] for entry in CONFIG_SCHEMA}

# Keys whose values must be masked in ``GET /api/config`` responses. Set via
# ``"secret": True`` in CONFIG_SCHEMA; admins editing the value see the fact
# that it is set without the plaintext leaking through a logged response.
SECRET_KEYS: frozenset[str] = frozenset(
    entry["key"] for entry in CONFIG_SCHEMA if entry.get("secret") is True
)

# Sentinel returned in place of a set secret. Matches the convention commonly
# shown in config UIs so users recognize "value is present but hidden".
_SECRET_MASK = "***"


def _mask_secrets(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *config* with secret values replaced by a mask.

    A secret is masked as ``"***"`` when it holds any non-empty value, and as
    an empty string when unset. Writes are not intercepted; callers that PUT a
    value go through the normal path.
    """
    masked = dict(config)
    for key in SECRET_KEYS:
        if key in masked:
            value = masked[key]
            masked[key] = _SECRET_MASK if value else ""
    return masked


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
    """Read all config from spellbook.json, with defaults filled in.

    Secret keys (``"secret": True`` in CONFIG_SCHEMA) are masked in the
    response so plaintext never leaves the daemon in a GET. Writes via PUT go
    through the normal path.
    """
    explicit = await asyncio.to_thread(get_all_config)
    config = {**CONFIG_DEFAULTS, **explicit}
    return ConfigResponse(config=_mask_secrets(config))


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
