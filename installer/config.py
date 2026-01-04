"""
Configuration constants and platform settings for spellbook installer.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Supported platforms
SUPPORTED_PLATFORMS = ["claude_code", "opencode", "codex", "gemini"]

# Platform configuration
PLATFORM_CONFIG: Dict[str, Dict[str, Any]] = {
    "claude_code": {
        "name": "Claude Code",
        "config_dir_env": "CLAUDE_CONFIG_DIR",
        "default_config_dir": Path.home() / ".claude",
        "context_file": "CLAUDE.md",
        "skills_subdir": "skills",
        "commands_subdir": "commands",
        "scripts_subdir": "scripts",
        "agents_subdir": "agents",
        "patterns_subdir": "patterns",
        "docs_subdir": "docs",
        "plans_subdir": "plans",
        "mcp_supported": True,
        "mcp_server_name": "spellbook",
    },
    "opencode": {
        "name": "OpenCode",
        "config_dir_env": None,
        "default_config_dir": Path.home() / ".opencode",
        "context_file": None,  # Uses CLAUDE.md via symlink resolution
        "skills_subdir": "skills",
        "skill_format": "flat_md",  # Skills as individual .md files
        "mcp_supported": False,
    },
    "codex": {
        "name": "Codex",
        "config_dir_env": None,
        "default_config_dir": Path.home() / ".codex",
        "context_file": "AGENTS.md",
        "spellbook_symlink": "spellbook",  # Symlink to spellbook root
        "cli_script": ".codex/spellbook-codex",
        "mcp_supported": False,
    },
    "gemini": {
        "name": "Gemini CLI",
        "config_dir_env": None,
        "default_config_dir": Path.home() / ".gemini",
        "context_file": "GEMINI.md",
        "extensions_subdir": "extensions/spellbook",
        "extension_manifest": "gemini-extension.json",
        "mcp_supported": True,  # Via extension manifest
    },
}


def get_platform_config_dir(platform: str) -> Path:
    """Get the configuration directory for a platform."""
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        raise ValueError(f"Unknown platform: {platform}")

    env_var = config.get("config_dir_env")
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return Path(env_value)

    return config["default_config_dir"]


def get_context_file_path(platform: str) -> Optional[Path]:
    """Get the path to the context file for a platform."""
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        raise ValueError(f"Unknown platform: {platform}")

    context_file = config.get("context_file")
    if not context_file:
        return None

    config_dir = get_platform_config_dir(platform)

    # Special handling for platforms with subdirectories
    if platform == "gemini":
        extensions_subdir = config.get("extensions_subdir", "")
        return config_dir / extensions_subdir / context_file

    return config_dir / context_file


def platform_exists(platform: str) -> bool:
    """Check if a platform's config directory exists."""
    config_dir = get_platform_config_dir(platform)
    return config_dir.exists()


def detect_available_platforms() -> List[str]:
    """Detect which platforms have config directories."""
    available = []
    for platform in SUPPORTED_PLATFORMS:
        # Claude Code is always available (we create its directory)
        if platform == "claude_code":
            available.append(platform)
        elif platform_exists(platform):
            available.append(platform)
    return available


# Backup file suffix pattern
BACKUP_SUFFIX_PATTERN = ".backup.{timestamp}"

# Version file name
VERSION_FILE = ".version"
