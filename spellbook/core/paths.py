"""Platform-aware path helpers for spellbook data, log, and config directories.

These helpers are the canonical source for spellbook's directory layout.
They live in spellbook.core so that both the spellbook package and the
installer package can import them without circular dependencies.

No external dependencies beyond the Python standard library.
"""

import os
import platform
import sys
from pathlib import Path


def _is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system().lower() == "windows"


def get_data_dir(app_name: str = "spellbook") -> Path:
    """Get OS-appropriate data directory.

    macOS:   ~/.local/{app_name}
    Linux:   ~/.local/{app_name}
    Windows: %LOCALAPPDATA%/{app_name}

    Args:
        app_name: Application name for the data subdirectory.

    Returns:
        Path to the data directory.
    """
    if _is_windows():
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / app_name
        return Path.home() / "AppData" / "Local" / app_name
    return Path.home() / ".local" / app_name


def get_log_dir(app_name: str = "spellbook") -> Path:
    """Get OS-appropriate log directory.

    macOS:   ~/.local/{app_name}/logs
    Linux:   ~/.local/{app_name}/logs
    Windows: %LOCALAPPDATA%/{app_name}/logs

    Args:
        app_name: Application name for the log subdirectory.

    Returns:
        Path to the log directory.
    """
    return get_data_dir(app_name) / "logs"


def get_config_dir(app_name: str = "spellbook") -> Path:
    """Get OS-appropriate config directory.

    macOS:   ~/.config/{app_name}
    Linux:   ~/.config/{app_name}
    Windows: %APPDATA%/{app_name}

    Args:
        app_name: Application name for the config subdirectory.

    Returns:
        Path to the config directory.
    """
    if _is_windows():
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    return Path.home() / ".config" / app_name
