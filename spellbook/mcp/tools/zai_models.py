"""MCP tools for z.AI model management.

Provides tools for listing models, getting model details, configuring
default models and task routing, setting API keys, and checking concurrency.
"""

__all__ = [
    "zai_list_models",
    "zai_get_model_info",
    "zai_set_default_model",
    "zai_configure_task_routing",
    "zai_set_api_key",
    "zai_concurrency_status",
]

from dataclasses import asdict
from typing import Optional

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook.sessions.injection import inject_recovery_context


def _get_registry():
    """Lazy import of ModelRegistry to avoid circular imports."""
    from spellbook.core.zai_models import get_registry
    return get_registry()


def _get_concurrency_manager():
    """Lazy import of ConcurrencyManager singleton."""
    from spellbook.core.concurrency import ConcurrencyManager
    return ConcurrencyManager()


@mcp.tool()
@inject_recovery_context
def zai_list_models(ctx: Context) -> dict:
    """List all available z.AI models with metadata.

    Returns a list of all registered models (built-in and user-configured)
    including their capabilities, concurrency limits, and use cases.

    Args:
        ctx: FastMCP request context (injected automatically).

    Returns:
        Dict with "models" list containing id, name, display_name,
        max_concurrent, context_size, description, use_cases,
        deprecated, and vision_capable for each model.
    """
    try:
        registry = _get_registry()
        models = registry.get_all_models()
        return {
            "models": [asdict(m) for m in models],
        }
    except Exception as e:
        return {"error": str(e), "models": []}


@mcp.tool()
@inject_recovery_context
def zai_get_model_info(ctx: Context, model_id: str) -> dict:
    """Get detailed info about a specific z.AI model including current concurrency.

    Returns all model metadata plus the current number of concurrent requests
    for the specified model.

    Args:
        ctx: FastMCP request context (injected automatically).
        model_id: The model identifier (e.g., "zai-coding-plan/glm-5").

    Returns:
        Dict with model fields plus "current_concurrent" usage count.

    Raises:
        ValueError: If the model_id is not found in the registry.
    """
    registry = _get_registry()
    model = registry.get_model(model_id)
    if model is None:
        raise ValueError(f"Model not found: {model_id}")

    try:
        manager = _get_concurrency_manager()
        current_concurrent = manager.get_current_usage(model_id)
    except Exception:
        current_concurrent = 0

    result = asdict(model)
    result["current_concurrent"] = current_concurrent
    return result


@mcp.tool()
@inject_recovery_context
def zai_set_default_model(ctx: Context, model_id: str) -> dict:
    """Set the default z.AI model.

    Validates that the model exists in the registry before persisting
    the preference to configuration.

    Args:
        ctx: FastMCP request context (injected automatically).
        model_id: The model identifier to set as default
            (e.g., "zai-coding-plan/glm-5").

    Returns:
        Dict with "status" and "model_id" on success.

    Raises:
        ValueError: If the model_id is not found in the registry.
    """
    registry = _get_registry()
    model = registry.get_model(model_id)
    if model is None:
        raise ValueError(f"Model not found: {model_id}")

    from spellbook.core.zai_config import set_zai_default_model
    set_zai_default_model(model_id)

    return {"status": "ok", "model_id": model_id}


@mcp.tool()
@inject_recovery_context
def zai_configure_task_routing(ctx: Context, routing_config: dict) -> dict:
    """Configure task-to-model routing for z.AI.

    Maps task types to model IDs. All model IDs in the routing values
    are validated against the registry before persisting.

    Args:
        ctx: FastMCP request context (injected automatically).
        routing_config: Dict mapping task names to model IDs
            (e.g., {"coding": "zai-coding-plan/glm-5", "review": "zai-coding-plan/glm-4.7"}).

    Returns:
        Dict with "status" and "routing_config" on success.

    Raises:
        ValueError: If any model ID in routing_config values is not found.
    """
    registry = _get_registry()

    # Validate all model IDs in routing values
    for task_name, model_id in routing_config.items():
        if not isinstance(model_id, str):
            raise ValueError(
                f"Model ID for task '{task_name}' must be a string, got {type(model_id).__name__}"
            )
        if registry.get_model(model_id) is None:
            raise ValueError(
                f"Model not found for task '{task_name}': {model_id}"
            )

    from spellbook.core.zai_config import set_zai_task_routing
    set_zai_task_routing(routing_config)

    return {"status": "ok", "routing_config": routing_config}


@mcp.tool()
@inject_recovery_context
def zai_set_api_key(ctx: Context, api_key: str) -> dict:
    """Set the z.AI API key.

    Persists the API key to spellbook configuration. The key must be
    at least 10 characters long.

    Args:
        ctx: FastMCP request context (injected automatically).
        api_key: The z.AI API key string (minimum 10 characters).

    Returns:
        Dict with "status" on success.

    Raises:
        ValueError: If api_key is empty or shorter than 10 characters.
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API key must be a non-empty string")
    if len(api_key) < 10:
        raise ValueError(
            f"API key must be at least 10 characters long, got {len(api_key)}"
        )

    from spellbook.core.zai_config import set_zai_api_key
    set_zai_api_key(api_key)

    return {"status": "ok"}


@mcp.tool()
@inject_recovery_context
def zai_concurrency_status(ctx: Context) -> dict:
    """Get current concurrency status for all z.AI models.

    Returns per-model usage counts and semaphore limits for monitoring
    and debugging concurrent request handling.

    Args:
        ctx: FastMCP request context (injected automatically).

    Returns:
        Dict with "models" containing per-model usage info dicts,
        each with "current_concurrent" and "limit" fields.
    """
    try:
        manager = _get_concurrency_manager()
        all_usage = manager.get_all_usage()
        registry = _get_registry()

        models_info = {}
        for model in registry.get_all_models():
            mid = model.id
            models_info[mid] = {
                "current_concurrent": all_usage.get(mid, 0),
                "limit": model.max_concurrent,
            }

        # Also include any models that have usage but aren't in registry
        for mid in all_usage:
            if mid not in models_info:
                models_info[mid] = {
                    "current_concurrent": all_usage[mid],
                    "limit": manager.get_semaphore_limit(mid),
                }

        return {"models": models_info}
    except Exception as e:
        return {"error": str(e), "models": {}}
