"""Configuration management and session initialization for spellbook."""

import json
import os
import random
from pathlib import Path
from typing import Any, Optional


def get_config_path() -> Path:
    """Get path to spellbook config file."""
    return Path.home() / ".config" / "spellbook" / "spellbook.json"


def get_spellbook_dir() -> Path:
    """Get spellbook source directory from environment.

    Returns SPELLBOOK_DIR environment variable if set, otherwise
    raises ValueError since we need it to find skill assets.
    """
    spellbook_dir = os.environ.get("SPELLBOOK_DIR")
    if spellbook_dir:
        return Path(spellbook_dir)
    raise ValueError("SPELLBOOK_DIR environment variable not set")


def config_get(key: str) -> Optional[Any]:
    """Read a config value from spellbook.json.

    Args:
        key: The config key to read

    Returns:
        The value for the key, or None if not set or file missing
    """
    config_path = get_config_path()
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text())
        return config.get(key)
    except (json.JSONDecodeError, OSError):
        return None


def config_set(key: str, value: Any) -> dict:
    """Write a config value to spellbook.json.

    Creates the config file and parent directories if they don't exist.
    Preserves other config values (read-modify-write).

    Args:
        key: The config key to set
        value: The value to set (must be JSON-serializable)

    Returns:
        Dict with status and the updated config
    """
    config_path = get_config_path()

    # Read existing config or start fresh
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}

    # Update the value
    config[key] = value

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write back
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    return {"status": "ok", "config": config}


def random_line(file_path: Path) -> str:
    """Select a random non-empty line from a file.

    Args:
        file_path: Path to the file to read

    Returns:
        A random line from the file, or empty string if file missing/empty
    """
    try:
        lines = [line.strip() for line in file_path.read_text().splitlines() if line.strip()]
        return random.choice(lines) if lines else ""
    except OSError:
        return ""


def session_init() -> dict:
    """Initialize a spellbook session.

    Reads fun_mode preference from config and selects random
    persona/context/undertow if fun mode is enabled.

    Returns:
        Dict with:
        - fun_mode: "yes" | "no" | "unset"
        - persona: str (only if fun_mode=yes)
        - context: str (only if fun_mode=yes)
        - undertow: str (only if fun_mode=yes)
    """
    fun_mode_value = config_get("fun_mode")

    # Determine fun_mode status
    if fun_mode_value is None:
        return {"fun_mode": "unset"}

    if not fun_mode_value:
        return {"fun_mode": "no"}

    # Fun mode enabled - select random persona/context/undertow
    try:
        spellbook_dir = get_spellbook_dir()
    except ValueError:
        # SPELLBOOK_DIR not set, can't find assets
        return {
            "fun_mode": "yes",
            "error": "SPELLBOOK_DIR not set, cannot load fun-mode assets"
        }

    fun_assets = spellbook_dir / "skills" / "fun-mode"

    return {
        "fun_mode": "yes",
        "persona": random_line(fun_assets / "personas.txt"),
        "context": random_line(fun_assets / "contexts.txt"),
        "undertow": random_line(fun_assets / "undertows.txt"),
    }
