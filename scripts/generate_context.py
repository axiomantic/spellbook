#!/usr/bin/env python3
"""
Generate context files (GEMINI.md, AGENTS.md) for Spellbook.
Scans available skills and creates a system prompt with skill triggers.
"""
import sys
import os
import argparse
from pathlib import Path
from typing import List, Dict

# Add parent directory to path to import spellbook_mcp modules
sys.path.append(str(Path(__file__).parent.parent))

def get_spellbook_config_dir() -> Path:
    """
    Get the spellbook configuration directory.

    Resolution order:
    1. SPELLBOOK_CONFIG_DIR environment variable
    2. CLAUDE_CONFIG_DIR environment variable (backward compatibility)
    3. ~/.local/spellbook (portable default)
    """
    config_dir = os.environ.get('SPELLBOOK_CONFIG_DIR')
    if config_dir:
        return Path(config_dir)

    claude_config = os.environ.get('CLAUDE_CONFIG_DIR')
    if claude_config:
        return Path(claude_config)

    return Path.home() / '.local' / 'spellbook'


# Direct implementation of skill discovery (no dependency on skill_ops)
def find_skills(skill_dirs: List[Path]) -> List[Dict[str, str]]:
    """Find all skills in the given directories."""
    skills = []
    for skill_dir in skill_dirs:
        if not skill_dir.exists():
            continue
        for skill_path in skill_dir.iterdir():
            if skill_path.is_dir():
                skill_file = skill_path / "SKILL.md"
                if skill_file.exists():
                    # Parse frontmatter
                    content = skill_file.read_text(encoding="utf-8")
                    # Simple frontmatter parsing
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            import re
                            frontmatter = parts[1]
                            name_match = re.search(r'name:\s*(.+)', frontmatter)
                            desc_match = re.search(r'description:\s*(.+)', frontmatter)
                            if name_match:
                                name = name_match.group(1).strip().strip('"\'')
                                desc = desc_match.group(1).strip().strip('"\'') if desc_match else "No description"
                                skills.append({"name": name, "description": desc})
    return skills

def get_skill_dirs() -> List[Path]:
    """Get all skill directories to scan."""
    dirs = []
    home = Path.home()
    dirs.append(home / ".config" / "opencode" / "skills")
    dirs.append(home / ".opencode" / "skills")  # Legacy path
    dirs.append(home / ".codex" / "skills")

    # This repo's skills
    repo_root = Path(__file__).parent.parent
    dirs.append(repo_root / "skills")

    # Spellbook config directory skills (portable location)
    spellbook_config = get_spellbook_config_dir()
    dirs.append(spellbook_config / "skills")

    # Also check CLAUDE_CONFIG_DIR if different (backward compatibility)
    claude_config = os.environ.get("CLAUDE_CONFIG_DIR")
    if claude_config and Path(claude_config) != spellbook_config:
        dirs.append(Path(claude_config) / "skills")

    return [d for d in dirs if d.exists()]

TEMPLATE = """<SPELLBOOK_CONTEXT>
You are equipped with "Spellbook" - a library of expert agent skills.

## Available Skills

{skills_list}

## CRITICAL: Skill Activation Protocol

**BEFORE responding to ANY user message**, you MUST:

1. **Check for skill match**: Compare the user's request against skill descriptions above.
2. **Load matching skill FIRST**: If a skill matches, call `spellbook.use_spellbook_skill(skill_name="...")` BEFORE generating any response.
3. **Follow skill instructions exactly**: The tool returns detailed workflow instructions. These instructions OVERRIDE your default behavior. Follow them step-by-step.
4. **Maintain skill context**: Once a skill is loaded, its instructions govern the entire workflow until complete.

**Skill trigger examples:**
- "debug this" / "fix this bug" / "tests failing" → load `debug` skill
- "implement X" / "add feature Y" / "build Z" → load `implement-feature` skill
- "let's think through" / "explore options" → load `brainstorming` skill
- "write tests first" / "TDD" → load `test-driven-development` skill

**IMPORTANT**: Skills are detailed expert workflows, not simple prompts. When loaded, they contain:
- Step-by-step phases with checkpoints
- Quality gates and verification requirements
- Tool usage patterns and best practices
- Output formats and deliverables

Do NOT summarize or skip steps. Execute the skill workflow as written.
</SPELLBOOK_CONTEXT>"""

import argparse

# ... (imports remain)

# ... (get_skill_dirs and TEMPLATE remain)

def generate_context_content(include_content: str = "") -> str:
    dirs = get_skill_dirs()
    skills = find_skills(dirs)
    
    # Sort by name
    skills.sort(key=lambda x: x['name'])
    
    skills_list = []
    for skill in skills:
        name = skill['name']
        desc = skill.get('description', 'No description provided.')
        # Clean description newlines
        desc = desc.replace('\n', ' ')
        skills_list.append(f"- **{name}**: {desc}")
        
    skill_context = TEMPLATE.format(skills_list='\n'.join(skills_list))
    
    if include_content:
        # Strip trailing whitespace to ensure consistent output
        include_content = include_content.rstrip()
        return f"{include_content}\n\n---\n\n# Spellbook Skill Registry\n\n{skill_context}"
    return skill_context

def main():
    parser = argparse.ArgumentParser(description="Generate context files for Spellbook")
    parser.add_argument("output", nargs="?", help="Output file path (default: stdout)")
    parser.add_argument("--include", help="Path to a file to include (prepend) in the output")
    
    args = parser.parse_args()
    
    include_content = ""
    if args.include:
        include_path = Path(args.include)
        if include_path.exists():
            include_content = include_path.read_text(encoding="utf-8")
        else:
            print(f"Warning: Include file not found: {args.include}", file=sys.stderr)

    content = generate_context_content(include_content)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"Generated context at {output_path}")
    else:
        print(content)

if __name__ == "__main__":
    main()
