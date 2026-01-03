#!/usr/bin/env python3
"""
Generate context files (GEMINI.md, AGENTS.md) for Spellbook.
Scans available skills and creates a system prompt with skill triggers.
"""
import sys
import os
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
        
        # Superpowers
        claude_config = os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))
        dirs.append(Path(claude_config) / "skills")
        dirs.append(home / "Development" / "superpowers" / "skills")
        
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

def generate_context_content() -> str:
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
        
    return TEMPLATE.format(skills_list='\n'.join(skills_list))

def main():
    content = generate_context_content()
    
    # Default output is stdout
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        print(f"Generated context at {output_path}")
    else:
        print(content)

if __name__ == "__main__":
    main()
