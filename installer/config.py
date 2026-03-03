"""
Configuration constants and platform settings for spellbook installer.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Spellbook's own config directory (platform-agnostic)
# This is where spellbook stores its outputs: projects, logs, distilled sessions, etc.
SPELLBOOK_CONFIG_DIR_ENV = "SPELLBOOK_CONFIG_DIR"
SPELLBOOK_DEFAULT_CONFIG_DIR = Path.home() / ".local" / "spellbook"


def get_spellbook_config_dir() -> Path:
    """
    Get the spellbook configuration directory.

    Resolution order:
    1. SPELLBOOK_CONFIG_DIR environment variable
    2. ~/.local/spellbook (portable default)

    Note: CLAUDE_CONFIG_DIR is intentionally NOT used here. That variable
    controls where Claude Code's own config lives (skills, commands, etc.),
    which is a separate concern from where spellbook stores its work files.
    """
    config_dir = os.environ.get('SPELLBOOK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir)

    return SPELLBOOK_DEFAULT_CONFIG_DIR


# Supported platforms (AI coding assistants that can consume spellbook)
SUPPORTED_PLATFORMS = ["claude_code", "opencode", "codex", "gemini", "crush"]

# Platform configuration
# NOTE: These are the AI assistant platforms that consume spellbook.
# Spellbook's own config (SPELLBOOK_CONFIG_DIR) is separate from these.
PLATFORM_CONFIG: Dict[str, Dict[str, Any]] = {
    "claude_code": {
        "name": "Claude Code",
        "config_dir_env": "CLAUDE_CONFIG_DIR",
        "default_config_dir": Path.home() / ".claude",
        "cli_flag_name": "claude-config-dir",
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
        "config_dir_env": "OPENCODE_CONFIG_DIR",
        "default_config_dir": Path.home() / ".config" / "opencode",
        "cli_flag_name": "opencode-config-dir",
        "context_file": "AGENTS.md",
        # Note: OpenCode reads skills from ~/.claude/skills/* natively
        "mcp_supported": True,
        "mcp_server_name": "spellbook",
    },
    "codex": {
        "name": "Codex",
        "config_dir_env": "CODEX_CONFIG_DIR",
        "default_config_dir": Path.home() / ".codex",
        "cli_flag_name": "codex-config-dir",
        "context_file": "AGENTS.md",
        "spellbook_symlink": "spellbook",  # Symlink to spellbook root
        "mcp_server_name": "spellbook",
        "mcp_supported": True,
    },
    "gemini": {
        "name": "Gemini CLI",
        "config_dir_env": "GEMINI_CONFIG_DIR",
        "default_config_dir": Path.home() / ".gemini",
        "cli_flag_name": "gemini-config-dir",
        # Context provided via native extension system (gemini extensions link)
        # Extension at ~/.gemini/extensions/spellbook/ -> <repo>/extensions/gemini/
        "context_file": None,
        "mcp_supported": True,  # Via extension
    },
    "crush": {
        "name": "Crush",
        "config_dir_env": "CRUSH_GLOBAL_CONFIG",
        "default_config_dir": Path.home() / ".local" / "share" / "crush",
        "cli_flag_name": "crush-config-dir",
        "context_file": "AGENTS.md",
        # Note: Crush reads skills from options.skills_paths in crush.json
        # We configure it to include ~/.claude/skills/ for shared skills
        "mcp_supported": True,
        "mcp_server_name": "spellbook",
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


def resolve_config_dirs(
    platform: str,
    cli_dirs: Optional[List[Path]] = None,
    env_override: Optional[str] = None,
) -> List[Path]:
    """Resolve the list of config directories for a platform.

    Resolution order:
    1. CLI flags (--<platform>-config-dir), if any provided
    2. Environment variable (single dir), if set
    3. Platform default

    CLI flags REPLACE (not supplement) env var and defaults.
    Env var REPLACES (not supplements) default.

    Post-processing:
    - Resolve all paths to absolute
    - Deduplicate (preserve order, remove later duplicates)
    - For default dirs: create if missing (preserve current behavior)
    - For explicitly-passed dirs (CLI or env): skip with warning if non-existent

    Args:
        platform: Platform identifier (e.g., "claude_code")
        cli_dirs: Directories passed via CLI flags (repeatable)
        env_override: Optional env var override (for testing; normally read
            from os.environ)

    Returns:
        List of zero or more resolved config dirs.
    """
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        raise ValueError(f"Unknown platform: {platform}")

    raw_dirs: List[Path] = []
    is_explicit = False  # True if dirs came from CLI or env (not default)

    if cli_dirs:
        # CLI flags override everything
        raw_dirs = [Path(d) if not isinstance(d, Path) else d for d in cli_dirs]
        is_explicit = True
    else:
        # Check env var
        env_var_name = config.get("config_dir_env")
        env_value = env_override
        if env_value is None and env_var_name:
            env_value = os.environ.get(env_var_name)

        if env_value:
            raw_dirs = [Path(env_value)]
            is_explicit = True
        else:
            # Fall back to default
            raw_dirs = [config["default_config_dir"]]
            is_explicit = False

    # Resolve to absolute paths and deduplicate
    seen: set = set()
    result: List[Path] = []

    for d in raw_dirs:
        abs_path = d.resolve()
        if abs_path in seen:
            continue
        seen.add(abs_path)

        if is_explicit:
            # Explicit dirs (CLI or env): must exist, skip with warning if not
            if not abs_path.exists():
                logger.warning(
                    "Config directory does not exist, skipping: %s", abs_path
                )
                continue
            result.append(abs_path)
        else:
            # Default dir: create if missing (preserve existing behavior)
            abs_path.mkdir(parents=True, exist_ok=True)
            result.append(abs_path)

    return result


def get_context_file_path(platform: str) -> Optional[Path]:
    """Get the path to the context file for a platform."""
    config = PLATFORM_CONFIG.get(platform)
    if not config:
        raise ValueError(f"Unknown platform: {platform}")

    context_file = config.get("context_file")
    if not context_file:
        return None

    config_dir = get_platform_config_dir(platform)

    # Context files go at the root of the config directory
    # (Gemini's extension manifest is separate from GEMINI.md global context)
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
