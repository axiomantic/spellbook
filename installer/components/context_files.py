"""
Context file generation for spellbook installation.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

# Add parent directories to path for imports
_installer_dir = Path(__file__).parent.parent
_spellbook_dir = _installer_dir.parent

if str(_spellbook_dir) not in sys.path:
    sys.path.insert(0, str(_spellbook_dir))


def get_spellbook_config_dir() -> Path:
    """Get the spellbook config directory (for outputs).

    Note: CLAUDE_CONFIG_DIR is intentionally NOT consulted here.
    That variable controls where Claude Code installs its own artifacts,
    not where spellbook stores work files.
    """
    config_dir = os.environ.get('SPELLBOOK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir)
    return Path.home() / '.local' / 'spellbook'


def generate_spellbook_config_section(spellbook_dir: Path) -> str:
    """
    Generate the Spellbook Configuration section with path definitions.

    This section defines variables that are referenced in symlinked skill/command files.
    The AI should substitute these values when interpreting paths.
    """
    config_dir = get_spellbook_config_dir()

    lines = [
        "## Spellbook Configuration",
        "",
        "The following variables are defined for this spellbook installation.",
        "When reading spellbook skills, commands, and documentation, **substitute these values**",
        "for any `$VARIABLE` or `${VARIABLE}` references:",
        "",
        "```",
        f"SPELLBOOK_DIR={spellbook_dir}",
        f"SPELLBOOK_CONFIG_DIR={config_dir}",
        "```",
        "",
        "**CRITICAL:** Treat these as environment variables when interpreting paths in spellbook files.",
        "For example, `$SPELLBOOK_DIR/tests/example.py` means `" + str(spellbook_dir) + "/tests/example.py`.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def get_spellbook_context_content(spellbook_dir: Path) -> str:
    """
    Get the content of AGENTS.spellbook.md from the spellbook repository.

    This is the installable template content that will be placed in the
    demarcated section of user config files. Separate from any project-specific
    AGENTS.md that may exist for spellbook development.
    """
    agents_md = spellbook_dir / "AGENTS.spellbook.md"
    if not agents_md.exists():
        return ""
    return agents_md.read_text(encoding="utf-8").strip()


# Backward-compatible alias
get_spellbook_claude_md_content = get_spellbook_context_content


def generate_codex_context(spellbook_dir: Path, include_claude_md: bool = True) -> str:
    """
    Generate context content for Codex/OpenCode (AGENTS.md).

    Args:
        spellbook_dir: Path to spellbook directory
        include_claude_md: Whether to include AGENTS.spellbook.md content

    Returns complete context content for AGENTS.md demarcated section.
    """
    parts = []

    # Add configuration section first
    parts.append(generate_spellbook_config_section(spellbook_dir))

    if include_claude_md:
        claude_content = get_spellbook_context_content(spellbook_dir)
        if claude_content:
            parts.append(claude_content)

    # Note: Skills are discovered via MCP server. No static skill registry needed here.

    return "\n".join(parts)


def generate_claude_context(spellbook_dir: Path) -> str:
    """
    Generate context content for Claude Code (CLAUDE.md).

    Includes:
    1. Spellbook configuration (SPELLBOOK_DIR, SPELLBOOK_CONFIG_DIR)
    2. The raw AGENTS.spellbook.md content

    Claude Code handles skills differently (via Skill tool).
    """
    parts = []

    # Add configuration section first
    parts.append(generate_spellbook_config_section(spellbook_dir))

    # Add AGENTS.spellbook.md content
    claude_content = get_spellbook_context_content(spellbook_dir)
    if claude_content:
        parts.append(claude_content)

    return "\n".join(parts)
