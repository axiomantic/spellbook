"""Typed access functions for z.AI configuration.

Provides convenience wrappers around config_get/config_set for z.AI-specific
keys, with sensible defaults and environment variable support for API keys.
"""

import os
from typing import Any, Optional

from spellbook.core.config import config_get, config_set

ZAI_DEFAULT_MODEL_ID = "glm-4.7"


def get_zai_default_model() -> str:
    """Return the configured default model ID, or 'glm-4.7' if unset."""
    return config_get("zai_default_model") or ZAI_DEFAULT_MODEL_ID


def set_zai_default_model(model_id: str) -> None:
    """Persist the default model ID to config."""
    config_set("zai_default_model", model_id)


def get_zai_api_key() -> Optional[str]:
    """Return the z.AI API key.

    Resolution order: ZAI_API_KEY environment variable, then config.
    Returns None if neither source has a key.
    """
    env_key = os.environ.get("ZAI_API_KEY")
    if env_key:
        return env_key
    return config_get("zai_api_key")


def set_zai_api_key(api_key: str) -> None:
    """Persist the API key to config."""
    config_set("zai_api_key", api_key)


def get_zai_task_routing() -> dict:
    """Return task-to-model routing configuration, or empty dict if unset."""
    return config_get("zai_task_routing") or {}


def set_zai_task_routing(routing: dict) -> None:
    """Persist task-to-model routing configuration."""
    config_set("zai_task_routing", routing)


def get_zai_concurrency_limits() -> dict:
    """Return concurrency limits configuration, or empty dict if unset."""
    return config_get("zai_concurrency_limits") or {}


def get_zai_models_config() -> list:
    """Return user-configured model definitions, or empty list if unset."""
    return config_get("zai_models") or []


def is_zai_configured() -> bool:
    """Return True if an API key is set.

    Built-in models (18 GLM variants) are always available via ModelRegistry,
    so this check only verifies that authentication is in place.
    """
    return get_zai_api_key() is not None
