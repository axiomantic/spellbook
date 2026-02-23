#!/usr/bin/env python3
"""Spellbook session initialization.

Reads config and outputs session startup data including fun-mode selections.
"""

import json
import os
import random
import sys
from pathlib import Path


def get_config_path() -> Path:
    """Get path to spellbook config file."""
    return Path.home() / ".config" / "spellbook" / "spellbook.json"


def get_spellbook_dir() -> Path:
    """Get spellbook source directory from environment."""
    spellbook_dir = os.environ.get("SPELLBOOK_DIR")
    if spellbook_dir:
        return Path(spellbook_dir)
    # Fallback: assume script is in spellbook/scripts/
    return Path(__file__).parent.parent


def read_config() -> dict:
    """Read spellbook config, returning empty dict if missing."""
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def random_line(file_path: Path) -> str:
    """Select a random line from a file."""
    try:
        lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return random.choice(lines) if lines else ""
    except OSError:
        return ""


def main():
    config = read_config()
    fun_mode = config.get("fun_mode")

    if fun_mode is None:
        print("fun_mode=unset")
        return

    if not fun_mode:
        print("fun_mode=no")
        return

    # Fun mode enabled - select random persona/context/undertow
    spellbook_dir = get_spellbook_dir()
    fun_assets = spellbook_dir / "skills" / "fun-mode"

    print("fun_mode=yes")
    print(f"persona={random_line(fun_assets / 'personas.txt')}")
    print(f"context={random_line(fun_assets / 'contexts.txt')}")
    print(f"undertow={random_line(fun_assets / 'undertows.txt')}")


if __name__ == "__main__":
    main()
