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
4. README.md's "(N total)" section headings and their TOC anchors match the
   real counts. The repo forbids a count no mechanism reads; this is the
   mechanism that reads these three.
5. The reverse direction: every README table entry, every README
   link-reference definition, every mkdocs.yml nav entry, and every page
   under each generated docs/ subtree resolves to a real source file. The
   README-facing parts follow README_ARTIFACT_KINDS; the nav checks and the
   orphan-page sweep read mkdocs.yml and docs/ rather than README, so they
   follow DOCUMENTED_TREES and cover rules as well.

Checks 1-4 are one-directional -- they assert that every real item is
documented, never that every documented item is real. That asymmetry let
seven skills and five commands keep shipping documentation pages,
README rows, and nav entries for months after their sources were
deleted. Check 5 is the missing direction; without it the rot is
invisible by construction.

Exits with code 0 if all are documented, code 1 if any are missing.
"""

import re
import sys
from pathlib import Path

from corpus_trees import DOCUMENTED_TREES, README_ARTIFACT_KINDS
from docs_config import (
    EXCLUDED_SKILLS,
    EXCLUDED_COMMANDS,
    EXCLUDED_AGENTS,
    SKILL_ALIASES,
)


DOCS_BASE_URL = "https://axiomantic.github.io/spellbook/latest/"

# A link-reference definition may legitimately point at hand-authored docs
# (guides, reference pages) rather than at a generated artifact page. Only
# these three prefixes name an artifact with a README table and link
# definitions; `rules` is absent because README has no Rules section.
ARTIFACT_PREFIXES = README_ARTIFACT_KINDS

# The orphan sweep reads docs/, not README, so the README-table exclusion of
# `rules` never applied to it. Every tree that generates pages can orphan
# them, so the sweep follows what is GENERATED, not what README tabulates.
ORPHAN_SWEEP_TREES = DOCUMENTED_TREES

# The nav publishes every generated tree, rules included, so both nav
# directions follow DOCUMENTED_TREES rather than README_ARTIFACT_KINDS. The
# alternation is BUILT from that tuple: a literal re-spelling of the same
# names is the drift this module exists to prevent.
NAV_TREES = DOCUMENTED_TREES

LINK_DEF_RE = re.compile(r"^\[([^\]^]+)\]:[ \t]*(\S+)[ \t]*$", re.M)
NAV_ENTRY_RE = re.compile(
    rf"\b({'|'.join(re.escape(t) for t in NAV_TREES)})/([A-Za-z0-9._-]+)\.md\b"
)


def real_sources(repo_root):
    """Return the set of names that actually exist on disk, per artifact kind.

    Commands come in two shapes: a flat ``commands/<name>.md`` and a
    directory ``commands/<name>/<name>.md``. Both are real, and a reverse
    check that knows only the flat shape would report the two
    subdirectory commands as phantoms.
    """
    skills = {
        d.name
        for d in (repo_root / "skills").iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "SKILL.md").exists()
    }
    commands = {
        f.stem
        for f in (repo_root / "commands").glob("*.md")
        if not f.name.startswith("_") and "crystallized2" not in f.name
    }
    commands |= {
        d.name
        for d in (repo_root / "commands").iterdir()
        if d.is_dir() and (d / f"{d.name}.md").exists()
    }
    agents = set()
    if (repo_root / "agents").exists():
        agents = {
            f.stem
            for f in (repo_root / "agents").glob("*.md")
            if not f.name.startswith("_") and "crystallized2" not in f.name
        }
    # Rules have no README table, but they DO generate docs/rules/ pages, so
    # the orphan sweep needs a real-source set to check those pages against.
    rules = set()
    if (repo_root / "rules").exists():
        rules = {
            f.stem
            for f in (repo_root / "rules").glob("*.md")
            if not f.name.startswith("_")
        }
    return {"skills": skills, "commands": commands, "agents": agents, "rules": rules}


def section(readme_content, label):
    """Return the README text under '### <label> (N total)'."""
    match = re.search(rf"^### {label} \(\d+ total\)$", readme_content, re.M)
    if match is None:
        return ""
    rest = readme_content[match.end():]
    nxt = re.search(r"^### \w+ \(\d+ total\)$|^## ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def check_reverse(repo_root, readme_content, mkdocs_content, issues):
    """Assert every documented item resolves to a real source file.

    Named separately from the forward checks because the two directions
    fail for opposite reasons: forward failure means someone added a
    source without documenting it, reverse failure means someone deleted
    a source and left its documentation behind.
    """
    real = real_sources(repo_root)

    # README table entries. Skills and agents are shortcut links '[name]';
    # commands carry a leading slash, '[/name]'.
    for label, kind, pattern in (
        ("Skills", "skills", r"\[([a-z0-9][a-z0-9-]*)\]"),
        ("Commands", "commands", r"^\| \[/([a-z0-9][a-z0-9:-]*)\]"),
        ("Agents", "agents", r"^\| \[([a-z0-9][a-z0-9-]*)\]"),
    ):
        body = section(readme_content, label)
        rows = "".join(
            line + "\n" for line in body.splitlines() if line.startswith("| ")
        )
        for name in sorted(set(re.findall(pattern, rows, re.M))):
            if name not in real[kind]:
                issues.append(
                    f"README {label} table lists '{name}', which has no source "
                    f"under {kind}/"
                )

    # README link-reference definitions.
    seen = {}
    for name, url in LINK_DEF_RE.findall(readme_content):
        if name in seen:
            issues.append(f"README link definition duplicated: [{name}]")
        seen[name] = url
        if not url.startswith(DOCS_BASE_URL):
            continue
        parts = [p for p in url[len(DOCS_BASE_URL):].split("/") if p]
        if not parts or parts[0] not in ARTIFACT_PREFIXES:
            continue
        kind, rest = parts[0], parts[1:]
        if len(rest) == 1:
            if rest[0] not in real[kind]:
                issues.append(
                    f"README link definition [{name}] points at {kind}/{rest[0]}, "
                    f"which has no source"
                )
        elif len(rest) == 2 and kind == "skills":
            # A nested reference page inside a skill directory, e.g.
            # skills/shared-references/cove-protocol.
            nested = repo_root / "skills" / rest[0] / f"{rest[1]}.md"
            if not nested.exists():
                issues.append(
                    f"README link definition [{name}] points at "
                    f"skills/{rest[0]}/{rest[1]}, which has no source file"
                )

    # mkdocs.yml nav and exclude_docs entries.
    for kind, name in sorted(set(NAV_ENTRY_RE.findall(mkdocs_content))):
        if name == "index":
            continue
        if name not in real[kind]:
            issues.append(
                f"mkdocs.yml references {kind}/{name}.md, which has no source "
                f"under {kind}/"
            )

    # Generated documentation pages.
    for kind in ORPHAN_SWEEP_TREES:
        docs_subdir = repo_root / "docs" / kind
        if not docs_subdir.exists():
            continue
        for page in sorted(docs_subdir.glob("*.md")):
            if page.stem == "index":
                continue
            if page.stem not in real[kind]:
                issues.append(
                    f"Orphan docs page: docs/{kind}/{page.name} has no source "
                    f"under {kind}/"
                )


def main():
    # Get repo root
    repo_root = Path(__file__).parent.parent.absolute()
    readme_path = repo_root / "README.md"
    mkdocs_path = repo_root / "mkdocs.yml"
    skills_dir = repo_root / "skills"
    agents_dir = repo_root / "agents"
    docs_skills_dir = repo_root / "docs" / "skills"
    docs_commands_dir = repo_root / "docs" / "commands"
    docs_agents_dir = repo_root / "docs" / "agents"

    # Read files
    readme_content = readme_path.read_text(encoding="utf-8")
    mkdocs_content = mkdocs_path.read_text(encoding="utf-8") if mkdocs_path.exists() else ""

    # Find all commands, in BOTH shapes: flat `commands/<name>.md` and directory
    # `commands/<name>/<name>.md`. Globbing only the flat shape made the forward
    # checks disagree with the README table the reverse check reads, so the
    # '### Commands (N total)' heading undercounted by the number of
    # subdirectory commands while every check still reported green.
    # real_sources() is the single definition of what a command is; deriving
    # from it keeps the two directions from drifting apart again.
    commands = sorted(real_sources(repo_root)["commands"] - set(EXCLUDED_COMMANDS))

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

    # Rules have no README table, so they are absent from the checks above --
    # but generate_docs.py publishes docs/rules/ and mkdocs.yml navigates it,
    # so the nav direction applies to them exactly like the other trees.
    for rule in sorted(real_sources(repo_root)["rules"]):
        if f"rules/{rule}.md" not in mkdocs_content:
            issues.append(f"mkdocs.yml nav missing: rules/{rule}.md")

    # Check the "(N total)" counts in README section headings and TOC anchors.
    for label, items in (("Skills", skills), ("Commands", commands), ("Agents", agents)):
        expected = len(items)
        heading = re.search(rf"^### {label} \((\d+) total\)$", readme_content, re.M)
        if heading is None:
            issues.append(f"README missing heading: ### {label} (N total)")
        elif int(heading.group(1)) != expected:
            issues.append(
                f"README heading '### {label} ({heading.group(1)} total)' is stale; "
                f"the tree holds {expected}"
            )
        anchor = re.search(
            rf"\[{label} \((\d+) total\)\]\(#{label.lower()}-(\d+)-total\)",
            readme_content,
        )
        if anchor is None:
            issues.append(f"README TOC missing entry for {label} (N total)")
        elif {int(anchor.group(1)), int(anchor.group(2))} != {expected}:
            issues.append(
                f"README TOC entry for {label} says "
                f"{anchor.group(1)}/#{label.lower()}-{anchor.group(2)}-total; "
                f"the tree holds {expected}"
            )

    check_reverse(repo_root, readme_content, mkdocs_content, issues)

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
