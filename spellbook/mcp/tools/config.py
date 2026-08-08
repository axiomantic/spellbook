"""MCP tools for configuration management."""

__all__ = [
    "spellbook_config_get",
    "spellbook_config_set",
]

import logging
from typing import Any

from spellbook.mcp.server import mcp
from spellbook.core.config import (
    config_get,
    config_set,
)

logger = logging.getLogger(__name__)


@mcp.tool()
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
async def spellbook_config_set(key: str, value: Any) -> dict:
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
    return config_set(key, value)


