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

try:
    from spellbook_mcp.skill_ops import find_skills
    # Mimic server.py's get_skill_dirs logic but simplified for generation
    # We want to document ALL skills found in the standard locations
    def get_skill_dirs() -> List[Path]:
        dirs = []
        home = Path.home()
        dirs.append(home / ".config" / "opencode" / "skills")
        dirs.append(home / ".opencode" / "skills")
        dirs.append(home / ".codex" / "skills")
        
        # This repo's skills
        repo_root = Path(__file__).parent.parent
        dirs.append(repo_root / "skills")

        # Claude config skills
        claude_config = os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))
        dirs.append(Path(claude_config) / "skills")

        return [d for d in dirs if d.exists()]

except ImportError:
    # Fallback if spellbook_mcp not importable (should not happen if structure preserved)
    print("Error: Could not import spellbook_mcp.skill_ops")
    sys.exit(1)

TEMPLATE = """<SPELLBOOK_CONTEXT>
You are equipped with "Spellbook" - a library of expert agent skills.

## Available Skills

{skills_list}

## Instruction
1. **Analyze the User Request**: Compare it against the skill descriptions above.
2. **Auto-Trigger**: If a skill matches the intent (e.g. user asks to "debug"), you MUST load it.
3. **Load Skill**: Use the tool `spellbook.use_spellbook_skill(skill_name="...")` (or `spellbook-codex use-skill ...` in Codex).
4. **Follow Instructions**: The tool will return the skill's specific instructions. Follow them rigorously.
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
