"""Configuration management for PR distillation.

Handles per-project configuration for pattern blessing, thresholds, and
always-review paths. Config is stored in ~/.local/spellbook/docs/{project-encoded}/pr-distill-config.json.

Ported from lib/pr-distill/config.js.
"""

import json
import os
from pathlib import Path
from typing import TypedDict


class QueryCountThresholds(TypedDict):
    """Thresholds for query count change detection."""
    relative_percent: int
    absolute_delta: int


class PRDistillConfig(TypedDict):
    """Configuration for PR distillation."""
    blessed_patterns: list[str]
    always_review_paths: list[str]
    query_count_thresholds: QueryCountThresholds


# Base directory for PR distillation config
# Config is stored per-project: ~/.local/spellbook/docs/<project-encoded>/pr-distill-config.json
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".local", "spellbook", "docs")

# Default configuration values
DEFAULT_CONFIG: PRDistillConfig = {
    "blessed_patterns": [],
    "always_review_paths": [],
    "query_count_thresholds": {
        "relative_percent": 20,
        "absolute_delta": 10,
    },
}


def encode_project_path(project_root: str) -> str:
    """Encode a project root path for use in filesystem.

    Removes leading slash and replaces remaining slashes with dashes.

    Args:
        project_root: Absolute path to project root

    Returns:
        Encoded path suitable for directory name
    """
    # Remove leading slash and replace remaining slashes with dashes
    return project_root.lstrip("/").replace("/", "-")


def get_config_path(project_root: str) -> str:
    """Get the config file path for a project.

    Args:
        project_root: Absolute path to project root

    Returns:
        Absolute path to config file
    """
    encoded = encode_project_path(project_root)
    return os.path.join(CONFIG_DIR, encoded, "pr-distill-config.json")


def load_config(project_root: str) -> PRDistillConfig:
    """Load configuration for a project.

    Returns default config if file does not exist or is invalid.
    Merges with defaults for any missing keys.

    Args:
        project_root: Absolute path to project root

    Returns:
        Configuration dictionary
    """
    config_path = get_config_path(project_root)

    if not os.path.exists(config_path):
        # Return a deep copy of defaults to avoid mutation issues
        return {
            "blessed_patterns": list(DEFAULT_CONFIG["blessed_patterns"]),
            "always_review_paths": list(DEFAULT_CONFIG["always_review_paths"]),
            "query_count_thresholds": dict(DEFAULT_CONFIG["query_count_thresholds"]),
        }

    try:
        with open(config_path, "r") as f:
            loaded = json.load(f)

        # Merge with defaults for any missing keys
        return {
            "blessed_patterns": loaded.get("blessed_patterns", DEFAULT_CONFIG["blessed_patterns"]),
            "always_review_paths": loaded.get("always_review_paths", DEFAULT_CONFIG["always_review_paths"]),
            "query_count_thresholds": loaded.get("query_count_thresholds", DEFAULT_CONFIG["query_count_thresholds"]),
        }
    except (json.JSONDecodeError, OSError):
        # Parse error or read error, return deep copy of defaults
        return {
            "blessed_patterns": list(DEFAULT_CONFIG["blessed_patterns"]),
            "always_review_paths": list(DEFAULT_CONFIG["always_review_paths"]),
            "query_count_thresholds": dict(DEFAULT_CONFIG["query_count_thresholds"]),
        }


def save_config(project_root: str, config: PRDistillConfig) -> None:
    """Save configuration for a project.

    Creates directories if they don't exist.

    Args:
        project_root: Absolute path to project root
        config: Configuration to save
    """
    config_path = get_config_path(project_root)
    config_dir = os.path.dirname(config_path)

    # Create directory structure
    os.makedirs(config_dir, exist_ok=True)

    # Write config with pretty-printing
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def bless_pattern(project_root: str, pattern_id: str) -> PRDistillConfig:
    """Add a pattern to the blessed_patterns list.

    Does not duplicate existing patterns.

    Args:
        project_root: Absolute path to project root
        pattern_id: Pattern ID to bless

    Returns:
        Updated configuration dictionary
    """
    # Load existing config (or defaults)
    config = load_config(project_root)

    # Add pattern if not already present
    if pattern_id not in config["blessed_patterns"]:
        config["blessed_patterns"].append(pattern_id)

    # Save updated config
    save_config(project_root, config)

    return config
