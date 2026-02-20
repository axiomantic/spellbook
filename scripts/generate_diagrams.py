#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Generate diagrams for skills and commands by invoking Claude Code in headless mode.

Discovers all skills and commands, classifies them into mandatory/optional tiers,
detects staleness via SHA256 hash comparison, and regenerates stale or missing
diagrams using Claude headless with the generating-diagrams skill.

Usage:
    python3 scripts/generate_diagrams.py
    python3 scripts/generate_diagrams.py --dry-run
    python3 scripts/generate_diagrams.py --force
    python3 scripts/generate_diagrams.py --filter "implementing-*"
    python3 scripts/generate_diagrams.py --mandatory-only
    python3 scripts/generate_diagrams.py --verbose
"""

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"
AGENTS_DIR = REPO_ROOT / "agents"
DIAGRAMS_DIR = REPO_ROOT / "docs" / "diagrams"

# ---------------------------------------------------------------------------
# Tiering configuration (mirrors check_diagram_freshness.py)
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

# Timeout for each Claude headless invocation (5 minutes)
CLAUDE_TIMEOUT_SECONDS = 300

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


# All agents are mandatory
MANDATORY_AGENTS: bool = True


class SourceItem(NamedTuple):
    """A discovered source file with its tier classification."""
    name: str
    kind: str          # "skill", "command", or "agent"
    source_path: Path
    diagram_path: Path
    mandatory: bool


class GenerationResult(NamedTuple):
    """Result of a diagram generation attempt."""
    item: SourceItem
    status: str        # "generated", "skipped", "failed", "fresh"
    message: str


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
# Staleness detection
# ---------------------------------------------------------------------------


def is_stale(item: SourceItem) -> tuple[bool, str, str]:
    """Check whether a diagram needs regeneration.

    Returns (needs_regen, current_hash, reason).
    """
    current_hash = compute_hash(item.source_path)

    if not item.diagram_path.exists():
        return True, current_hash, "missing"

    meta = parse_diagram_meta(item.diagram_path)
    stored_hash = extract_stored_hash(meta)

    if current_hash != stored_hash:
        return True, current_hash, "stale"

    return False, current_hash, "fresh"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def apply_filters(
    items: list[SourceItem],
    *,
    mandatory_only: bool = False,
    filter_pattern: str | None = None,
) -> list[SourceItem]:
    """Filter items by mandatory tier and/or glob pattern."""
    filtered = items

    if mandatory_only:
        filtered = [item for item in filtered if item.mandatory]

    if filter_pattern is not None:
        filtered = [item for item in filtered if fnmatch.fnmatch(item.name, filter_pattern)]

    return filtered


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(item: SourceItem) -> str:
    """Build the prompt for Claude headless diagram generation."""
    source_rel = item.source_path.relative_to(REPO_ROOT)
    kind_label = "skill" if item.kind == "skill" else "command"

    return f"""You are generating a diagram for the {kind_label} "{item.name}".

Follow the generating-diagrams skill workflow:

1. **Phase 1 - Analysis**: Read the source file at `{item.source_path}`. Identify the subject type (process/workflow, dependencies, states, etc.), scope the traversal to the file and any commands/skills it references, and select Mermaid as the format (unless node count exceeds ~100, then decompose).

2. **Phase 2 - Content Extraction**: Perform systematic depth-first traversal of the source. Extract all decision points, phase transitions, subagent dispatches, skill/command invocations, quality gates, loop/retry logic, terminal conditions, and conditional branches. Verify completeness: no orphan nodes, all branches represented, no placeholders.

3. **Phase 3 - Diagram Generation**: Generate Mermaid diagram code blocks. For complex multi-phase {kind_label}s, decompose into:
   - An overview diagram showing the high-level phases/flow
   - Detailed diagrams for each major phase
   Include a legend subgraph in each diagram. Use appropriate node shapes (rectangles for processes, diamonds for decisions, stadiums for terminals). Use colors: blue (#4a9eff) for subagent dispatches, red (#ff6b6b) for quality gates, green (#51cf66) for success terminals. Add a cross-reference table mapping overview nodes to detail diagrams if decomposed.

4. **Phase 4 - Verification**: Verify syntax (matched braces, subgraph/end pairs, valid node IDs, correct edge label quoting). Verify every node traces to source material. Verify all decision branches are represented.

Output ONLY the diagram content: Mermaid code blocks with brief descriptions, legends, and cross-reference tables. No preamble, no meta-commentary about the process. The output will be saved directly as a diagram markdown file.

Source file: `{source_rel}`"""


# ---------------------------------------------------------------------------
# Diagram generation
# ---------------------------------------------------------------------------


def generate_diagram(
    item: SourceItem,
    current_hash: str,
    *,
    verbose: bool = False,
) -> GenerationResult:
    """Generate a diagram for a single item via Claude headless.

    Returns a GenerationResult indicating success or failure.
    """
    prompt = build_prompt(item)
    source_rel = str(item.source_path.relative_to(REPO_ROOT))

    cmd = [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        prompt,
    ]

    if verbose:
        print(f"  Command: {' '.join(cmd[:3])} [prompt truncated]")
        print(f"  Stdin: {item.source_path}")

    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SECONDS,
            cwd=REPO_ROOT,
        )
    except subprocess.TimeoutExpired:
        return GenerationResult(
            item=item,
            status="failed",
            message=f"Claude timed out after {CLAUDE_TIMEOUT_SECONDS}s",
        )
    except FileNotFoundError:
        return GenerationResult(
            item=item,
            status="failed",
            message="'claude' command not found. Is Claude Code installed and on PATH?",
        )

    if result.returncode != 0:
        stderr_snippet = result.stderr.strip()[:500] if result.stderr else "(no stderr)"
        return GenerationResult(
            item=item,
            status="failed",
            message=f"Claude exited with code {result.returncode}: {stderr_snippet}",
        )

    diagram_content = result.stdout.strip()
    if not diagram_content:
        return GenerationResult(
            item=item,
            status="failed",
            message="Claude returned empty output",
        )

    # Build the output file with metadata header
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "source": source_rel,
        "source_hash": f"sha256:{current_hash}",
        "generated_at": now,
        "generator": "generate_diagrams.py",
    }
    meta_line = f"<!-- diagram-meta: {json.dumps(meta)} -->"

    output = f"{meta_line}\n# Diagram: {item.name}\n\n{diagram_content}\n"

    # Ensure parent directory exists
    item.diagram_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the diagram file
    item.diagram_path.write_text(output, encoding="utf-8")

    return GenerationResult(
        item=item,
        status="generated",
        message=str(item.diagram_path.relative_to(REPO_ROOT)),
    )


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------


def count_by_tier(items: list[SourceItem]) -> tuple[int, int]:
    """Return (mandatory_count, optional_count)."""
    mandatory = sum(1 for item in items if item.mandatory)
    optional = len(items) - mandatory
    return mandatory, optional


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate diagrams for skills and commands via Claude headless",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without generating",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all diagrams regardless of staleness",
    )
    parser.add_argument(
        "--filter",
        metavar="PATTERN",
        default=None,
        help="Only process items matching glob pattern (e.g., 'implementing-*')",
    )
    parser.add_argument(
        "--mandatory-only",
        action="store_true",
        help="Only process mandatory tier items",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show Claude invocation details",
    )
    args = parser.parse_args()

    # Discover all items
    all_skills = discover_skills()
    all_commands = discover_commands()
    all_agents = discover_agents()

    skills_mandatory, skills_optional = count_by_tier(all_skills)
    cmds_mandatory, cmds_optional = count_by_tier(all_commands)
    agents_mandatory, agents_optional = count_by_tier(all_agents)

    print("Diagram Generation")
    print("==================")
    print()
    print("Scanning sources...")
    print(f"Found {len(all_skills)} skills ({skills_mandatory} mandatory, {skills_optional} optional)")
    print(f"Found {len(all_commands)} commands ({cmds_mandatory} mandatory, {cmds_optional} optional)")
    print(f"Found {len(all_agents)} agents ({agents_mandatory} mandatory, {agents_optional} optional)")

    # Merge and filter
    all_items = all_skills + all_commands + all_agents
    filtered_items = apply_filters(
        all_items,
        mandatory_only=args.mandatory_only,
        filter_pattern=args.filter,
    )

    if args.filter or args.mandatory_only:
        print(f"After filtering: {len(filtered_items)} items")

    # Determine which items need regeneration
    work_items: list[tuple[SourceItem, str]] = []  # (item, current_hash)

    for item in filtered_items:
        if args.force:
            current_hash = compute_hash(item.source_path)
            work_items.append((item, current_hash))
        else:
            stale, current_hash, reason = is_stale(item)
            if stale:
                work_items.append((item, current_hash))

    if not work_items:
        print()
        print("All diagrams are fresh. Nothing to generate.")
        return 0

    print()
    if args.force:
        print(f"Force mode: regenerating all {len(work_items)} diagrams")
    else:
        print(f"Stale/missing diagrams: {len(work_items)}")
    print()

    # Ensure output directories exist
    (DIAGRAMS_DIR / "skills").mkdir(parents=True, exist_ok=True)
    (DIAGRAMS_DIR / "commands").mkdir(parents=True, exist_ok=True)
    (DIAGRAMS_DIR / "agents").mkdir(parents=True, exist_ok=True)

    # Generate diagrams
    if args.dry_run:
        for i, (item, _current_hash) in enumerate(work_items, 1):
            stale, _, reason = is_stale(item)
            tier_label = "mandatory" if item.mandatory else "optional"
            print(f"[{i}/{len(work_items)}] Would generate: {item.name} ({item.kind}, {tier_label}, {reason})")
        print()
        print(f"Dry run complete. {len(work_items)} diagrams would be generated.")
        return 0

    generated_count = 0
    failed_count = 0

    for i, (item, current_hash) in enumerate(work_items, 1):
        print(f"[{i}/{len(work_items)}] Generating: {item.name}...", end="", flush=True)

        result = generate_diagram(item, current_hash, verbose=args.verbose)

        if result.status == "generated":
            generated_count += 1
            print(f" done ({result.message})")
        elif result.status == "failed":
            failed_count += 1
            print(f" FAILED")
            print(f"         Error: {result.message}")
        else:
            print(f" {result.status}: {result.message}")

    print()
    print(f"Done: {generated_count} generated, {failed_count} failed")

    if failed_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
