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


def generate_skill_registry(spellbook_dir: Path) -> str:
    """
    Generate a skill registry section listing all available skills.

    This can be appended to context files to help AI assistants
    discover and use skills.
    """
    try:
        from spellbook_mcp.skill_ops import find_skills
    except ImportError:
        # Fallback if spellbook_mcp not available
        return _generate_skill_registry_fallback(spellbook_dir)

    # Get skill directories
    skill_dirs = [spellbook_dir / "skills"]

    # Also check for claude config skills
    claude_config = Path.home() / ".claude"
    claude_skills = claude_config / "skills"
    if claude_skills.exists():
        skill_dirs.append(claude_skills)

    skills = find_skills(skill_dirs)
    skills.sort(key=lambda x: x["name"])

    lines = ["## Available Skills", ""]
    for skill in skills:
        name = skill["name"]
        desc = skill.get("description", "No description provided.")
        # Clean description newlines
        desc = desc.replace("\n", " ").strip()
        lines.append(f"- **{name}**: {desc}")

    return "\n".join(lines)


def _generate_skill_registry_fallback(spellbook_dir: Path) -> str:
    """Fallback skill registry generation without spellbook_mcp."""
    skills_dir = spellbook_dir / "skills"
    if not skills_dir.exists():
        return ""

    lines = ["## Available Skills", ""]

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        name = skill_dir.name
        desc = _extract_description(skill_md)
        lines.append(f"- **{name}**: {desc}")

    return "\n".join(lines)


def _extract_description(skill_md: Path) -> str:
    """Extract description from SKILL.md frontmatter."""
    try:
        content = skill_md.read_text(encoding="utf-8")

        # Look for YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                frontmatter = content[3:end]
                for line in frontmatter.split("\n"):
                    if line.startswith("description:"):
                        desc = line[12:].strip()
                        # Handle multi-line with >
                        if desc.startswith(">"):
                            desc = desc[1:].strip()
                        return desc.replace("\n", " ")

        return "No description provided."
    except OSError:
        return "No description provided."


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

    skill_registry = generate_skill_registry(spellbook_dir)
    if skill_registry:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("# Spellbook Skill Registry")
        parts.append("")
        parts.append(skill_registry)
        parts.append("")
        parts.append("## Usage")
        parts.append("")
        parts.append("To use a skill, invoke it via the spellbook MCP server:")
        parts.append("```")
        parts.append('spellbook.use_spellbook_skill(skill_name="<skill-name>")')
        parts.append("```")

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

    skill_registry = generate_skill_registry(spellbook_dir)
    if skill_registry:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("# Spellbook Skill Registry")
        parts.append("")
        parts.append(skill_registry)
        parts.append("")
        parts.append("## Usage")
        parts.append("")
        parts.append("To use a skill in Codex, run:")
        parts.append("```")
        parts.append(".codex/spellbook-codex use-skill <skill-name>")
        parts.append("```")

    return "\n".join(parts)


def generate_claude_context(spellbook_dir: Path) -> str:
    """
    Generate context content for Claude Code (CLAUDE.md).

    This is just the raw CLAUDE.md content since Claude Code
    handles skills differently (via Skill tool).
    """
    return get_spellbook_claude_md_content(spellbook_dir)
