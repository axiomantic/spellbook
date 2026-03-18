#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Check that all commands, skills, and agents are documented.

Validates:
1. README.md mentions all skills/commands/agents
2. docs/ has documentation pages for all items
3. mkdocs.yml nav includes all items

Exits with code 0 if all are documented, code 1 if any are missing.
"""

import sys
from pathlib import Path

from diagram_config import (
    EXCLUDED_SKILLS,
    EXCLUDED_COMMANDS,
    EXCLUDED_AGENTS,
    SKILL_ALIASES,
)


def main():
    # Get repo root
    repo_root = Path(__file__).parent.parent.absolute()
    readme_path = repo_root / "README.md"
    mkdocs_path = repo_root / "mkdocs.yml"
    commands_dir = repo_root / "commands"
    skills_dir = repo_root / "skills"
    agents_dir = repo_root / "agents"
    docs_skills_dir = repo_root / "docs" / "skills"
    docs_commands_dir = repo_root / "docs" / "commands"
    docs_agents_dir = repo_root / "docs" / "agents"

    # Read files
    readme_content = readme_path.read_text(encoding="utf-8")
    mkdocs_content = mkdocs_path.read_text(encoding="utf-8") if mkdocs_path.exists() else ""

    # Find all commands (exclude files starting with underscore or crystallized2)
    commands = []
    for cmd_file in commands_dir.glob("*.md"):
        if not cmd_file.name.startswith("_") and "crystallized2" not in cmd_file.name:
            name = cmd_file.stem
            if name not in EXCLUDED_COMMANDS:
                commands.append(name)

    # Find all skills (directories with SKILL.md, exclude underscore prefix)
    skills = []
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                name = skill_dir.name
                if name not in EXCLUDED_SKILLS:
                    skills.append(name)

    # Find all agents (exclude files starting with underscore or crystallized2)
    agents = []
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.md"):
            if not agent_file.name.startswith("_") and "crystallized2" not in agent_file.name:
                name = agent_file.stem
                if name not in EXCLUDED_AGENTS:
                    agents.append(name)

    # Check for issues
    issues = []

    # Check README mentions all items (use alias name for renamed skills)
    for cmd in commands:
        if f"/{cmd}" not in readme_content:
            issues.append(f"README missing command: /{cmd}")

    for skill in skills:
        doc_name = SKILL_ALIASES.get(skill, skill)
        if doc_name not in readme_content and skill not in readme_content:
            issues.append(f"README missing skill: {skill}")

    for agent in agents:
        if agent not in readme_content:
            issues.append(f"README missing agent: {agent}")

    # Check docs pages exist (use alias name for renamed skills)
    for skill in skills:
        doc_name = SKILL_ALIASES.get(skill, skill)
        doc_file = docs_skills_dir / f"{doc_name}.md"
        if not doc_file.exists():
            # Also check original name as fallback
            orig_file = docs_skills_dir / f"{skill}.md"
            if not orig_file.exists():
                issues.append(f"Missing docs page: docs/skills/{doc_name}.md")

    for cmd in commands:
        doc_file = docs_commands_dir / f"{cmd}.md"
        if not doc_file.exists():
            issues.append(f"Missing docs page: docs/commands/{cmd}.md")

    for agent in agents:
        doc_file = docs_agents_dir / f"{agent}.md"
        if not doc_file.exists():
            issues.append(f"Missing docs page: docs/agents/{agent}.md")

    # Check mkdocs.yml nav includes items (use alias name for renamed skills)
    for skill in skills:
        doc_name = SKILL_ALIASES.get(skill, skill)
        if f"skills/{doc_name}.md" not in mkdocs_content and f"skills/{skill}.md" not in mkdocs_content:
            issues.append(f"mkdocs.yml nav missing: skills/{skill}.md")

    for cmd in commands:
        if f"commands/{cmd}.md" not in mkdocs_content:
            issues.append(f"mkdocs.yml nav missing: commands/{cmd}.md")

    for agent in agents:
        if f"agents/{agent}.md" not in mkdocs_content:
            issues.append(f"mkdocs.yml nav missing: agents/{agent}.md")

    # Report findings
    if issues:
        print("Documentation issues found:\n")
        for issue in sorted(issues):
            print(f"  - {issue}")
        print(f"\nTotal: {len(issues)} issues")
        print("\nRun 'python3 scripts/generate_docs.py' to regenerate docs pages.")
        sys.exit(1)
    else:
        print("All commands, skills, and agents are properly documented")
        sys.exit(0)


if __name__ == "__main__":
    main()
