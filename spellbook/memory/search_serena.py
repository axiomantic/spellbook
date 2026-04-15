"""At-risk memory detection for the memory sync pipeline.

Identifies memory files whose citations may be stale because the cited
source files appear in a recent set of symbol-level changes. Detection is
file-level (grep-based via citation.file matching), not symbol-level: any
change to a cited file marks every citation pointing at that file as
at-risk.

This module does NOT integrate with Serena. The name is retained for
historical reasons and import compatibility; symbol-level integration via
Serena was never implemented.
"""

from dataclasses import dataclass

from spellbook.memory.diff_symbols import SymbolChange
from spellbook.memory.frontmatter import parse_frontmatter
from spellbook.memory.models import Citation, MemoryFile
from spellbook.memory.utils import iter_memory_files


@dataclass
class AtRiskMemory:
    """A memory whose citations may be stale due to code changes."""

    memory: MemoryFile
    at_risk_citations: list[Citation]
    reason: str  # cited_file_changed, cited_symbol_modified, referenced_symbol_changed
    relevant_diff: str = ""


def find_at_risk_memories(
    symbol_changes: list[SymbolChange],
    memory_dir: str,
) -> list[AtRiskMemory]:
    """Find memories with citations into files that have changed.

    Args:
        symbol_changes: Symbol-level changes from diff_symbols. Only the
            ``file`` attribute is consulted; symbol identity is not used.
        memory_dir: Root memory directory to scan for ``.md`` files.

    Returns:
        AtRiskMemory entries for every memory whose frontmatter citations
        reference at least one file present in ``symbol_changes``.
    """
    changed_set = {sc.file for sc in symbol_changes}
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

    return at_risk
