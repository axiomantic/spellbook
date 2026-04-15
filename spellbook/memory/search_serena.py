"""Serena adapter for code intelligence in the memory sync pipeline.

Provides symbol reference finding and file symbol listing via Serena CLI.
Serena is a hard dependency; callers must ensure_memory_system_available()
before invoking these functions.
"""

from dataclasses import dataclass

from spellbook.memory.diff_symbols import SymbolChange
from spellbook.memory.frontmatter import parse_frontmatter
from spellbook.memory.models import Citation, MemoryFile
from spellbook.memory.utils import iter_memory_files


@dataclass
class SymbolReference:
    """A reference to a symbol found by Serena."""

    file: str
    symbol: str
    line: int


@dataclass
class AtRiskMemory:
    """A memory whose citations may be stale due to code changes."""

    memory: MemoryFile
    at_risk_citations: list[Citation]
    reason: str  # cited_file_changed, cited_symbol_modified, referenced_symbol_changed
    relevant_diff: str = ""


# ---------------------------------------------------------------------------
# Serena operations
# ---------------------------------------------------------------------------


def find_symbol_references(
    symbol_name: str, project_root: str
) -> list[SymbolReference]:
    """Find all references to a symbol using Serena.

    Args:
        symbol_name: The symbol to search for.
        project_root: Root of the project.

    Returns:
        List of SymbolReference.
    """
    # Serena CLI integration would go here
    return []


def get_file_symbols(file_path: str, project_root: str) -> list[str]:
    """Get all symbol names in a file using Serena.

    Args:
        file_path: Path to the file (relative to project root).
        project_root: Root of the project.

    Returns:
        List of symbol names.
    """
    # Serena CLI integration would go here
    return []


# ---------------------------------------------------------------------------
# At-risk memory detection
# ---------------------------------------------------------------------------


def find_at_risk_memories(
    symbol_changes: list[SymbolChange],
    memory_dir: str,
    project_root: str,
) -> list[AtRiskMemory]:
    """Find at-risk memories using Serena for symbol-level precision.

    Args:
        symbol_changes: List of changed symbols from diff_symbols.
        memory_dir: Root memory directory.
        project_root: Root of the project for Serena queries.

    Returns:
        List of AtRiskMemory with at-risk citations and reasons.
    """
    changed_files = list({sc.file for sc in symbol_changes})
    changed_set = set(changed_files)
    at_risk: list[AtRiskMemory] = []

    for md_path in iter_memory_files(memory_dir):
        try:
            fm, body = parse_frontmatter(md_path)
        except (ValueError, OSError):
            continue

        if not fm.citations:
            continue

        matching_citations: list[Citation] = []
        for citation in fm.citations:
            if citation.file in changed_set:
                matching_citations.append(citation)

        if matching_citations:
            mf = MemoryFile(path=md_path, frontmatter=fm, content=body)
            at_risk.append(AtRiskMemory(
                memory=mf,
                at_risk_citations=matching_citations,
                reason="cited_file_changed",
            ))

    # TODO: enhance with Serena's find_referencing_symbols for
    # "referenced_symbol_changed" detection

    return at_risk
