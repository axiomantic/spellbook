"""4-phase sync pipeline for the file-based memory system.

Client-driven architecture: the pipeline PREPARES context, the calling
LLM EXECUTES fact-checking and discovery. No server-side LLM calls.

Phases:
  1. Diff-to-Citation Mapping (no LLM)
  2. Fact-Check Context Preparation (no LLM -- prepares context FOR LLM)
  3. Discovery Context Preparation (no LLM -- prepares context FOR LLM)
  4. Quality Gate (heuristic -- no LLM needed for basic checks)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import date

from spellbook.memory.diff_symbols import SymbolChange
from spellbook.memory.filestore import read_memory, store_memory
from spellbook.memory.frontmatter import parse_frontmatter, write_memory_file
from spellbook.memory.models import Citation, MemoryFile
from spellbook.memory.search_serena import AtRiskMemory, find_at_risk_memories
from spellbook.memory.utils import content_hash as _content_hash, iter_memory_files

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FactCheckItem:
    """A single memory to fact-check, with all context the LLM needs."""

    memory_path: str
    memory_content: str
    citations: list[Citation]
    relevant_diff: str
    current_code_snippet: str
    prompt: str


@dataclass
class SyncPhase1Result:
    """Output of Phase 1: at-risk memories identified."""

    at_risk_memories: list[AtRiskMemory]
    changed_files: list[str]
    changed_symbols: list[SymbolChange]
    stats: dict


@dataclass
class SyncPhase2Result:
    """Output of Phase 2: fact-check context assembled."""

    factcheck_items: list[FactCheckItem]
    total_at_risk: int


@dataclass
class SyncPhase3Result:
    """Output of Phase 3: discovery context for the LLM."""

    discovery_context: str
    diff_summary: str
    new_symbols: list[SymbolChange]
    removed_symbols: list[SymbolChange]
    memory_type_guidance: str


@dataclass
class SyncPhase4Result:
    """Output of Phase 4: quality gate verdicts."""

    accepted: list[dict]
    rejected: list[dict]


@dataclass
class SyncPlan:
    """Complete plan returned by memory_sync for the calling LLM."""

    factcheck_items: list[FactCheckItem]
    discovery_context: SyncPhase3Result
    prompt_template: str
    phase4_instructions: str
    stats: dict


@dataclass
class SyncReport:
    """Summary of apply_sync_results execution."""

    memories_updated: int = 0
    memories_archived: int = 0
    memories_unchanged: int = 0
    memories_created: int = 0
    memories_rejected: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_code_snippet(project_root: str, file_path: str) -> str:
    """Read source file content, returning empty string if missing."""
    full_path = os.path.join(project_root, file_path)
    if not os.path.exists(full_path):
        return ""
    with open(full_path, "r") as f:
        return f.read()


def _scan_existing_hashes(memory_dir: str) -> set[str]:
    """Collect all content hashes from existing memory files."""
    hashes: set[str] = set()
    for md_path in iter_memory_files(memory_dir):
        try:
            fm, _ = parse_frontmatter(md_path)
            if fm.content_hash:
                hashes.add(fm.content_hash)
        except (ValueError, OSError):
            continue
    return hashes


_FACTCHECK_ITEM_PROMPT = """\
## Memory: {memory_path}

**Content:**
{memory_content}

**Citations:**
{citations_text}

**Relevant diff:**
```
{relevant_diff}
```

**Current code state:**
```
{current_code}
```

Determine the verdict: STILL_TRUE | NEEDS_UPDATE | NOW_FALSE | UNCERTAIN
If NEEDS_UPDATE, provide the updated content."""


_PROMPT_TEMPLATE = """\
## Memory Sync: Fact-Check Phase

For each memory below, determine if it is still accurate given the code changes.

Respond with a JSON object:
{{
  "verdicts": [
    {{
      "memory_path": "path/to/memory.md",
      "verdict": "STILL_TRUE" | "NEEDS_UPDATE" | "NOW_FALSE" | "UNCERTAIN",
      "updated_content": "..." // only if NEEDS_UPDATE
      "reason": "..." // brief explanation
    }}
  ],
  "new_memories": [
    {{
      "content": "...",
      "type": "project|user|feedback|reference",
      "kind": "fact|rule|convention|preference|decision|antipattern",
      "citations": [{{"file": "...", "symbol": "...", "symbol_type": "..."}}],
      "tags": ["..."]
    }}
  ]
}}

### Memories to Fact-Check

{factcheck_section}

### Discovery Context

{discovery_section}

### Guidelines
- STILL_TRUE: Memory is accurate, no changes needed
- NEEDS_UPDATE: Memory is partially accurate, provide updated content
- NOW_FALSE: Memory is no longer true, will be archived
- UNCERTAIN: Cannot determine, will be flagged for manual review
- For new memories: only create for non-obvious decisions, not derivable facts"""


_MEMORY_TYPE_GUIDANCE = """\
Memory Types:
- project: Facts about the codebase, architecture, APIs
- user: Information about the developer's preferences and expertise
- feedback: Corrections, workflow preferences, behavioral feedback
- reference: External references, links, third-party documentation

Memory Kinds:
- fact: A verifiable statement about the codebase
- rule: A constraint or requirement that must be followed
- convention: A coding style or process convention the team follows
- preference: A user preference for how things should be done
- decision: A design decision with rationale
- antipattern: Something to avoid, with explanation of why

What NOT to store:
- Derivable facts (function signatures, file paths alone)
- Ephemeral state (currently debugging X, current branch name)
- Information that changes every commit (line numbers, exact counts)"""


_PHASE4_INSTRUCTIONS = """\
After the LLM produces verdicts and new_memories, call:
  apply_sync_results(results=llm_response, memory_dir=memory_dir, project_root=project_root)

This will:
1. Process verdicts (update/archive/keep memories)
2. Run phase4_quality_gate on new_memories
3. Write accepted new memories to disk
4. Return a SyncReport summary"""


# ---------------------------------------------------------------------------
# Phase 1: Diff-to-Citation Mapping
# ---------------------------------------------------------------------------


def phase1_find_at_risk(
    project_root: str,
    memory_dir: str,
    changed_files: list[str],
    symbol_changes: list[SymbolChange] | None = None,
) -> SyncPhase1Result:
    """Find memories at risk due to code changes.

    Scans memory frontmatter for citations matching changed files.

    Args:
        project_root: Root directory of the git repository.
        memory_dir: Root memory directory.
        changed_files: List of changed file paths relative to project root.
        symbol_changes: Symbol-level changes from diff_symbols (best-effort).

    Returns:
        SyncPhase1Result with at-risk memories and stats.
    """
    if symbol_changes is None:
        symbol_changes = []

    # Build SymbolChange entries for changed files so find_at_risk_memories
    # sees the full set of changed files (symbol-level changes are folded in).
    file_only_changes: list[SymbolChange] = [
        SymbolChange(
            file=f,
            symbol_name="",
            symbol_type="",
            change_type="modified",
            context="",
        )
        for f in changed_files
    ]
    combined_changes = list(symbol_changes) + file_only_changes

    at_risk = find_at_risk_memories(
        symbol_changes=combined_changes,
        memory_dir=memory_dir,
        project_root=project_root,
    )

    return SyncPhase1Result(
        at_risk_memories=at_risk,
        changed_files=changed_files,
        changed_symbols=symbol_changes,
        stats={
            "at_risk_count": len(at_risk),
            "changed_files_count": len(changed_files),
            "changed_symbols_count": len(symbol_changes),
        },
    )


# ---------------------------------------------------------------------------
# Phase 2: Fact-Check Context Preparation
# ---------------------------------------------------------------------------


def phase2_prepare_factcheck(
    at_risk: list[AtRiskMemory],
    project_root: str,
) -> SyncPhase2Result:
    """Assemble fact-check context for each at-risk memory.

    For each memory, builds a FactCheckItem with the memory content,
    citations, relevant diff, current code snippet, and a prompt.

    Args:
        at_risk: At-risk memories from Phase 1.
        project_root: Root of the project for reading current code.

    Returns:
        SyncPhase2Result with fact-check items.
    """
    items: list[FactCheckItem] = []

    for arm in at_risk:
        # Read current code for each cited file
        snippets: list[str] = []
        for citation in arm.at_risk_citations:
            snippet = _read_code_snippet(project_root, citation.file)
            if snippet:
                snippets.append(snippet)

        current_code = "\n".join(snippets)

        citations_text = "\n".join(
            f"- {c.file}" + (f"::{c.symbol}" if c.symbol else "")
            for c in arm.at_risk_citations
        )

        prompt = _FACTCHECK_ITEM_PROMPT.format(
            memory_path=arm.memory.path,
            memory_content=arm.memory.content,
            citations_text=citations_text,
            relevant_diff=arm.relevant_diff,
            current_code=current_code,
        )

        items.append(FactCheckItem(
            memory_path=arm.memory.path,
            memory_content=arm.memory.content,
            citations=list(arm.at_risk_citations),
            relevant_diff=arm.relevant_diff,
            current_code_snippet=current_code,
            prompt=prompt,
        ))

    return SyncPhase2Result(
        factcheck_items=items,
        total_at_risk=len(items),
    )


# ---------------------------------------------------------------------------
# Phase 3: Discovery Context Preparation
# ---------------------------------------------------------------------------


def phase3_prepare_discovery(
    project_root: str,
    memory_dir: str,
    symbol_changes: list[SymbolChange] | None = None,
    changed_files: list[str] | None = None,
) -> SyncPhase3Result:
    """Prepare discovery context for the calling LLM.

    Analyzes the changeset for notable changes and prepares context
    for the LLM to decide what's worth remembering.

    Args:
        project_root: Root directory of the git repository.
        memory_dir: Root memory directory.
        symbol_changes: Symbol-level changes from diff_symbols.
        changed_files: List of changed file paths.

    Returns:
        SyncPhase3Result with discovery context and taxonomy guidance.
    """
    if symbol_changes is None:
        symbol_changes = []
    if changed_files is None:
        changed_files = []

    new_symbols = [s for s in symbol_changes if s.change_type == "added"]
    removed_symbols = [s for s in symbol_changes if s.change_type == "removed"]

    # Build diff summary
    diff_lines = [f"Changed files: {', '.join(changed_files)}"] if changed_files else []
    if new_symbols:
        diff_lines.append("New symbols: " + ", ".join(s.symbol_name for s in new_symbols))
    if removed_symbols:
        diff_lines.append("Removed symbols: " + ", ".join(s.symbol_name for s in removed_symbols))
    modified = [s for s in symbol_changes if s.change_type == "modified"]
    if modified:
        diff_lines.append("Modified symbols: " + ", ".join(s.symbol_name for s in modified))

    diff_summary = "\n".join(diff_lines) if diff_lines else "No symbol-level changes detected."

    # Build discovery context
    context_parts = [
        "## Changeset Summary",
        diff_summary,
        "",
        "## Memory Type Guidance",
        _MEMORY_TYPE_GUIDANCE,
    ]

    if new_symbols:
        context_parts.append("\n## New Symbols (candidates for new memories)")
        for s in new_symbols:
            context_parts.append(f"- {s.file}::{s.symbol_name} ({s.symbol_type}): {s.context}")

    if removed_symbols:
        context_parts.append("\n## Removed Symbols (check for stale memories)")
        for s in removed_symbols:
            context_parts.append(f"- {s.file}::{s.symbol_name} ({s.symbol_type}): {s.context}")

    discovery_context = "\n".join(context_parts)

    return SyncPhase3Result(
        discovery_context=discovery_context,
        diff_summary=diff_summary,
        new_symbols=new_symbols,
        removed_symbols=removed_symbols,
        memory_type_guidance=_MEMORY_TYPE_GUIDANCE,
    )


# ---------------------------------------------------------------------------
# Phase 4: Quality Gate
# ---------------------------------------------------------------------------


def phase4_quality_gate(
    new_memories: list[dict],
    memory_dir: str,
    project_root: str,
) -> SyncPhase4Result:
    """Validate proposed new memories with heuristic checks.

    Checks: dedup (content-hash), citation validation, content length,
    tag/citation anchoring.

    Args:
        new_memories: Memories proposed by the LLM.
        memory_dir: Root memory directory.
        project_root: Root of the project for citation checks.

    Returns:
        SyncPhase4Result with accepted and rejected memories.
    """
    existing_hashes = _scan_existing_hashes(memory_dir)

    accepted: list[dict] = []
    rejected: list[dict] = []

    for mem in new_memories:
        content = mem.get("content", "")
        citations = mem.get("citations", [])
        tags = mem.get("tags", [])

        # Content length checks
        word_count = len(content.split())
        if word_count < 10:
            rejected.append({**mem, "reason": "too_short"})
            continue
        if word_count > 500:
            rejected.append({**mem, "reason": "too_long"})
            continue

        # Dedup check
        c_hash = _content_hash(content)
        if c_hash in existing_hashes:
            rejected.append({**mem, "reason": "duplicate"})
            continue

        # Citation validation
        if citations:
            all_valid = True
            for cit in citations:
                cited_file = cit.get("file", "")
                full_path = os.path.join(project_root, cited_file)
                if not os.path.exists(full_path):
                    all_valid = False
                    break
            if not all_valid:
                rejected.append({**mem, "reason": "citation_invalid"})
                continue

        # Anchoring check: must have at least tags OR citations
        if not citations and not tags:
            rejected.append({**mem, "reason": "unanchored"})
            continue

        accepted.append(mem)

    return SyncPhase4Result(accepted=accepted, rejected=rejected)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def memory_sync(
    project_root: str,
    memory_dir: str,
    changed_files: list[str],
    symbol_changes: list[SymbolChange] | None = None,
    diff_text: str = "",
) -> SyncPlan:
    """Run phases 1-3 and return a SyncPlan for the calling LLM.

    Args:
        project_root: Root directory of the git repository.
        memory_dir: Root memory directory.
        changed_files: Changed file paths from git diff.
        symbol_changes: Symbol-level changes from diff_symbols.
        diff_text: Raw diff text for context.

    Returns:
        SyncPlan the calling LLM should execute.
    """
    if symbol_changes is None:
        symbol_changes = []

    # Phase 1
    p1 = phase1_find_at_risk(
        project_root=project_root,
        memory_dir=memory_dir,
        changed_files=changed_files,
        symbol_changes=symbol_changes,
    )

    # Attach diff text to at-risk memories
    for arm in p1.at_risk_memories:
        arm.relevant_diff = diff_text

    # Phase 2
    p2 = phase2_prepare_factcheck(
        at_risk=p1.at_risk_memories,
        project_root=project_root,
    )

    # Phase 3
    p3 = phase3_prepare_discovery(
        project_root=project_root,
        memory_dir=memory_dir,
        symbol_changes=symbol_changes,
        changed_files=changed_files,
    )

    # Build factcheck section for prompt
    factcheck_section = ""
    for item in p2.factcheck_items:
        factcheck_section += item.prompt + "\n\n"
    if not factcheck_section:
        factcheck_section = "No memories are at risk from this changeset.\n"

    prompt = _PROMPT_TEMPLATE.format(
        factcheck_section=factcheck_section.strip(),
        discovery_section=p3.discovery_context,
    )

    return SyncPlan(
        factcheck_items=p2.factcheck_items,
        discovery_context=p3,
        prompt_template=prompt,
        phase4_instructions=_PHASE4_INSTRUCTIONS,
        stats={
            **p1.stats,
            "factcheck_items_count": len(p2.factcheck_items),
        },
    )


# ---------------------------------------------------------------------------
# Apply results from LLM execution
# ---------------------------------------------------------------------------


def apply_sync_results(
    results: dict,
    memory_dir: str,
    project_root: str,
) -> SyncReport:
    """Process LLM verdicts and new memories.

    Handles:
    - STILL_TRUE / UNCERTAIN: leave memory unchanged
    - NEEDS_UPDATE: rewrite memory content
    - NOW_FALSE: archive (move to .archive/)
    - New memories: run phase4_quality_gate, write accepted ones

    Args:
        results: LLM response with "verdicts" and "new_memories" keys.
        memory_dir: Root memory directory.
        project_root: Root of the project.

    Returns:
        SyncReport summarizing what happened.
    """
    report = SyncReport()

    verdicts = results.get("verdicts", [])
    new_memories = results.get("new_memories", [])

    real_memory_dir = os.path.realpath(memory_dir)

    for verdict_data in verdicts:
        mem_path = verdict_data.get("memory_path", "")
        verdict = verdict_data.get("verdict", "")

        # Validate that the LLM-provided path resolves within memory_dir
        if mem_path:
            real_mem_path = os.path.realpath(mem_path)
            if not real_mem_path.startswith(real_memory_dir + os.sep) and real_mem_path != real_memory_dir:
                report.errors.append(
                    f"Path traversal rejected: '{mem_path}' resolves outside memory directory"
                )
                continue

        try:
            if verdict == "NEEDS_UPDATE":
                updated_content = verdict_data.get("updated_content", "")
                if updated_content and os.path.exists(mem_path):
                    mf = read_memory(mem_path)
                    # Rewrite with updated content and new hash
                    mf.frontmatter.content_hash = _content_hash(updated_content)
                    write_memory_file(mem_path, mf.frontmatter, updated_content)
                    report.memories_updated += 1
                else:
                    report.errors.append(f"NEEDS_UPDATE but no content or path missing: {mem_path}")

            elif verdict == "NOW_FALSE":
                if os.path.exists(mem_path):
                    # Move to archive
                    rel_path = os.path.relpath(mem_path, memory_dir)
                    archive_path = os.path.join(memory_dir, ".archive", rel_path)
                    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
                    os.rename(mem_path, archive_path)
                    report.memories_archived += 1
                else:
                    report.errors.append(f"NOW_FALSE but path missing: {mem_path}")

            elif verdict == "STILL_TRUE":
                # Refresh last_verified to today so confidence decay resets.
                # created is left untouched; content is not rewritten.
                if os.path.exists(mem_path):
                    mf = read_memory(mem_path)
                    mf.frontmatter.last_verified = date.today()
                    write_memory_file(mem_path, mf.frontmatter, mf.content)
                report.memories_unchanged += 1

            elif verdict == "UNCERTAIN":
                report.memories_unchanged += 1

            else:
                report.errors.append(f"Unknown verdict '{verdict}' for {mem_path}")

        except OSError as e:
            report.errors.append(f"Error processing {mem_path}: {e}")

    # Process new memories through quality gate
    if new_memories:
        gate_result = phase4_quality_gate(
            new_memories=new_memories,
            memory_dir=memory_dir,
            project_root=project_root,
        )

        for mem in gate_result.accepted:
            try:
                citations = [
                    Citation(
                        file=c.get("file", ""),
                        symbol=c.get("symbol"),
                        symbol_type=c.get("symbol_type"),
                    )
                    for c in mem.get("citations", [])
                ]
                store_memory(
                    content=mem["content"],
                    type=mem.get("type", "project"),
                    kind=mem.get("kind"),
                    citations=citations,
                    tags=mem.get("tags", []),
                    scope="project",
                    branch=None,
                    memory_dir=memory_dir,
                )
                report.memories_created += 1
            except OSError as e:
                report.errors.append(f"Error storing new memory: {e}")

        report.memories_rejected += len(gate_result.rejected)

    return report
