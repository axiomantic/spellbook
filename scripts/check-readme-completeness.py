#!/usr/bin/env python3
"""
Check that all commands and skills are documented in README.md.

Exits with code 0 if all are documented, code 1 if any are missing.
"""

import os
import sys
from pathlib import Path


def main():
    # Get repo root
    repo_root = Path(__file__).parent.parent.absolute()
    readme_path = repo_root / "README.md"
    commands_dir = repo_root / "commands"
    skills_dir = repo_root / "skills"

    # Read README
    readme_content = readme_path.read_text()

    # Find all commands (exclude files starting with underscore)
    commands = []
    for cmd_file in commands_dir.glob("*.md"):
        if not cmd_file.name.startswith("_"):
            # Extract command name (filename without .md)
            commands.append(cmd_file.stem)

    # Find all skills (directories with SKILL.md, exclude underscore prefix)
    skills = []
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skills.append(skill_dir.name)

    # Check for missing documentation
    missing_commands = []
    missing_skills = []

    for cmd in commands:
        # Check if command appears in README (as /command-name or ### /command-name)
        if f"/{cmd}" not in readme_content and f"# /{cmd}" not in readme_content:
            missing_commands.append(cmd)

    for skill in skills:
        # Check if skill name appears in README (as heading or link)
        if skill not in readme_content:
            missing_skills.append(skill)

    # Report findings
    if missing_commands or missing_skills:
        print("❌ README.md is incomplete!")
        print()

        if missing_commands:
            print("Missing commands:")
            for cmd in sorted(missing_commands):
                print(f"  - /{cmd}")
            print()

        if missing_skills:
            print("Missing skills:")
            for skill in sorted(missing_skills):
                print(f"  - {skill}")
            print()

        sys.exit(1)
    else:
        print("✅ README.md documents all commands and skills")
        sys.exit(0)


if __name__ == "__main__":
    main()
