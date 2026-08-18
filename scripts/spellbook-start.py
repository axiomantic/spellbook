#!/usr/bin/env python3
"""Spellbook session initialization.

Reads config and outputs session startup data including fun-mode selections.
"""

import json
import os
import random
import sys
from pathlib import Path

ASSET_KEYS = ("persona", "context", "undertow")


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
    fun_assets = get_spellbook_dir() / "skills" / "fun-mode"
    selections = {key: random_line(fun_assets / f"{key}s.txt") for key in ASSET_KEYS}

    # An unreadable, absent, or empty asset file yields "". Emitting
    # "persona=" would announce an active fun mode while supplying nothing to
    # act on -- a failure indistinguishable from success for any consumer. Fun
    # mode without its assets is fun mode off, and it says so on stderr.
    missing = [key for key, value in selections.items() if not value]
    if missing:
        print(
            f"spellbook-start: fun mode requested but {', '.join(missing)} "
            f"unavailable under {fun_assets}; reporting fun mode off",
            file=sys.stderr,
        )
        print("fun_mode=no")
        return

    print("fun_mode=yes")
    for key in ASSET_KEYS:
        print(f"{key}={selections[key]}")


if __name__ == "__main__":
    main()
