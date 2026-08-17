#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Generate documentation pages from SKILL.md, command, agent, and rule files.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

from diagram_config import (
    EXCLUDED_AGENTS,
    EXCLUDED_COMMANDS,
    EXCLUDED_SKILLS,
)

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"
RULES_DIR = REPO_ROOT / "rules"
DOCS_DIR = REPO_ROOT / "docs"
DIAGRAMS_DIR = DOCS_DIR / "diagrams"

# Skills that came from superpowers
SUPERPOWERS_SKILLS = {
    "design-exploration",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
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

SUPERPOWERS_COMMANDS = {"design-explore", "execute-plan", "write-plan"}

SUPERPOWERS_AGENTS = {"code-reviewer"}


_FENCE_RUN = re.compile(r"^\s{0,3}(`{3,})", re.MULTILINE)


def fence_for(body: str) -> str:
    """Return the shortest fence that can legally wrap ``body``.

    Every generator below embeds a raw source body inside a fenced block so
    that XML-style tags (``<CRITICAL>``, ``<RULE>``) are shown rather than
    swallowed as HTML. CommonMark only requires the wrapping fence to be
    LONGER than the longest fence inside it, so the fence length is a
    property of the body, not a constant.

    This used to be a hardcoded ten backticks everywhere. That is legal but
    reads as noise -- a body containing no fences at all got the same
    ``` `````````` ``` wrapper as a deeply nested one.
    """
    longest = max((len(m.group(1)) for m in _FENCE_RUN.finditer(body)), default=0)
    return "`" * max(3, longest + 1)


def write_if_changed(path: Path, content: str) -> bool:
    """
    Write content to file only if it differs from existing content.

    Returns True if file was written, False if unchanged.
    """
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.write_text(content, encoding="utf-8")
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
        item_name: The item name (e.g., 'develop')

    Returns:
        Markdown section with diagram content, or empty string if no diagram exists.
    """
    diagram_file = DIAGRAMS_DIR / item_type / f"{item_name}.md"
    if not diagram_file.exists():
        return ""

    content = diagram_file.read_text(encoding="utf-8")

    # Strip the metadata comment line (first line starting with <!-- diagram-meta:)
    lines = content.split("\n", 1)
    if lines and lines[0].startswith("<!-- diagram-meta:"):
        body = lines[1] if len(lines) > 1 else ""
    else:
        body = content

    # Strip the "# Diagram:" header (redundant when embedded under "## Workflow Diagram")
    body_stripped = body.lstrip("\n")
    if body_stripped.startswith("# Diagram:"):
        _, _, body_stripped = body_stripped.partition("\n")
        body = body_stripped

    if not body.strip():
        return ""

    return f"\n## Workflow Diagram\n\n{body.strip()}\n\n"


def generate_skill_doc(skill_dir: Path) -> str | None:
    """Generate documentation page for a skill."""
    skill_name = skill_dir.name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return None

    content = skill_file.read_text(encoding="utf-8")
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
    intro = frontmatter.get("intro", "")
    if intro:
        parts.append(f"\n{intro.rstrip()}\n")
    if description:
        # Frame the description as an auto-invocation trigger (descriptions are
        # written for the AI assistant, not for human readers)
        parts.append("\n**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.\n")
        parts.append(f"\n> {description.rstrip()}\n")
    if attribution:
        parts.append(f"\n{attribution}")

    # Include diagram if available
    diagram = get_diagram_section("skills", skill_name)
    if diagram:
        # Strip leading \n when preceded by attribution (which ends with \n\n)
        # to avoid double blank lines that the markdown linter normalizes away
        parts.append(diagram.lstrip("\n") if attribution else diagram)

    parts.append("## Skill Content\n\n")
    fence = fence_for(body)
    parts.append(f"{fence}markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append(f"{fence}\n")

    return "".join(parts)


def generate_command_doc(command_file: Path) -> str:
    """Generate documentation page for a command."""
    command_name = command_file.stem
    content = command_file.read_text(encoding="utf-8")
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
    fence = fence_for(body)
    parts.append(f"{fence}markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append(f"{fence}\n")

    return "".join(parts)


def generate_agent_doc(agent_file: Path) -> str:
    """Generate documentation page for an agent."""
    agent_name = agent_file.stem
    content = agent_file.read_text(encoding="utf-8")
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
    fence = fence_for(body)
    parts.append(f"{fence}markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append(f"{fence}\n")

    return "".join(parts)


def generate_rule_doc(rule_file: Path) -> str:
    """Generate documentation page for a rule module."""
    content = rule_file.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(content)

    name = frontmatter.get("name", rule_file.stem)
    module_class = frontmatter.get("class", "preference")
    description = frontmatter.get("description", "")
    benefit = frontmatter.get("benefit", "")
    declining_means = frontmatter.get("declining_means", "")
    related = frontmatter.get("related") or []

    parts = [f"# {name}\n"]

    if module_class == "mandatory":
        parts.append(
            '\n!!! warning "Mandatory module"\n'
            "    This module installs on every platform and cannot be declined.\n\n"
        )
    else:
        default_state = str(frontmatter.get("default", "off"))
        pre_checked = "pre-checked" if default_state == "on" else "unchecked"
        parts.append(
            '\n!!! info "Optional module"\n'
            f"    The installer offers this module {pre_checked}. "
            f"Config key: `rules.module.{frontmatter.get('id', rule_file.stem)}`.\n\n"
        )

    if description:
        parts.append(f"{' '.join(str(description).split())}\n\n")

    if benefit:
        parts.append(f"**Why keep it:** {' '.join(str(benefit).split())}\n\n")

    if declining_means:
        parts.append(f"**If you decline:** {' '.join(str(declining_means).split())}\n\n")

    if related:
        parts.append("**Related artifacts:**\n\n")
        for ref in related:
            parts.append(f"- `{ref}`\n")
        parts.append("\n")

    # Wrap body in a markdown code block to prevent XML-style tags (<CRITICAL>,
    # <RULE>) from being swallowed as HTML, as the other generators do.
    parts.append("## Rule Content\n\n")
    fence = fence_for(body)
    parts.append(f"{fence}markdown\n")
    parts.append(body)
    if not body.endswith("\n"):
        parts.append("\n")
    parts.append(f"{fence}\n")

    return "".join(parts)


def collect_docs() -> tuple[dict[Path, str], dict[str, int]]:
    """Render every generated page in memory, writing nothing.

    Splitting rendering from writing is what lets ``--check`` report
    staleness without touching the tree (Check 2/Check 3): the same
    content the default mode would write is compared against what is on
    disk. Insertion order is the write/report order.
    """
    docs: dict[Path, str] = {}

    # Generate skill docs
    skill_count = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.is_dir() and skill_dir.name not in EXCLUDED_SKILLS and (skill_dir / "SKILL.md").exists():
            doc = generate_skill_doc(skill_dir)
            if doc:
                output_file = DOCS_DIR / "skills" / f"{skill_dir.name}.md"
                docs[output_file] = doc
                skill_count += 1

    # Generate command docs (flat files)
    command_count = 0
    for cmd_file in sorted(COMMANDS_DIR.glob("*.md")):
        if "crystallized2" in cmd_file.name:
            continue
        if cmd_file.stem in EXCLUDED_COMMANDS:
            continue
        doc = generate_command_doc(cmd_file)
        if doc:
            output_file = DOCS_DIR / "commands" / cmd_file.name
            docs[output_file] = doc
            command_count += 1

    # Generate command docs (nested directories like commands/systematic-debugging/)
    for cmd_dir in sorted(COMMANDS_DIR.iterdir()):
        if cmd_dir.is_dir() and cmd_dir.name not in EXCLUDED_COMMANDS:
            # Look for main command file (same name as directory)
            main_cmd = cmd_dir / f"{cmd_dir.name}.md"
            if main_cmd.exists():
                doc = generate_command_doc(main_cmd)
                if doc:
                    output_file = DOCS_DIR / "commands" / f"{cmd_dir.name}.md"
                    docs[output_file] = doc
                    command_count += 1

    # Generate agent docs
    agent_count = 0
    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        if "crystallized2" in agent_file.name:
            continue
        if agent_file.stem in EXCLUDED_AGENTS:
            continue
        doc = generate_agent_doc(agent_file)
        if doc:
            output_file = DOCS_DIR / "agents" / agent_file.name
            docs[output_file] = doc
            agent_count += 1

    # Generate rule module docs
    rule_count = 0
    for rule_file in sorted(RULES_DIR.glob("*.md")):
        doc = generate_rule_doc(rule_file)
        if doc:
            output_file = DOCS_DIR / "rules" / rule_file.name
            docs[output_file] = doc
            rule_count += 1

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
        content = cmd_file.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter(content)
        desc = frontmatter.get("description", "")
        if isinstance(desc, str):
            # Collapse multi-line descriptions to single line, truncate
            desc = " ".join(desc.split())[:80]
            if len(frontmatter.get("description", "")) > 80:
                desc += "..."
        origin = "[superpowers](https://github.com/obra/superpowers)" if name in SUPERPOWERS_COMMANDS else "spellbook"
        commands_index += f"| [/{name}]({name}.md) | {desc} | {origin} |\n"

    docs[DOCS_DIR / "commands" / "index.md"] = commands_index

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

    docs[DOCS_DIR / "agents" / "index.md"] = agents_index

    # Generate rules index
    rules_index = """# Rule Modules Overview

Rule modules are the behavioral instructions spellbook installs into your coding
assistant. Each module is a separate file under `rules/`, delivered as a symlink
on harnesses that read a rules directory and as a generated bundle on harnesses
that read a single instruction file.

Mandatory modules install on every platform. Optional modules are offered during
installation and recorded under the `rules.module.<id>` config keys, so a module
you decline is never reinstalled and a module added later is offered once.

## Available Rule Modules

| Module | Class | Description |
|--------|-------|-------------|
"""
    for rule_file in sorted(RULES_DIR.glob("*.md")):
        content = rule_file.read_text(encoding="utf-8")
        frontmatter, _ = extract_frontmatter(content)
        name = frontmatter.get("name", rule_file.stem)
        module_class = frontmatter.get("class", "preference")
        if module_class == "mandatory":
            class_label = "mandatory"
        else:
            default_state = str(frontmatter.get("default", "off"))
            class_label = f"optional (default {default_state})"
        desc = " ".join(str(frontmatter.get("description", "")).split())
        rules_index += f"| [{name}]({rule_file.name}) | {class_label} | {desc} |\n"

    docs[DOCS_DIR / "rules" / "index.md"] = rules_index

    counts = {
        "skills": skill_count,
        "commands": command_count,
        "agents": agent_count,
        "rules": rule_count,
    }
    return docs, counts


def stale_docs(docs: dict[Path, str]) -> list[Path]:
    """Return the generated paths whose on-disk content is missing or stale."""
    stale = []
    for path, content in docs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            stale.append(path)
    return stale


def build_parser() -> argparse.ArgumentParser:
    """Argument handling for the generator.

    Without a parser, `--help` was silently ignored and the script
    rewrote the mirror as a side effect of asking for usage. Every flag
    is now parsed, so an unknown flag is an error rather than a write.
    """
    parser = argparse.ArgumentParser(
        prog="generate_docs",
        description=(
            "Generate the docs/ mirror from skills, commands, agents, and "
            "rule modules. With no arguments, writes the mirror in place."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Do not write anything. Exit non-zero if any generated page is "
            "missing or stale, listing the offending paths."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    docs, counts = collect_docs()
    summary = (
        f"\nProcessed {counts['skills']} skills, {counts['commands']} commands, "
        f"{counts['agents']} agents, {counts['rules']} rule modules"
    )

    # --check must write nothing at all: no page contents and no output
    # directories. Comparison happens purely in memory.
    if args.check:
        stale = stale_docs(docs)
        print(summary)
        if stale:
            print(f"Stale or missing generated page(s): {len(stale)}")
            for path in stale:
                print(f"  {path.relative_to(REPO_ROOT)}")
            print("Run: python3 scripts/generate_docs.py")
            return 1
        print("All files up to date")
        return 0

    for subdir in ("skills", "commands", "agents", "rules"):
        (DOCS_DIR / subdir).mkdir(parents=True, exist_ok=True)

    files_changed = 0
    for path, content in docs.items():
        if write_if_changed(path, content):
            files_changed += 1
            print(f"Generated: {path.relative_to(DOCS_DIR)}")

    print(summary)
    if files_changed > 0:
        print(f"Updated {files_changed} file(s)")
    else:
        print("All files up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
