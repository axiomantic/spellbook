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


def get_project_dir() -> Path:
    """
    Get session storage directory for current project.

    Auto-detects project directory based on current working directory
    and encodes it for storage under ~/.claude/projects/ (or
    $CLAUDE_CONFIG_DIR/projects/ if environment variable is set).

    Returns:
        Path to project's session directory
    """
    cwd = os.getcwd()
    encoded = encode_cwd(cwd)

    # Support CLAUDE_CONFIG_DIR environment variable
    config_dir = os.environ.get('CLAUDE_CONFIG_DIR')
    if config_dir:
        base_dir = Path(config_dir)
    else:
        base_dir = Path.home() / '.claude'

    return base_dir / 'projects' / encoded
