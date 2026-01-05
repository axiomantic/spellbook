"""User preferences management."""

import os
from pathlib import Path
from typing import Any
from .command_utils import atomic_write_json, read_json_safe

def get_preferences_path() -> Path:
    """Get path to preferences file."""
    config_dir = Path.home() / ".config" / "spellbook"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "preferences.json"

def load_preferences() -> dict:
    """Load user preferences."""
    prefs_path = get_preferences_path()

    if not prefs_path.exists():
        return {
            "terminal": {
                "program": None,
                "detected": False
            },
            "execution_mode": {
                "default": None,
                "always_ask": True
            }
        }

    return read_json_safe(str(prefs_path))

def save_preference(key: str, value: Any):
    """
    Save a preference value.

    Args:
        key: Dot-separated key path (e.g., "terminal.program")
        value: Value to save
    """
    prefs = load_preferences()

    keys = key.split('.')
    current = prefs
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    current[keys[-1]] = value

    prefs_path = get_preferences_path()
    atomic_write_json(str(prefs_path), prefs)
