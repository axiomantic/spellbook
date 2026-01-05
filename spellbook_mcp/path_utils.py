"""Path encoding and project directory resolution for session storage."""

import os
from pathlib import Path


def encode_cwd(cwd: str) -> str:
    """
    Encode current working directory for session storage path.

    Args:
        cwd: Absolute path to working directory

    Returns:
        Encoded path with slashes replaced by dashes, leading dash stripped

    Examples:
        >>> encode_cwd('/Users/alice/Development/spellbook')
        'Users-alice-Development-spellbook'
    """
    return cwd.replace('/', '-').lstrip('-')


def get_spellbook_config_dir() -> Path:
    """
    Get the spellbook configuration directory.

    Resolution order:
    1. SPELLBOOK_CONFIG_DIR environment variable
    2. CLAUDE_CONFIG_DIR environment variable (backward compatibility)
    3. ~/.local/spellbook (portable default)

    Returns:
        Path to spellbook config directory
    """
    # Check SPELLBOOK_CONFIG_DIR first (preferred)
    config_dir = os.environ.get('SPELLBOOK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir)

    # Fall back to CLAUDE_CONFIG_DIR for backward compatibility
    claude_config = os.environ.get('CLAUDE_CONFIG_DIR')
    if claude_config:
        return Path(claude_config)

    # Default to portable location
    return Path.home() / '.local' / 'spellbook'


def get_project_dir() -> Path:
    """
    Get session storage directory for current project.

    Auto-detects project directory based on current working directory
    and encodes it for storage under the spellbook config directory.

    Resolution order for base directory:
    1. $SPELLBOOK_CONFIG_DIR/projects/
    2. $CLAUDE_CONFIG_DIR/projects/ (backward compatibility)
    3. ~/.local/spellbook/projects/ (portable default)

    Returns:
        Path to project's session directory
    """
    cwd = os.getcwd()
    encoded = encode_cwd(cwd)

    return get_spellbook_config_dir() / 'projects' / encoded
