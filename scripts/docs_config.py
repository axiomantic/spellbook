#!/usr/bin/env python3
"""Shared configuration for the documentation generator and completeness check.

Both generate_docs.py and check-readme-completeness.py import from here so the
exclusion lists and name aliases stay in one place.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"

# Skills excluded from documentation generation and completeness checks.
# These are deprecated skills or thin legacy wrappers that redirect to their
# replacement. They still exist as source files for backward compatibility.
EXCLUDED_SKILLS: set[str] = {
    # Legacy wrappers (populate when rename scripts run):
    # "old-skill-name",  # renamed to "new-skill-name"
}

# Skill name aliases: source directory name -> documentation name.
# Used when a skill has been renamed in docs but the source directory
# hasn't been renamed yet (transitional state), or when the doc name
# intentionally differs from the source directory name.
SKILL_ALIASES: dict[str, str] = {
    # Populated during transitional renames. Remove entries once
    # both source dir and docs use the same name.
}

# Commands excluded from documentation generation and completeness checks.
EXCLUDED_COMMANDS: set[str] = set()

# Agents excluded from documentation generation and completeness checks.
EXCLUDED_AGENTS: set[str] = set()
