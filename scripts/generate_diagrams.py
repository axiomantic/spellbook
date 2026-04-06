#!/usr/bin/env python3
"""
Generate diagrams for skills and commands by invoking Claude Code in headless mode.

Discovers all skills and commands, classifies them into mandatory/optional tiers,
detects staleness via SHA256 hash comparison, and regenerates stale or missing
diagrams using Claude headless with the generating-diagrams skill.

By default, only mandatory-tier items are processed. Use --all to include optional items.

Usage:
    python3 scripts/generate_diagrams.py              # mandatory only (default)
    python3 scripts/generate_diagrams.py --all         # include optional tier
    python3 scripts/generate_diagrams.py --interactive  # review each diff before accepting
    python3 scripts/generate_diagrams.py --dry-run
    python3 scripts/generate_diagrams.py --force
    python3 scripts/generate_diagrams.py --filter "implementing-*"
    python3 scripts/generate_diagrams.py --verbose
"""

import asyncio
import argparse
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from spellbook.sdk.unified import get_agent_client, AgentOptions, AgentMessage

from diagram_config import (
    AGENTS_DIR,
    COMMANDS_DIR,
    DIAGRAMS_DIR,
    EXCLUDED_AGENTS,
    EXCLUDED_COMMANDS,
    EXCLUDED_SKILLS,
    MANDATORY_AGENTS,
    MANDATORY_COMMAND_PREFIXES,
    MANDATORY_SKILLS,
    REPO_ROOT,
    SKILLS_DIR,
    compute_structure_hash,
)

# No timeouts on LLM invocations -- let them run to completion
# (Classification and patching timeouts are also unused since those use the SDK now)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SourceItem:
    """A discovered source file with its tier classification."""
    name: str
    kind: str          # "skill", "command", or "agent"
    source_path: Path
    diagram_path: Path
    mandatory: bool


@dataclass
class GenerationResult:
    """Result of a diagram generation attempt."""
    item: SourceItem
    status: str        # "generated", "skipped", "failed", "fresh"
    message: str = ""


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
        if name in EXCLUDED_SKILLS:
            continue
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
        if name in EXCLUDED_COMMANDS:
            continue
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
        if name in EXCLUDED_COMMANDS:
            continue
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
        if name in EXCLUDED_AGENTS:
            continue
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
    """Compute SHA256 hex digest of a file's heading structure.

    Only markdown headings (after stripping YAML frontmatter) contribute
    to the hash, so cosmetic edits like wording tweaks or frontmatter
    changes do not trigger unnecessary diagram regeneration.
    """
    return compute_structure_hash(filepath)


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
    kind_label = item.kind  # "skill", "command", or "agent"

    return f"""You are generating a diagram for the {kind_label} "{item.name}".

Follow the generating-diagrams skill workflow:

1. **Phase 1 - Analysis**: Read the source file at `{source_rel}`. Identify the subject type (process/workflow, dependencies, states, etc.), scope the traversal to the file and any commands/skills it references, and select Mermaid as the format (unless node count exceeds ~100, then decompose).

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
    provider: str = "claude",
    model: str = "sonnet",
    provider_args: list[str] | None = None,
    verbose: bool = False,
    write: bool = True,
) -> tuple[GenerationResult, str | None]:
    """Generate a diagram for a single item via an LLM provider.

    Args:
        provider: "claude" or "gemini"
        model: model name to pass to the provider
        provider_args: extra arguments for the provider CLI
        write: If True, write the diagram file. If False, return the content
               without writing (for interactive mode).

    Returns (GenerationResult, output_content). output_content is the full
    file content when generation succeeds, None otherwise.
    """
    prompt = build_prompt(item)
    source_rel = str(item.source_path.relative_to(REPO_ROOT))

    if provider == "claude":
        cmd = [
            "claude",
            "--print",
            "--model", model,
            "--dangerously-skip-permissions",
        ]
        if provider_args:
            cmd.extend(provider_args)
        cmd.append(prompt)
    elif provider == "gemini":
        cmd = [
            "gemini",
            "--prompt", prompt,
            "--model", model,
            "--yolo",
            "-o", "text",
        ]
        if provider_args:
            cmd.extend(provider_args)
    else:
        return GenerationResult(
            item=item,
            status="failed",
            message=f"Unknown provider: {provider}",
        ), None

    if verbose:
        print(f"  Command: {' '.join(cmd[:4])} [prompt truncated]")
        print(f"  Stdin: {item.source_path}")

    # Unset CLAUDECODE and GEMINI_CLI to allow spawning subprocesses from within
    # an active session (e.g., when run via pre-commit hooks).
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "GEMINI_CLI")}

    print(f"  Generating diagram for {item.source_path.name} via {provider} ({model})...", end="", flush=True)

    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=None,  # inherit parent stderr so errors are visible
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )
    except FileNotFoundError:
        print(" failed")
        return GenerationResult(
            item=item,
            status="failed",
            message=f"'{cmd[0]}' command not found. Is it installed and on PATH?",
        ), None

    if result.returncode != 0:
        print(" failed")
        return GenerationResult(
            item=item,
            status="failed",
            message=f"{cmd[0]} exited with code {result.returncode} (stderr was printed above)",
        ), None

    diagram_content = result.stdout.strip()

    # Check if Claude wrote to a DIAGRAM.md file instead of stdout.
    # Common locations: source directory, repo root, or diagrams dir.
    diagram_file_candidates = [
        item.source_path.parent / "DIAGRAM.md",
        REPO_ROOT / "DIAGRAM.md",
        item.diagram_path.parent / f"{item.name}-DIAGRAM.md",
    ]
    for candidate in diagram_file_candidates:
        if candidate.exists():
            file_content = candidate.read_text(encoding="utf-8").strip()
            if file_content:
                if verbose:
                    print(f"  Found LLM-written file: {candidate}")
                if not diagram_content or "mermaid" not in diagram_content:
                    diagram_content = file_content
                candidate.unlink()
            else:
                candidate.unlink()

    if not diagram_content:
        print(" failed")
        return GenerationResult(
            item=item,
            status="failed",
            message="Claude returned empty output",
        ), None

    # Accept both fenced (```mermaid) and raw mermaid output.
    # Raw mermaid starts with a diagram type keyword (graph, flowchart,
    # sequenceDiagram, stateDiagram, classDiagram, erDiagram, gantt, pie,
    # journey, gitGraph, mindmap, timeline, etc.)
    has_fenced = "```mermaid" in diagram_content
    mermaid_keywords = (
        "graph ", "graph\n", "flowchart ", "flowchart\n",
        "sequenceDiagram", "stateDiagram", "classDiagram",
        "erDiagram", "gantt", "pie", "journey", "gitGraph",
        "mindmap", "timeline", "sankey", "xychart", "block-beta",
    )
    has_raw = any(diagram_content.lstrip().startswith(kw) for kw in mermaid_keywords)

    if not has_fenced and not has_raw:
        print(" failed")
        return GenerationResult(
            item=item,
            status="failed",
            message="Claude output does not contain mermaid content",
        ), None

    # Wrap raw mermaid in a fenced code block if needed
    if has_raw and not has_fenced:
        diagram_content = f"```mermaid\n{diagram_content}\n```"

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

    if write:
        # Ensure parent directory exists
        item.diagram_path.parent.mkdir(parents=True, exist_ok=True)
        item.diagram_path.write_text(output, encoding="utf-8")

    print(" done")
    return GenerationResult(
        item=item,
        status="generated",
        message=str(item.diagram_path.relative_to(REPO_ROOT)),
    ), output


# ---------------------------------------------------------------------------
# Stamp existing diagram as fresh (update hash without changing content)
# ---------------------------------------------------------------------------


def stamp_as_fresh(item: SourceItem, current_hash: str) -> None:
    """Update the source_hash in an existing diagram's metadata without changing content.

    This marks the diagram as "reviewed and accepted" for the current source,
    so it won't show as stale in future runs.
    """
    if not item.diagram_path.exists():
        return

    content = item.diagram_path.read_text(encoding="utf-8")
    lines = content.split("\n", 1)

    prefix = "<!-- diagram-meta: "
    suffix = " -->"
    if lines[0].startswith(prefix) and lines[0].rstrip().endswith(suffix):
        meta = parse_diagram_meta(item.diagram_path)
        meta["source_hash"] = f"sha256:{current_hash}"
        meta["stamped_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_meta_line = f"{prefix}{json.dumps(meta)}{suffix}"
        rest = lines[1] if len(lines) > 1 else ""
        item.diagram_path.write_text(f"{new_meta_line}\n{rest}", encoding="utf-8")


# ---------------------------------------------------------------------------
# Smart update: diff retrieval, classification, and patching
# ---------------------------------------------------------------------------

# Classification and patching now use the Unified SDK (no subprocess timeouts needed)

CLASSIFICATION_PROMPT = """\
You are classifying whether a source file change affects its workflow diagram.

Given this diff of a skill/command/agent instruction file, classify the change:

STAMP - The change does NOT affect the workflow diagram. Examples:
  - Adding/modifying XML tags that aren't workflow steps (e.g., <BEHAVIORAL_MODE>, <ROLE>, <CRITICAL>)
  - Changing prose, descriptions, or explanations within existing steps
  - Fixing typos, rewording instructions
  - Adding/removing FORBIDDEN or REQUIRED items
  - Changing code examples within steps
  - Adding/modifying metadata or comments

PATCH - The change makes SMALL structural modifications to the workflow. Examples:
  - Adding or removing a single step within an existing phase
  - Renaming a phase or step
  - Adding a new quality gate
  - Reordering 1-2 steps

REGENERATE - The change fundamentally restructures the workflow. Examples:
  - Adding or removing entire phases
  - Major reorganization of step ordering
  - Changing the flow/branching logic
  - Adding new parallel tracks or decision points

Respond with ONLY one word: STAMP, PATCH, or REGENERATE

DIFF:
{diff}"""

PATCH_PROMPT = """\
You are surgically patching an existing Mermaid workflow diagram to reflect a small structural change.

RULES:
- Make ONLY the minimum edits needed to reflect the diff
- Preserve all existing node IDs, styles, and formatting where possible
- Do NOT reorganize or restructure unchanged parts of the diagram
- Output ONLY the updated diagram content (Mermaid code blocks with descriptions)
- If you cannot make a surgical patch, output exactly: CANNOT_PATCH

EXISTING DIAGRAM:
{existing_diagram}

SOURCE DIFF:
{diff}

Output the patched diagram content:"""


def get_source_diff(source_path: Path) -> str:
    """Get the git diff for a source file.

    Tries git diff HEAD first (uncommitted changes). If empty, falls back to
    git diff HEAD~1 (most recent commit's changes).

    Returns the diff text, or empty string if no diff is available.
    """
    source_rel = str(source_path.relative_to(REPO_ROOT))

    # Try uncommitted changes first
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", source_rel],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except OSError:
        return ""

    # Fall back to last commit's changes
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--", source_rel],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except OSError:
        pass

    return ""


async def classify_change(
    source_path: Path,
    diagram_path: Path,
    *,
    provider: str = "claude",
    model: str = "haiku",
    provider_args: list[str] | None = None,
) -> str:
    """Classify a source file change via Unified SDK."""
    diff = get_source_diff(source_path)
    if not diff:
        return "REGENERATE"

    prompt = CLASSIFICATION_PROMPT.format(diff=diff)
    
    options = AgentOptions(
        cwd=REPO_ROOT,
        model=model,
        extra_args=provider_args or []
    )
    client = get_agent_client(provider, options)

    print(f"  Classifying change for {source_path.name} via {provider} ({model})...", end="", flush=True)

    try:
        classification = await client.run(prompt)
        classification = classification.strip().upper()
    except Exception as e:
        print(f"  -> REGENERATE ({type(e).__name__}: {e})")
        return "REGENERATE"

    if classification in ("STAMP", "PATCH", "REGENERATE"):
        print(f" {classification}")
        return classification

    print(" REGENERATE")
    return "REGENERATE"


async def patch_diagram(
    source_path: Path,
    diagram_path: Path,
    diff: str,
    *,
    provider: str = "claude",
    model: str = "haiku",
    provider_args: list[str] | None = None,
) -> str | None:
    """Surgically patch an existing diagram via Unified SDK."""
    if not diagram_path.exists():
        return None

    existing_diagram = diagram_path.read_text(encoding="utf-8")
    prompt = PATCH_PROMPT.format(existing_diagram=existing_diagram, diff=diff)
    
    options = AgentOptions(
        cwd=REPO_ROOT,
        model=model,
        extra_args=provider_args or []
    )
    client = get_agent_client(provider, options)

    print(f"  Patching diagram for {source_path.name} via {provider} ({model})...", end="", flush=True)

    try:
        output = await client.run(prompt)
        output = output.strip()
    except Exception as e:
        print(f" failed ({type(e).__name__}: {e}), falling back to regeneration")
        return None

    if not output or output == "CANNOT_PATCH":
        print(" failed, falling back to regeneration")
        return None

    print(" done")
    return output


# ---------------------------------------------------------------------------
# Source change display (pre-generation)
# ---------------------------------------------------------------------------


def _is_tracked_by_git(source_rel: Union[str, Path]) -> bool:
    """Check whether a file is tracked by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(source_rel)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        return result.returncode == 0
    except OSError:
        return False


def _strip_diff_headers(lines: list[str]) -> list[str]:
    """Strip git diff header lines (diff --git, index, ---/+++ lines)."""
    content_lines = []
    for line in lines:
        stripped = line.lstrip("\x1b[0123456789;m")
        if stripped.startswith(("diff --git", "index ", "--- ", "+++ ")):
            continue
        content_lines.append(line)
    return content_lines


def _print_diff_lines(lines: list[str], max_lines: int = 100) -> bool:
    """Print diff lines with indentation. Returns True if any lines were printed."""
    for line in lines[:max_lines]:
        print(f"  {line}")
    if len(lines) > max_lines:
        print(f"  ... ({len(lines) - max_lines} more lines)")
    return bool(lines)


def show_source_changes(item: SourceItem) -> None:
    """Show a single combined diff of source changes since the diagram was last generated."""
    import shutil

    term_width = shutil.get_terminal_size().columns
    source_rel = item.source_path.relative_to(REPO_ROOT)

    print("-" * min(term_width, 80))
    print(f"  Source changes: {source_rel}")
    print("-" * min(term_width, 80))

    # Check if the source file is tracked by git at all
    if not _is_tracked_by_git(source_rel):
        print("  (new file, not yet tracked by git)")
        print()
        # Show first 60 lines of the file content as a preview
        try:
            content = item.source_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line in lines[:60]:
                print(f"  + {line}")
            if len(lines) > 60:
                print(f"  ... ({len(lines) - 60} more lines)")
        except OSError:
            print("  (could not read file)")
        print()
        return

    # Find the commit where the diagram was last generated/stamped
    base_commit = None
    if item.diagram_path.exists():
        meta = parse_diagram_meta(item.diagram_path)
        generated_at = meta.get("generated_at") or meta.get("stamped_at")
        if generated_at:
            # Find the oldest commit after the diagram timestamp
            try:
                result = subprocess.run(
                    ["git", "log", "--format=%H", "--after=" + generated_at,
                     "--reverse", "--", str(source_rel)],
                    capture_output=True, text=True, cwd=REPO_ROOT,
                )
                commits = result.stdout.strip().splitlines()
                if commits:
                    # Verify the parent commit exists (first commit has no parent)
                    parent_check = subprocess.run(
                        ["git", "rev-parse", "--verify", commits[0] + "~1"],
                        capture_output=True, text=True, cwd=REPO_ROOT,
                    )
                    if parent_check.returncode == 0:
                        base_commit = commits[0] + "~1"
                    else:
                        # First commit in repo; diff against empty tree
                        base_commit = "4b825dc642cb6eb9a060e54bf899d15f7fb7c488"
            except OSError:
                pass

    shown = False

    # Strategy 1: Combined diff from base_commit to working tree (includes uncommitted)
    if base_commit:
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--color=always", "--no-ext-diff",
                 base_commit, "--", str(source_rel)],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            if diff_result.stdout.strip():
                content_lines = _strip_diff_headers(diff_result.stdout.splitlines())
                shown = _print_diff_lines(content_lines)
        except OSError:
            pass

    # Strategy 2: Uncommitted changes (staged + unstaged)
    if not shown:
        try:
            staged = subprocess.run(
                ["git", "diff", "--cached", "--color=always", "--no-ext-diff",
                 "--", str(source_rel)],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            unstaged = subprocess.run(
                ["git", "diff", "--color=always", "--no-ext-diff",
                 "--", str(source_rel)],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            combined = (staged.stdout.strip() + "\n" + unstaged.stdout.strip()).strip()
            if combined:
                content_lines = _strip_diff_headers(combined.splitlines())
                shown = _print_diff_lines(content_lines)
        except OSError:
            pass

    # Strategy 3: Diff across recent history (widen the search)
    if not shown:
        # The source hash changed but we couldn't find a diff above. This typically
        # means the change was committed and we failed to locate the base commit.
        # Walk back through history to find where the file last matched.
        for depth in ("HEAD~5", "HEAD~10", "HEAD~25"):
            try:
                diff_result = subprocess.run(
                    ["git", "diff", "--color=always", "--no-ext-diff",
                     depth, "HEAD", "--", str(source_rel)],
                    capture_output=True, text=True, cwd=REPO_ROOT,
                )
                if diff_result.stdout.strip():
                    content_lines = _strip_diff_headers(diff_result.stdout.splitlines())
                    shown = _print_diff_lines(content_lines)
                    break
            except OSError:
                break

    # Strategy 4: Show the full file diff against empty tree (file exists but
    # all git diff strategies failed, e.g., very old change or unusual history)
    if not shown:
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--color=always", "--no-ext-diff",
                 "4b825dc642cb6eb9a060e54bf899d15f7fb7c488",
                 "HEAD", "--", str(source_rel)],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            if diff_result.stdout.strip():
                content_lines = _strip_diff_headers(diff_result.stdout.splitlines())
                print("  (showing full file content; could not isolate specific changes)")
                shown = _print_diff_lines(content_lines)
        except OSError:
            pass

    if not shown:
        print("  (no diff available - git may not be accessible)")

    print()


# ---------------------------------------------------------------------------
# Interactive diff display (post-generation)
# ---------------------------------------------------------------------------


def show_diff_and_prompt(item: SourceItem, new_content: str) -> bool:
    """Show a diff between existing and new diagram content, prompt user.

    Returns True to accept the new content, False to skip (stamp as fresh).
    For missing diagrams, shows the new content directly.
    """
    import difflib
    import shutil

    term_width = shutil.get_terminal_size().columns

    print()
    print("=" * min(term_width, 80))
    print(f"  {item.kind}: {item.name}")
    print("=" * min(term_width, 80))

    if item.diagram_path.exists():
        old_lines = item.diagram_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"existing/{item.name}.md",
            tofile=f"generated/{item.name}.md",
        )
        diff_text = "".join(diff)
        if diff_text:
            print(diff_text)
        else:
            print("  (no differences)")
    else:
        # New diagram, show first 60 lines
        preview_lines = new_content.splitlines()
        shown = preview_lines[:60]
        for line in shown:
            print(f"+ {line}")
        if len(preview_lines) > 60:
            print(f"  ... ({len(preview_lines) - 60} more lines)")

    print()
    while True:
        answer = input("  Accept new diagram? [y]es / [s]kip (mark as reviewed): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("s", "skip"):
            return False
        print("  Please enter 'y' or 's'.")


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


async def main_async() -> int:
    parser = argparse.ArgumentParser(
        description="Generate diagrams for skills and commands via LLM (Claude or Gemini)",
    )
    parser.add_argument(
        "--provider",
        choices=["claude", "gemini"],
        default="claude",
        help="LLM provider to use (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name to pass to the provider (default: 'sonnet' for claude, 'gemini-2.5-flash' for gemini)",
    )
    parser.add_argument(
        "--provider-args",
        nargs="*",
        help="Additional arguments to pass to the provider CLI",
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
        "--all",
        action="store_true",
        help="Process all items including optional tier (default: mandatory only)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Show diff for each generated diagram and prompt to accept or skip",
    )
    parser.add_argument(
        "--force-regen",
        action="store_true",
        help="Force full regeneration, bypassing smart classification",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show Claude invocation details",
    )
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="Stamp stale diagrams as fresh without regenerating (just update hash)",
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

    # Set default model based on provider
    provider = args.provider
    model = args.model
    if model is None:
        if provider == "claude":
            model = "sonnet"
        elif provider == "gemini":
            model = "gemini-2.5-flash"
    
    # Fast model for utility tasks (classification, patching)
    # Use the specified model if provided, otherwise default to a fast one
    fast_model = args.model
    if fast_model is None:
        if provider == "claude":
            fast_model = "haiku"
        elif provider == "gemini":
            fast_model = "gemini-2.5-flash"

    # Merge and filter
    all_items = all_skills + all_commands + all_agents
    filtered_items = apply_filters(
        all_items,
        mandatory_only=not args.all,
        filter_pattern=args.filter,
    )

    if args.filter or not args.all:
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

    # --stamp: just update hashes, no Claude calls, no generation
    if args.stamp:
        print()
        print(f"Stamping {len(work_items)} stale diagrams as fresh...")
        for item, current_hash in work_items:
            stamp_as_fresh(item, current_hash)
            print(f"  Stamped: {item.name}")
        print(f"Done: {len(work_items)} stamped")
        return 0

    print()
    if args.force:
        print(f"Force mode: regenerating all {len(work_items)} diagrams via {provider} ({model})")
    else:
        print(f"Stale/missing diagrams: {len(work_items)} (using {provider})")
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

    # Determine whether to use smart classification
    use_smart = not args.force and not args.force_regen

    # ----- Interactive triage: collect decisions upfront, then batch -----
    if args.interactive:
        to_generate: list[tuple[SourceItem, str]] = []
        to_patch: list[tuple[SourceItem, str, str]] = []  # (item, hash, diff)
        stamped: list[tuple[SourceItem, str]] = []
        skipped: list[tuple[SourceItem, str]] = []

        for i, (item, current_hash) in enumerate(work_items, 1):
            reason = is_stale(item)[2]
            print(f"\n[{i}/{len(work_items)}] {item.name} ({item.kind}, {reason})")
            show_source_changes(item)

            # Smart classification for interactive mode
            if use_smart and item.diagram_path.exists():
                classification = await classify_change(
                    item.source_path, item.diagram_path,
                    provider=provider, model=fast_model,
                    provider_args=args.provider_args,
                )
                print(f"  Smart classification: {classification}")

                if classification == "STAMP":
                    while True:
                        answer = input("  [S]tamp (enter) / [g]enerate / [q]uit: ").strip().lower()
                        if answer in ("s", "stamp", ""):
                            stamped.append((item, current_hash))
                            print(f"  -> Stamped as fresh (non-structural change)")
                            break
                        if answer in ("g", "generate"):
                            to_generate.append((item, current_hash))
                            break
                        if answer in ("q", "quit"):
                            print(f"\nAborted. No changes made.")
                            return 0
                        print("  Please enter 's', 'g', or 'q'.")
                elif classification == "PATCH":
                    while True:
                        answer = input("  [P]atch (enter) / [g]enerate / [q]uit: ").strip().lower()
                        if answer in ("p", "patch", ""):
                            diff = get_source_diff(item.source_path)
                            to_patch.append((item, current_hash, diff))
                            break
                        if answer in ("g", "generate"):
                            to_generate.append((item, current_hash))
                            break
                        if answer in ("q", "quit"):
                            print(f"\nAborted. No changes made.")
                            return 0
                        print("  Please enter 'p', 'g', or 'q'.")
                else:  # REGENERATE
                    while True:
                        answer = input("  [G]enerate (enter) / [s]kip / [q]uit: ").strip().lower()
                        if answer in ("g", "generate", ""):
                            to_generate.append((item, current_hash))
                            break
                        if answer in ("s", "skip"):
                            skipped.append((item, current_hash))
                            print(f"  -> Will skip (stamp on completion)")
                            break
                        if answer in ("q", "quit"):
                            print(f"\nAborted. No changes made.")
                            return 0
                        print("  Please enter 'g', 's', or 'q'.")
            else:
                # No smart classification (force, force-regen, or missing diagram)
                while True:
                    answer = input("  Generate this diagram? [y]es / [s]kip / [q]uit: ").strip().lower()
                    if answer in ("y", "yes"):
                        to_generate.append((item, current_hash))
                        break
                    if answer in ("s", "skip"):
                        skipped.append((item, current_hash))
                        print(f"  -> Will skip (stamp on completion)")
                        break
                    if answer in ("q", "quit"):
                        print(f"\nAborted. No changes made.")
                        return 0
                    print("  Please enter 'y', 's', or 'q'.")

        if not to_generate and not to_patch:
            # Apply stamps and skips
            for item, current_hash in stamped:
                stamp_as_fresh(item, current_hash)
            for item, current_hash in skipped:
                stamp_as_fresh(item, current_hash)
            total = len(stamped) + len(skipped)
            print(f"\nNothing to generate. {total} stamped/skipped.")
            return 0

        total_work = len(to_generate) + len(to_patch)
        print(f"\n{'=' * 60}")
        print(f"  Processing {total_work} diagrams (batch mode, using {provider})")
        print(f"{'=' * 60}\n")

        generated_count = 0
        patched_count = 0
        failed_count = 0

        # Process patches first
        for item, current_hash, diff in to_patch:
            patched_content = await patch_diagram(
                item.source_path, item.diagram_path, diff,
                provider=provider, model=fast_model,
                provider_args=args.provider_args,
            )
            if patched_content is not None:
                # Build output with metadata header
                source_rel = str(item.source_path.relative_to(REPO_ROOT))
                now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                meta = {
                    "source": source_rel,
                    "source_hash": f"sha256:{current_hash}",
                    "generated_at": now,
                    "generator": "generate_diagrams.py",
                    "method": "patch",
                    "provider": provider,
                    "model": fast_model,
                }
                meta_line = f"<!-- diagram-meta: {json.dumps(meta)} -->"
                output = f"{meta_line}\n# Diagram: {item.name}\n\n{patched_content}\n"
                item.diagram_path.parent.mkdir(parents=True, exist_ok=True)
                item.diagram_path.write_text(output, encoding="utf-8")
                patched_count += 1
                print(f"  {item.name}: done (patched)")
            else:
                # Fall back to full generation
                print(f"  {item.name}: patch failed, regenerating...", end="", flush=True)
                result, output_content = await asyncio.to_thread(
                    generate_diagram,
                    item, current_hash,
                    provider=provider, model=model,
                    provider_args=args.provider_args,
                    verbose=args.verbose, write=False,
                )
                if result.status == "generated" and output_content is not None:
                    item.diagram_path.parent.mkdir(parents=True, exist_ok=True)
                    item.diagram_path.write_text(output_content, encoding="utf-8")
                    generated_count += 1
                    print(f" done (regenerated)")
                else:
                    failed_count += 1
                    print(f" FAILED: {result.message}")

        # Process full generations
        for i, (item, current_hash) in enumerate(to_generate, 1):
            result, output_content = await asyncio.to_thread(
                generate_diagram,
                item, current_hash,
                provider=provider, model=model,
                provider_args=args.provider_args,
                verbose=args.verbose, write=False,
            )
            if result.status == "generated" and output_content is not None:
                item.diagram_path.parent.mkdir(parents=True, exist_ok=True)
                item.diagram_path.write_text(output_content, encoding="utf-8")
                generated_count += 1
                print(f" done ({result.message})")
            elif result.status == "failed":
                failed_count += 1
                print(f" FAILED")
                print(f"         Error: {result.message}")
            else:
                print(f" {result.status}: {result.message}")

        # Apply stamps and skips
        for item, current_hash in stamped:
            stamp_as_fresh(item, current_hash)
        for item, current_hash in skipped:
            stamp_as_fresh(item, current_hash)

        print()
        parts = []
        if generated_count:
            parts.append(f"{generated_count} generated")
        if patched_count:
            parts.append(f"{patched_count} patched")
        if stamped:
            parts.append(f"{len(stamped)} stamped")
        if skipped:
            parts.append(f"{len(skipped)} skipped")
        if failed_count:
            parts.append(f"{failed_count} failed")
        print(f"Done: {', '.join(parts)}")

        if failed_count > 0:
            return 1
        return 0

    # ----- Non-interactive: smart classification or direct generation -----
    generated_count = 0
    patched_count = 0
    stamped_count = 0
    failed_count = 0

    for i, (item, current_hash) in enumerate(work_items, 1):
        # Smart classification (if enabled and diagram exists)
        if use_smart and item.diagram_path.exists():
            classification = await classify_change(
                item.source_path, item.diagram_path,
                provider=provider, model=fast_model,
                provider_args=args.provider_args,
            )

            if classification == "STAMP":
                stamp_as_fresh(item, current_hash)
                stamped_count += 1
                print(f"[{i}/{len(work_items)}] Stamped as fresh: {item.name} (non-structural change)")
                continue

            if classification == "PATCH":
                diff = get_source_diff(item.source_path)
                patched_content = await patch_diagram(
                    item.source_path, item.diagram_path, diff,
                    provider=provider, model=fast_model,
                    provider_args=args.provider_args,
                )
                if patched_content is not None:
                    source_rel = str(item.source_path.relative_to(REPO_ROOT))
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    meta = {
                        "source": source_rel,
                        "source_hash": f"sha256:{current_hash}",
                        "generated_at": now,
                        "generator": "generate_diagrams.py",
                        "method": "patch",
                        "provider": provider,
                        "model": fast_model,
                    }
                    meta_line = f"<!-- diagram-meta: {json.dumps(meta)} -->"
                    output = f"{meta_line}\n# Diagram: {item.name}\n\n{patched_content}\n"
                    item.diagram_path.parent.mkdir(parents=True, exist_ok=True)
                    item.diagram_path.write_text(output, encoding="utf-8")
                    patched_count += 1
                    print(f"[{i}/{len(work_items)}] Patched diagram: {item.name} (surgical update)")
                    continue
                else:
                    # Fall through to full generation below
                    pass

            # classification == "REGENERATE" or patch failed: fall through

        result, output_content = await asyncio.to_thread(
            generate_diagram,
            item, current_hash,
            provider=provider,
            model=model,
            provider_args=args.provider_args,
            verbose=args.verbose,
            write=True,
        )

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
    parts = []
    if generated_count:
        parts.append(f"{generated_count} generated")
    if patched_count:
        parts.append(f"{patched_count} patched")
    if stamped_count:
        parts.append(f"{stamped_count} stamped")
    if failed_count:
        parts.append(f"{failed_count} failed")
    if not parts:
        parts.append("0 generated")
    print(f"Done: {', '.join(parts)}")

    if failed_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
