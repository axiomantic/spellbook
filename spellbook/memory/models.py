"""Data models for the file-based memory system.

Defines dataclasses for memory files, frontmatter, citations, search results,
and verification context. These are pure data containers with no I/O.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Citation:
    """A code reference within a memory."""

    file: str
    symbol: Optional[str] = None
    symbol_type: Optional[str] = None  # function, method, class, module, variable, type
    # Optional source line anchor. ``line_start`` is 1-indexed; ``line_end``
    # is inclusive. When only ``line_start`` is set, callers should treat it
    # as a single-line citation. Used by the sync pipeline to window the
    # source-code snippet handed to fact-checking LLMs.
    line_start: Optional[int] = None
    line_end: Optional[int] = None


@dataclass
class MemoryFrontmatter:
    """Structured YAML frontmatter for a memory file."""

    type: str  # project, user, feedback, reference
    created: date
    kind: Optional[str] = None  # fact, rule, convention, preference, decision, antipattern
    citations: list[Citation] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    scope: str = "project"  # project, global
    branch: Optional[str] = None
    last_verified: Optional[date] = None
    confidence: Optional[str] = None  # high, medium, low
    content_hash: Optional[str] = None


@dataclass
class MemoryFile:
    """A parsed memory file: path + frontmatter + body content."""

    path: str
    frontmatter: MemoryFrontmatter
    content: str  # body text (not including frontmatter)


@dataclass
class MemoryResult:
    """A search result: memory file + relevance score."""

    memory: MemoryFile
    score: float
    match_context: Optional[str] = None  # matched line/snippet


@dataclass
class VerifyContext:
    """Context package for LLM-driven fact-checking of a memory."""

    memory: MemoryFile
    cited_files_exist: dict[str, bool]
    cited_symbols_exist: dict[str, bool]
    relevant_diffs: Optional[str] = None
