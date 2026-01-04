"""
Context file generation for spellbook installation.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add parent directories to path for imports
_installer_dir = Path(__file__).parent.parent
_spellbook_dir = _installer_dir.parent

if str(_spellbook_dir) not in sys.path:
    sys.path.insert(0, str(_spellbook_dir))


def get_spellbook_claude_md_content(spellbook_dir: Path) -> str:
    """
    Get the content of CLAUDE.md from the spellbook repository.

    This is the content that will be placed in the demarcated section.
    """
    claude_md = spellbook_dir / "CLAUDE.md"
    if not claude_md.exists():
        return ""
    return claude_md.read_text(encoding="utf-8").strip()


def generate_gemini_context(spellbook_dir: Path, include_claude_md: bool = True) -> str:
    """
    Generate context content for Gemini CLI.

    Args:
        spellbook_dir: Path to spellbook directory
        include_claude_md: Whether to include CLAUDE.md content

    Returns the complete context content for GEMINI.md demarcated section.
    """
    parts = []

    if include_claude_md:
        claude_content = get_spellbook_claude_md_content(spellbook_dir)
        if claude_content:
            parts.append(claude_content)

    # Add MCP-based skill discovery instructions (no static list)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("# Spellbook Skills")
    parts.append("")
    parts.append("**CRITICAL:** Spellbook skills are MANDATORY workflows that MUST be invoked")
    parts.append("when their trigger conditions are met. Skills enforce quality gates and")
    parts.append("prevent shortcuts that lead to bugs and technical debt.")
    parts.append("")
    parts.append("## BINDING Priority Order")
    parts.append("")
    parts.append("Skills are resolved in this BINDING priority order (first match wins):")
    parts.append("")
    parts.append("1. **Personal skills** (~/.config/opencode/skills/, ~/.codex/skills/)")
    parts.append("2. **Spellbook skills** (shared repository skills)")
    parts.append("3. **Claude skills** ($CLAUDE_CONFIG_DIR/skills/)")
    parts.append("")
    parts.append("Personal customizations ALWAYS override shared skills. This is non-negotiable.")
    parts.append("")
    parts.append("## Discovering Skills")
    parts.append("")
    parts.append("List all available skills with their trigger conditions:")
    parts.append("```")
    parts.append("spellbook.find_spellbook_skills()")
    parts.append("```")
    parts.append("")
    parts.append("Each skill's description specifies WHEN to use it (e.g., 'Use when")
    parts.append("implementing features', 'Use when debugging'). When these conditions")
    parts.append("are met, you MUST invoke the skill before proceeding.")
    parts.append("")
    parts.append("## Using Skills")
    parts.append("")
    parts.append("Load and follow a skill's complete workflow:")
    parts.append("```")
    parts.append('spellbook.use_spellbook_skill(skill_name="<skill-name>")')
    parts.append("```")
    parts.append("")
    parts.append("Skills are always up-to-date via runtime discovery.")

    return "\n".join(parts)


def generate_codex_context(spellbook_dir: Path, include_claude_md: bool = True) -> str:
    """
    Generate context content for Codex (AGENTS.md).

    Args:
        spellbook_dir: Path to spellbook directory
        include_claude_md: Whether to include CLAUDE.md content

    Returns the complete context content for AGENTS.md demarcated section.
    """
    parts = []

    if include_claude_md:
        claude_content = get_spellbook_claude_md_content(spellbook_dir)
        if claude_content:
            parts.append(claude_content)

    # Add MCP-based skill discovery instructions (no static list)
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("# Spellbook Skills")
    parts.append("")
    parts.append("**CRITICAL:** Spellbook skills are MANDATORY workflows that MUST be invoked")
    parts.append("when their trigger conditions are met. Skills enforce quality gates and")
    parts.append("prevent shortcuts that lead to bugs and technical debt.")
    parts.append("")
    parts.append("## BINDING Priority Order")
    parts.append("")
    parts.append("Skills are resolved in this BINDING priority order (first match wins):")
    parts.append("")
    parts.append("1. **Personal skills** (~/.config/opencode/skills/, ~/.codex/skills/)")
    parts.append("2. **Spellbook skills** (shared repository skills)")
    parts.append("3. **Claude skills** ($CLAUDE_CONFIG_DIR/skills/)")
    parts.append("")
    parts.append("Personal customizations ALWAYS override shared skills. This is non-negotiable.")
    parts.append("")
    parts.append("## Discovering Skills")
    parts.append("")
    parts.append("List all available skills with their trigger conditions:")
    parts.append("```")
    parts.append("spellbook.find_spellbook_skills()")
    parts.append("```")
    parts.append("")
    parts.append("Each skill's description specifies WHEN to use it (e.g., 'Use when")
    parts.append("implementing features', 'Use when debugging'). When these conditions")
    parts.append("are met, you MUST invoke the skill before proceeding.")
    parts.append("")
    parts.append("## Using Skills")
    parts.append("")
    parts.append("Load and follow a skill's complete workflow:")
    parts.append("```")
    parts.append('spellbook.use_spellbook_skill(skill_name="<skill-name>")')
    parts.append("```")
    parts.append("")
    parts.append("Skills are always up-to-date via runtime discovery.")

    return "\n".join(parts)


def generate_claude_context(spellbook_dir: Path) -> str:
    """
    Generate context content for Claude Code (CLAUDE.md).

    This is just the raw CLAUDE.md content since Claude Code
    handles skills differently (via Skill tool).
    """
    return get_spellbook_claude_md_content(spellbook_dir)
