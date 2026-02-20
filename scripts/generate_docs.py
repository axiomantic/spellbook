#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Generate documentation pages from SKILL.md, command, and agent files.
"""
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"
DOCS_DIR = REPO_ROOT / "docs"
DIAGRAMS_DIR = DOCS_DIR / "diagrams"

# Skills that came from superpowers
SUPERPOWERS_SKILLS = {
    "brainstorming",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-skills",
    "verification-before-completion",
    "writing-plans",
    "writing-skills",
}

SUPERPOWERS_COMMANDS = {"brainstorm", "execute-plan", "write-plan"}

SUPERPOWERS_AGENTS = {"code-reviewer"}


def write_if_changed(path: Path, content: str) -> bool:
    """
    Write content to file only if it differs from existing content.

    Returns True if file was written, False if unchanged.
    """
    if path.exists():
        existing = path.read_text()
        if existing == content:
            return False
    path.write_text(content)
    return True


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}

    return frontmatter, parts[2].strip()


def get_diagram_section(item_type: str, item_name: str) -> str:
    """Return a diagram section if a diagram file exists for this item.

    Args:
        item_type: 'skills' or 'commands'
        item_name: The item name (e.g., 'implementing-features')

    Returns:
        Markdown section with diagram content, or empty string if no diagram exists.
    """
    diagram_file = DIAGRAMS_DIR / item_type / f"{item_name}.md"
    if not diagram_file.exists():
        return ""

    content = diagram_file.read_text()

    # Strip the metadata comment line (first line starting with <!-- diagram-meta:)
    lines = content.split("\n", 1)
    if lines and lines[0].startswith("<!-- diagram-meta:"):
        body = lines[1] if len(lines) > 1 else ""
    else:
        body = content

    if not body.strip():
        return ""

    return f"\n## Workflow Diagram\n\n{body.strip()}\n\n"


def generate_skill_doc(skill_dir: Path) -> str | None:
    """Generate documentation page for a skill."""
    skill_name = skill_dir.name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return None

    content = skill_file.read_text()
    frontmatter, body = extract_frontmatter(content)

    name = frontmatter.get("name", skill_name)
    description = frontmatter.get("description", "")

    # Check if from superpowers
    from_superpowers = skill_name in SUPERPOWERS_SKILLS
    attribution = ""
    if from_superpowers:
        attribution = '!!! info "Origin"\n    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).\n\n'

    # Build doc with proper spacing
    # Wrap body in markdown code block to prevent XML-style tags from rendering as HTML
    parts = [f"# {name}\n"]
    if description:
        parts.append(f"\n{description.rstrip()}\n")
    if attribution:
        parts.append(f"\n{attribution}")

    # Include diagram if available
    diagram = get_diagram_section("skills", skill_name)
    if diagram:
        # Strip leading \n when preceded by attribution (which ends with \n\n)
        # to avoid double blank lines that the markdown linter normalizes away
        parts.append(diagram.lstrip("\n") if attribution else diagram)

    parts.append("## Skill Content\n\n")
    parts.append("``````````markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append("``````````\n")

    return "".join(parts)


def generate_command_doc(command_file: Path) -> str:
    """Generate documentation page for a command."""
    command_name = command_file.stem
    content = command_file.read_text()
    frontmatter, body = extract_frontmatter(content)

    # Check if from superpowers
    from_superpowers = command_name in SUPERPOWERS_COMMANDS
    attribution = ""
    if from_superpowers:
        attribution = '!!! info "Origin"\n    This command originated from [obra/superpowers](https://github.com/obra/superpowers).\n\n'

    # Build doc with proper spacing
    # Wrap body in markdown code block to prevent XML-style tags from rendering as HTML
    parts = [f"# /{command_name}\n"]
    if attribution:
        parts.append(f"\n{attribution}")

    # Include diagram if available
    diagram = get_diagram_section("commands", command_name)
    if diagram:
        parts.append(diagram.lstrip("\n") if attribution else diagram)

    parts.append("## Command Content\n\n")
    parts.append("``````````markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append("``````````\n")

    return "".join(parts)


def generate_agent_doc(agent_file: Path) -> str:
    """Generate documentation page for an agent."""
    agent_name = agent_file.stem
    content = agent_file.read_text()
    frontmatter, body = extract_frontmatter(content)

    # Check if from superpowers
    from_superpowers = agent_name in SUPERPOWERS_AGENTS
    attribution = ""
    if from_superpowers:
        attribution = '!!! info "Origin"\n    This agent originated from [obra/superpowers](https://github.com/obra/superpowers).\n\n'

    # Build doc with proper spacing
    # Wrap body in markdown code block to prevent XML-style tags from rendering as HTML
    parts = [f"# {agent_name}\n"]
    if attribution:
        parts.append(f"\n{attribution}")

    # Include diagram if available
    diagram = get_diagram_section("agents", agent_name)
    if diagram:
        parts.append(diagram.lstrip("\n") if attribution else diagram)

    parts.append("## Agent Content\n\n")
    parts.append("``````````markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append("``````````\n")

    return "".join(parts)


def main():
    # Create output directories
    (DOCS_DIR / "skills").mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "commands").mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "agents").mkdir(parents=True, exist_ok=True)

    # Generate skill docs
    skill_count = 0
    files_changed = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            doc = generate_skill_doc(skill_dir)
            if doc:
                output_file = DOCS_DIR / "skills" / f"{skill_dir.name}.md"
                if write_if_changed(output_file, doc):
                    files_changed += 1
                    print(f"Generated: skills/{skill_dir.name}.md")
                skill_count += 1

    # Generate command docs (flat files)
    command_count = 0
    for cmd_file in sorted(COMMANDS_DIR.glob("*.md")):
        doc = generate_command_doc(cmd_file)
        if doc:
            output_file = DOCS_DIR / "commands" / cmd_file.name
            if write_if_changed(output_file, doc):
                files_changed += 1
                print(f"Generated: commands/{cmd_file.name}")
            command_count += 1

    # Generate command docs (nested directories like commands/systematic-debugging/)
    for cmd_dir in sorted(COMMANDS_DIR.iterdir()):
        if cmd_dir.is_dir():
            # Look for main command file (same name as directory)
            main_cmd = cmd_dir / f"{cmd_dir.name}.md"
            if main_cmd.exists():
                doc = generate_command_doc(main_cmd)
                if doc:
                    output_file = DOCS_DIR / "commands" / f"{cmd_dir.name}.md"
                    if write_if_changed(output_file, doc):
                        files_changed += 1
                        print(f"Generated: commands/{cmd_dir.name}.md")
                    command_count += 1

    # Generate agent docs
    agent_count = 0
    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        doc = generate_agent_doc(agent_file)
        if doc:
            output_file = DOCS_DIR / "agents" / agent_file.name
            if write_if_changed(output_file, doc):
                files_changed += 1
                print(f"Generated: agents/{agent_file.name}")
            agent_count += 1

    # Generate commands index
    commands_index = """# Commands Overview

Commands are slash commands that can be invoked with `/<command-name>` in Claude Code.

## Available Commands

| Command | Description | Origin |
|---------|-------------|--------|
"""
    # Collect all command files (flat and nested)
    all_cmd_files = []
    for cmd_file in COMMANDS_DIR.glob("*.md"):
        all_cmd_files.append((cmd_file.stem, cmd_file))
    for cmd_dir in COMMANDS_DIR.iterdir():
        if cmd_dir.is_dir():
            main_cmd = cmd_dir / f"{cmd_dir.name}.md"
            if main_cmd.exists():
                all_cmd_files.append((cmd_dir.name, main_cmd))

    for name, cmd_file in sorted(all_cmd_files, key=lambda x: x[0]):
        content = cmd_file.read_text()
        frontmatter, body = extract_frontmatter(content)
        desc = frontmatter.get("description", "")
        if isinstance(desc, str):
            # Collapse multi-line descriptions to single line, truncate
            desc = " ".join(desc.split())[:80]
            if len(frontmatter.get("description", "")) > 80:
                desc += "..."
        origin = "[superpowers](https://github.com/obra/superpowers)" if name in SUPERPOWERS_COMMANDS else "spellbook"
        commands_index += f"| [/{name}]({name}.md) | {desc} | {origin} |\n"

    if write_if_changed(DOCS_DIR / "commands" / "index.md", commands_index):
        files_changed += 1
        print("Generated: commands/index.md")

    # Generate agents index
    agents_index = """# Agents Overview

Agents are specialized reviewers that can be invoked for specific tasks.

## Available Agents

| Agent | Description | Origin |
|-------|-------------|--------|
"""
    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        name = agent_file.stem
        origin = "[superpowers](https://github.com/obra/superpowers)" if name in SUPERPOWERS_AGENTS else "spellbook"
        agents_index += f"| [{name}]({name}.md) | Specialized code review agent | {origin} |\n"

    if write_if_changed(DOCS_DIR / "agents" / "index.md", agents_index):
        files_changed += 1
        print("Generated: agents/index.md")

    print(f"\nProcessed {skill_count} skills, {command_count} commands, {agent_count} agents")
    if files_changed > 0:
        print(f"Updated {files_changed} file(s)")
    else:
        print("All files up to date")


if __name__ == "__main__":
    main()
