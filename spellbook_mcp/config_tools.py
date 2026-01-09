"""Configuration management and session initialization for spellbook."""

import json
import os
import random
from pathlib import Path
from typing import Any, Optional


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
    spellbook_dir = get_spellbook_dir()
    fun_assets = spellbook_dir / "skills" / "fun-mode"

    # Verify the assets directory exists
    if not fun_assets.is_dir():
        return {
            "fun_mode": "yes",
            "error": f"fun-mode assets not found at {fun_assets}",
        }

    return {
        "fun_mode": "yes",
        "persona": random_line(fun_assets / "personas.txt"),
        "context": random_line(fun_assets / "contexts.txt"),
        "undertow": random_line(fun_assets / "undertows.txt"),
    }
