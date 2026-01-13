"""Configuration management and session initialization for spellbook."""

import json
import os
import random
from pathlib import Path
from typing import Any, Optional

# Mode configuration constants
VALID_MODE_TYPES = {"tarot", "fun", "none"}
VALID_TAROT_PERSONAS = {"magician", "priestess", "hermit", "fool"}


def validate_mode_config(mode: Any) -> bool:
    """Validate a mode configuration object.

    Args:
        mode: The mode configuration to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(mode, dict):
        return False

    mode_type = mode.get("type")
    if mode_type not in VALID_MODE_TYPES:
        return False

    # Tarot-specific validation
    if mode_type == "tarot":
        active_personas = mode.get("active_personas")
        if active_personas is not None:
            if not isinstance(active_personas, list):
                return False
            if len(active_personas) == 0:
                return False
            if not all(p in VALID_TAROT_PERSONAS for p in active_personas):
                return False

    return True


def get_config_path() -> Path:
    """Get path to spellbook config file."""
    return Path.home() / ".config" / "spellbook" / "spellbook.json"


def _is_spellbook_root(path: Path) -> bool:
    """Check if a directory is the spellbook root by looking for key indicators.

    Args:
        path: Directory to check

    Returns:
        True if the directory contains spellbook indicators
    """
    # Key indicators: skills/ directory and CLAUDE.spellbook.md file
    skills_dir = path / "skills"
    spellbook_md = path / "CLAUDE.spellbook.md"
    return skills_dir.is_dir() and spellbook_md.is_file()


def _find_spellbook_root_from_file() -> Optional[Path]:
    """Find spellbook root by walking up from this file's directory.

    Returns:
        Path to spellbook root if found, None otherwise
    """
    # Start from this file's directory (spellbook_mcp/)
    current = Path(__file__).resolve().parent

    # Walk up the directory tree looking for spellbook indicators
    # Limit to reasonable depth to avoid infinite loops
    for _ in range(10):
        if _is_spellbook_root(current):
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    return None


def get_spellbook_dir() -> Path:
    """Get spellbook source directory.

    Resolution order:
    1. SPELLBOOK_DIR environment variable (if set)
    2. Derive from __file__ by walking up to find spellbook root
    3. Default to ~/.local/spellbook

    Returns:
        Path to the spellbook directory
    """
    # 1. Check environment variable first
    spellbook_dir = os.environ.get("SPELLBOOK_DIR")
    if spellbook_dir:
        return Path(spellbook_dir)

    # 2. Try to find by walking up from this file
    found_root = _find_spellbook_root_from_file()
    if found_root:
        return found_root

    # 3. Default to ~/.local/spellbook
    return Path.home() / ".local" / "spellbook"


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


# Tarot mode defaults
DEFAULT_TAROT_PERSONAS = ["magician", "priestess", "hermit", "fool"]
DEFAULT_DEBATE_ROUNDS_MAX = 3


def session_init() -> dict:
    """Initialize a spellbook session.

    Reads mode preference from config. Supports both new mode object format
    and legacy fun_mode boolean for backwards compatibility.

    Returns:
        Dict with mode configuration. Format depends on mode type:
        - unset: {"mode": {"type": "unset"}}
        - none: {"mode": {"type": "none"}}
        - fun: {"mode": {"type": "fun"}, "persona": ..., "context": ..., "undertow": ...}
        - tarot: {"mode": {"type": "tarot", "active_personas": [...], "debate_rounds_max": N}}
    """
    # Check for new mode object first
    mode_config = config_get("mode")
    if mode_config is not None and isinstance(mode_config, dict):
        return _handle_mode_config(mode_config)

    # Fall back to legacy fun_mode boolean
    fun_mode_value = config_get("fun_mode")
    if fun_mode_value is not None:
        return _handle_legacy_fun_mode(fun_mode_value)

    # Neither set - return unset
    return {"mode": {"type": "unset"}}


def _handle_mode_config(mode_config: dict) -> dict:
    """Handle new mode object configuration.

    Args:
        mode_config: The mode configuration dict from config

    Returns:
        Session init response dict
    """
    mode_type = mode_config.get("type")

    if mode_type == "tarot":
        return _handle_tarot_mode(mode_config)
    elif mode_type == "fun":
        return _handle_fun_mode()
    elif mode_type == "none":
        return {"mode": {"type": "none"}}
    else:
        # Invalid or missing type - treat as unset
        return {"mode": {"type": "unset"}}


def _handle_tarot_mode(mode_config: dict) -> dict:
    """Handle tarot mode configuration.

    Args:
        mode_config: The tarot mode configuration

    Returns:
        Tarot mode response with defaults applied
    """
    active_personas = mode_config.get("active_personas", DEFAULT_TAROT_PERSONAS)
    debate_rounds_max = mode_config.get("debate_rounds_max", DEFAULT_DEBATE_ROUNDS_MAX)

    return {
        "mode": {
            "type": "tarot",
            "active_personas": active_personas,
            "debate_rounds_max": debate_rounds_max,
        }
    }


def _handle_fun_mode() -> dict:
    """Handle fun mode - select random persona/context/undertow.

    Returns:
        Fun mode response with persona/context/undertow selections
    """
    spellbook_dir = get_spellbook_dir()
    fun_assets = spellbook_dir / "skills" / "fun-mode"

    if not fun_assets.is_dir():
        return {
            "mode": {"type": "fun"},
            "error": f"fun-mode assets not found at {fun_assets}",
        }

    return {
        "mode": {"type": "fun"},
        "persona": random_line(fun_assets / "personas.txt"),
        "context": random_line(fun_assets / "contexts.txt"),
        "undertow": random_line(fun_assets / "undertows.txt"),
    }


def _handle_legacy_fun_mode(fun_mode_value: Any) -> dict:
    """Handle legacy fun_mode boolean configuration.

    Provides backwards compatibility for configs using fun_mode: true/false.

    Args:
        fun_mode_value: The legacy fun_mode value

    Returns:
        Session init response in new format
    """
    if not fun_mode_value:
        return {"mode": {"type": "none"}}

    return _handle_fun_mode()
