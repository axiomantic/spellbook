#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Pre-commit validation script that checks diagram freshness via content hash comparison.

For each skill and command source file, computes a SHA256 hash and compares it against
the hash stored in the corresponding diagram file's metadata comment. Items are tiered
as mandatory (multi-phase skills and phase commands) or optional (everything else).

Mandatory items that are stale or missing cause exit code 1.
Optional items that are stale or missing produce warnings only.

Usage:
    python3 scripts/check_diagram_freshness.py
    python3 scripts/check_diagram_freshness.py --json
    python3 scripts/check_diagram_freshness.py --include-optional
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"
DIAGRAMS_DIR = REPO_ROOT / "docs" / "diagrams"

# ---------------------------------------------------------------------------
# Tiering configuration
# ---------------------------------------------------------------------------

# Skills that require diagrams (multi-phase, complex workflow skills)
MANDATORY_SKILLS: set[str] = {
    "advanced-code-review",
    "analyzing-domains",
    "auditing-green-mirage",
    "autonomous-roundtable",
    "brainstorming",
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
    "implementing-features",
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

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


# All agents are mandatory (small set, always worth diagramming)
MANDATORY_AGENTS: bool = True


class SourceItem(NamedTuple):
    """A discovered source file with its tier classification."""
    name: str
    kind: str          # "skill", "command", or "agent"
    source_path: Path
    diagram_path: Path
    mandatory: bool


class CheckResult(NamedTuple):
    """Result of a freshness check for a single item."""
    item: SourceItem
    status: str        # "fresh", "stale", "missing"
    current_hash: str
    stored_hash: str   # empty string if diagram missing or unparseable


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_skills() -> list[SourceItem]:
    """Scan skills/ for source files, classify each as mandatory or optional."""
    items: list[SourceItem] = []
    if not SKILLS_DIR.is_dir():
        return items

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        name = skill_dir.name
        diagram_path = DIAGRAMS_DIR / "skills" / f"{name}.md"
        mandatory = name in MANDATORY_SKILLS
        items.append(SourceItem(
            name=name,
            kind="skill",
            source_path=skill_file,
            diagram_path=diagram_path,
            mandatory=mandatory,
        ))

    return items


def discover_commands() -> list[SourceItem]:
    """Scan commands/ for source files, classify each as mandatory or optional."""
    items: list[SourceItem] = []
    if not COMMANDS_DIR.is_dir():
        return items

    seen: set[str] = set()

    # Flat command files
    for cmd_file in sorted(COMMANDS_DIR.glob("*.md")):
        if cmd_file.name.startswith("_"):
            continue
        name = cmd_file.stem
        if name in seen:
            continue
        seen.add(name)

        diagram_path = DIAGRAMS_DIR / "commands" / f"{name}.md"
        mandatory = any(name.startswith(prefix) for prefix in MANDATORY_COMMAND_PREFIXES)
        items.append(SourceItem(
            name=name,
            kind="command",
            source_path=cmd_file,
            diagram_path=diagram_path,
            mandatory=mandatory,
        ))

    # Nested command directories (e.g., commands/systematic-debugging/)
    for cmd_dir in sorted(COMMANDS_DIR.iterdir()):
        if not cmd_dir.is_dir() or cmd_dir.name.startswith("_"):
            continue
        main_cmd = cmd_dir / f"{cmd_dir.name}.md"
        if not main_cmd.exists():
            continue
        name = cmd_dir.name
        if name in seen:
            continue
        seen.add(name)

        diagram_path = DIAGRAMS_DIR / "commands" / f"{name}.md"
        mandatory = any(name.startswith(prefix) for prefix in MANDATORY_COMMAND_PREFIXES)
        items.append(SourceItem(
            name=name,
            kind="command",
            source_path=main_cmd,
            diagram_path=diagram_path,
            mandatory=mandatory,
        ))

    return items


def discover_agents() -> list[SourceItem]:
    """Scan agents/ for source files. All agents are mandatory."""
    items: list[SourceItem] = []
    if not AGENTS_DIR.is_dir():
        return items

    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        if agent_file.name.startswith("_"):
            continue
        name = agent_file.stem
        diagram_path = DIAGRAMS_DIR / "agents" / f"{name}.md"
        items.append(SourceItem(
            name=name,
            kind="agent",
            source_path=agent_file,
            diagram_path=diagram_path,
            mandatory=MANDATORY_AGENTS,
        ))

    return items


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def compute_hash(filepath: Path) -> str:
    """Compute SHA256 hex digest of a file's content."""
    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------


def parse_diagram_meta(diagram_path: Path) -> dict:
    """Parse the metadata comment from the first line of a diagram file.

    Expected format:
        <!-- diagram-meta: {"source": "...", "source_hash": "sha256:abc123...", ...} -->

    Returns the parsed dict, or an empty dict if parsing fails.
    """
    try:
        with diagram_path.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()
    except OSError:
        return {}

    prefix = "<!-- diagram-meta: "
    suffix = " -->"
    if not first_line.startswith(prefix) or not first_line.endswith(suffix):
        return {}

    json_str = first_line[len(prefix):-len(suffix)]
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return {}


def extract_stored_hash(meta: dict) -> str:
    """Extract the bare hex hash from the source_hash field.

    The field value is expected as "sha256:<hex>". Returns just the hex portion,
    or empty string if missing/malformed.
    """
    raw = meta.get("source_hash", "")
    if raw.startswith("sha256:"):
        return raw[len("sha256:"):]
    return raw


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def check_item(item: SourceItem) -> CheckResult:
    """Check freshness of a single item's diagram."""
    current_hash = compute_hash(item.source_path)

    if not item.diagram_path.exists():
        return CheckResult(
            item=item,
            status="missing",
            current_hash=current_hash,
            stored_hash="",
        )

    meta = parse_diagram_meta(item.diagram_path)
    stored_hash = extract_stored_hash(meta)

    if current_hash == stored_hash:
        status = "fresh"
    else:
        status = "stale"

    return CheckResult(
        item=item,
        status=status,
        current_hash=current_hash,
        stored_hash=stored_hash,
    )


def check_all(items: list[SourceItem]) -> list[CheckResult]:
    """Check freshness for all discovered items."""
    return [check_item(item) for item in items]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def format_console(results: list[CheckResult], include_optional: bool) -> str:
    """Format results for console display."""
    lines: list[str] = [
        "Diagram Freshness Check",
        "=======================",
        "",
    ]

    fresh_count = 0
    stale_count = 0
    optional_missing_count = 0
    mandatory_stale: list[CheckResult] = []

    for result in results:
        name = result.item.name

        if result.status == "fresh":
            fresh_count += 1
            lines.append(f"\u2713 {name} (fresh)")

        elif result.status == "stale":
            if result.item.mandatory:
                stale_count += 1
                mandatory_stale.append(result)
                lines.append(f"\u2717 {name} (stale - source changed)")
            elif include_optional:
                stale_count += 1
                mandatory_stale.append(result)
                lines.append(f"\u2717 {name} (stale - source changed)")
            else:
                optional_missing_count += 1
                lines.append(f"~ {name} (optional, stale)")

        elif result.status == "missing":
            if result.item.mandatory:
                stale_count += 1
                mandatory_stale.append(result)
                lines.append(f"\u2717 {name} (missing diagram)")
            elif include_optional:
                stale_count += 1
                mandatory_stale.append(result)
                lines.append(f"\u2717 {name} (missing diagram)")
            else:
                optional_missing_count += 1
                lines.append(f"~ {name} (optional, no diagram)")

    lines.append("")
    lines.append(f"Summary: {fresh_count} fresh, {stale_count} stale, {optional_missing_count} optional-missing")

    if mandatory_stale:
        lines.append(f"ERROR: {stale_count} mandatory diagrams are stale. Run: uv run scripts/generate_diagrams.py")

    return "\n".join(lines) + "\n"


def format_json(results: list[CheckResult], include_optional: bool) -> str:
    """Format results as machine-readable JSON."""
    items_out: list[dict] = []
    fresh_count = 0
    stale_count = 0
    optional_missing_count = 0

    for result in results:
        entry = {
            "name": result.item.name,
            "kind": result.item.kind,
            "mandatory": result.item.mandatory,
            "status": result.status,
            "source_path": str(result.item.source_path.relative_to(REPO_ROOT)),
            "diagram_path": str(result.item.diagram_path.relative_to(REPO_ROOT)),
            "current_hash": result.current_hash,
            "stored_hash": result.stored_hash,
        }
        items_out.append(entry)

        if result.status == "fresh":
            fresh_count += 1
        elif result.item.mandatory or include_optional:
            stale_count += 1
        else:
            optional_missing_count += 1

    has_errors = stale_count > 0
    output = {
        "fresh": fresh_count,
        "stale": stale_count,
        "optional_missing": optional_missing_count,
        "has_errors": has_errors,
        "items": items_out,
    }
    return json.dumps(output, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check diagram freshness via content hash comparison",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also fail on stale optional diagrams",
    )
    args = parser.parse_args()

    # Discover all source items
    items = discover_skills() + discover_commands() + discover_agents()

    if not items:
        if args.json:
            print(json.dumps({"fresh": 0, "stale": 0, "optional_missing": 0, "has_errors": False, "items": []}, indent=2))
        else:
            print("No skills or commands found.")
        return 0

    # Check freshness
    results = check_all(items)

    # Output
    if args.json:
        print(format_json(results, args.include_optional), end="")
    else:
        print(format_console(results, args.include_optional), end="")

    # Determine exit code
    for result in results:
        is_error = result.item.mandatory or args.include_optional
        if is_error and result.status in ("stale", "missing"):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
