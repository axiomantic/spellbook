#!/usr/bin/env python3
"""Shared configuration for diagram generation and freshness checking.

Both generate_diagrams.py and check_diagram_freshness.py import from here
to avoid duplicating tiering configuration and exclusion lists.
"""

import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"
DIAGRAMS_DIR = REPO_ROOT / "docs" / "diagrams"

# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------

# Skills excluded from diagram generation and freshness checks.
# These are deprecated skills or thin legacy wrappers that redirect
# to their replacement. They still exist as source files for backward
# compatibility but should not have their own diagrams.
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

# Commands excluded from diagram generation and freshness checks.
EXCLUDED_COMMANDS: set[str] = set()

# Agents excluded from diagram generation and freshness checks.
EXCLUDED_AGENTS: set[str] = set()

# ---------------------------------------------------------------------------
# Tiering configuration
# ---------------------------------------------------------------------------

# Skills that require diagrams (multi-phase, complex workflow skills)
MANDATORY_SKILLS: set[str] = {
    "advanced-code-review",
    "analyzing-domains",
    "auditing-green-mirage",
    "autonomous-roundtable",
    "design-exploration",
    "code-review",
    "debugging",
    "deep-research",
    "designing-workflows",
    "distilling-prs",
    "executing-plans",
    "finding-dead-code",
    "finishing-a-development-branch",
    "fixing-tests",
    "gathering-requirements",
    "generating-diagrams",
    "develop",
    "requesting-code-review",
    "reviewing-design-docs",
    "reviewing-impl-plans",
    "security-auditing",
    "test-driven-development",
    "writing-plans",
    "writing-skills",
}

# Command name prefixes that indicate phase commands (mandatory diagrams)
MANDATORY_COMMAND_PREFIXES: tuple[str, ...] = (
    "advanced-code-review-",
    "audit-mirage-",
    "code-review-",
    "dead-code-",
    "deep-research-",
    "distill-",
    "fact-check-",
    "feature-",
    "finish-branch-",
    "fix-tests-",
    "merge-worktree-",
    "pr-distill",
    "request-review-",
    "review-design-",
    "review-plan-",
    "simplify-",
)

# All agents are mandatory (small set, always worth diagramming)
MANDATORY_AGENTS: bool = True


# ---------------------------------------------------------------------------
# Structure hashing
# ---------------------------------------------------------------------------

# Regex to match YAML frontmatter: opening --- at start of file, content, closing ---
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)

# Regex to match markdown headings (ATX-style: lines starting with one or more #)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from markdown content.

    Frontmatter is delimited by ``---`` on its own line at the very start
    of the file and a closing ``---`` line.
    """
    return _FRONTMATTER_RE.sub("", content)


def extract_headings(content: str) -> list[str]:
    """Extract all markdown heading lines from content.

    Returns a list of strings like ``"## Section Name"`` preserving the
    heading level prefix so that hierarchy changes are detected.
    """
    return [f"{m.group(1)} {m.group(2)}" for m in _HEADING_RE.finditer(content)]


def compute_structure_hash(filepath: Path) -> str:
    """Compute a SHA256 hash of a markdown file's heading structure.

    The hash is based solely on the ATX-style headings (``#``, ``##``, etc.)
    after stripping any YAML frontmatter.  This means changes to body text,
    frontmatter metadata, or non-heading content do **not** alter the hash,
    preventing unnecessary diagram regeneration for cosmetic edits.
    """
    content = filepath.read_text(encoding="utf-8")
    content = strip_frontmatter(content)
    headings = extract_headings(content)
    structure = "\n".join(headings)
    return hashlib.sha256(structure.encode("utf-8")).hexdigest()
