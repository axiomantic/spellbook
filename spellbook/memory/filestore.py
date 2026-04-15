"""Core file-based memory CRUD operations.

Provides store, recall, forget, verify, read, and list operations
for markdown memory files with YAML frontmatter.
"""

import hashlib
import logging
import os
import shutil
from datetime import date

from spellbook.memory.access_log import (
    batch_record_access,
    importance_from_log,
    load_access_log,
    record_audit,
)
from spellbook.memory.frontmatter import (
    generate_slug,
    parse_frontmatter,
    write_memory_file,
)
from spellbook.memory.models import (
    Citation,
    MemoryFile,
    MemoryFrontmatter,
    MemoryResult,
    VerifyContext,
)
from spellbook.memory.scoring import compute_score
from spellbook.memory.search_qmd import search_memories as _qmd_search_memories
from spellbook.memory.secret_scanner import scan_for_secrets
from spellbook.memory.utils import content_hash as _content_hash

logger = logging.getLogger(__name__)

# Valid memory type directories. Prevents path traversal via type parameter.
VALID_MEMORY_TYPES = {"project", "user", "feedback", "reference"}


def _find_existing_by_hash(
    memory_dir: str, content_hash: str, type_dir: str
) -> str | None:
    """Scan existing memory files in a type directory for a matching content_hash.

    TODO(perf): this is O(N) in the number of memories of the given type --
    every store_memory call walks the entire type directory and parses each
    file's frontmatter just to check for a hash collision. Proposed fix is a
    hash-prefixed directory index (e.g. ``.index/by-hash/<sha-prefix>/<full-hash>``
    -> filename) maintained alongside writes; lookup then becomes O(1).
    Current scan is fine for small projects but starts to become a noticeable
    fixed cost on every store once a single type directory holds roughly
    500+ memories. Defer until that threshold is hit; the index needs its
    own integrity story (rebuild-on-corruption, archival handling).
    """
    target_dir = os.path.join(memory_dir, type_dir)
    if not os.path.isdir(target_dir):
        return None
    for fname in os.listdir(target_dir):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(target_dir, fname)
        try:
            fm, _ = parse_frontmatter(fpath)
            if fm.content_hash == content_hash:
                return fpath
        except (ValueError, OSError):
            continue
    return None


def _existing_slugs(memory_dir: str, type_dir: str) -> set[str]:
    """Collect existing slug names from a type subdirectory."""
    target_dir = os.path.join(memory_dir, type_dir)
    if not os.path.isdir(target_dir):
        return set()
    slugs: set[str] = set()
    for fname in os.listdir(target_dir):
        if fname.endswith(".md"):
            slugs.add(fname[:-3])  # Strip .md
    return slugs


def _validate_memory_type(type: str) -> None:
    """Validate that the memory type is in the allowlist.

    Raises:
        ValueError: If type is not one of the valid memory types.
    """
    if type not in VALID_MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory type '{type}'. Must be one of: {sorted(VALID_MEMORY_TYPES)}"
        )


def _validate_path_within_dir(path: str, root_dir: str) -> None:
    """Validate that a resolved path is within the root directory.

    Prevents path traversal attacks where a crafted path could escape
    the memory directory.

    Raises:
        ValueError: If the resolved path escapes root_dir.
    """
    real_path = os.path.realpath(path)
    real_root = os.path.realpath(root_dir)
    if not real_path.startswith(real_root + os.sep) and real_path != real_root:
        raise ValueError(
            f"Path '{path}' resolves outside memory directory '{root_dir}'"
        )


def store_memory(
    content: str,
    type: str,
    kind: str | None,
    citations: list[Citation],
    tags: list[str],
    scope: str,
    branch: str | None,
    memory_dir: str,
    confidence: str | None = None,
) -> MemoryFile:
    """Store a new memory as a markdown file with YAML frontmatter.

    Generates a kebab-case slug, checks for content-hash duplicates,
    runs secret detection (flags, does not reject), writes the file
    atomically, and appends to the audit log.

    Args:
        content: Memory body text.
        type: Memory category (project, user, feedback, reference).
        kind: Knowledge classification (fact, rule, convention, etc.).
        citations: List of code references.
        tags: Freeform tags for categorical retrieval.
        scope: "project" or "global".
        branch: Git branch where memory was created.
        memory_dir: Root memory directory.

    Returns:
        MemoryFile with the path, parsed frontmatter, and content.

    Raises:
        ValueError: If type is not a valid memory type.
    """
    _validate_memory_type(type)

    c_hash = _content_hash(content)

    # Dedup check
    existing = _find_existing_by_hash(memory_dir, c_hash, type)
    if existing is not None:
        return read_memory(existing)

    # Secret detection (flag, don't reject)
    findings = scan_for_secrets(content)
    if findings:
        logger.warning(
            "Secret scanner found %d potential secret(s) in memory content: %s",
            len(findings),
            ", ".join(f.pattern_name for f in findings),
        )

    # Generate slug
    slugs = _existing_slugs(memory_dir, type)
    slug = generate_slug(content, slugs)

    # Build frontmatter. New memories default to confidence="high" unless
    # the caller explicitly supplies a value.
    fm = MemoryFrontmatter(
        type=type,
        created=date.today(),
        kind=kind,
        citations=citations,
        tags=tags,
        scope=scope,
        branch=branch,
        confidence=confidence if confidence is not None else "high",
        content_hash=c_hash,
    )

    # Write file
    file_path = os.path.join(memory_dir, type, f"{slug}.md")
    write_memory_file(file_path, fm, content)

    # Audit log
    rel_path = os.path.relpath(file_path, memory_dir)
    record_audit("create", rel_path, {"type": type, "kind": kind}, memory_dir)

    return MemoryFile(path=file_path, frontmatter=fm, content=content)


def recall_memories(
    query: str,
    memory_dir: str,
    scope: str | None = None,
    tags: list[str] | None = None,
    file_path: str | None = None,
    limit: int = 10,
    branch: str | None = None,
) -> list[MemoryResult]:
    """Search and retrieve memories, ranked by relevance.

    Uses QMD hybrid search, with BM25-inspired term frequency,
    temporal decay, and branch multiplier layered on top via
    search_qmd.search_memories. Requires QMD to be installed.

    Args:
        query: Search text.
        memory_dir: Root memory directory.
        scope: Filter by scope (project, global). None means all.
        tags: Filter by tags.
        file_path: Filter by citation file path.
        limit: Maximum results to return.
        branch: Current git branch for branch-weighted scoring.

    Returns:
        List of MemoryResult sorted by score descending, limited to `limit`.
    """
    # When a scope filter is active, over-fetch from QMD so the
    # post-filter can still return up to `limit` matches. Without this
    # the caller gets fewer results than requested whenever some of the
    # top-ranked matches have the wrong scope.
    qmd_limit = limit * 3 if scope is not None else limit
    results = _qmd_search_memories(
        query=query,
        memory_dirs=[memory_dir],
        tags=tags,
        file_path=file_path,
        limit=qmd_limit,
        branch=branch,
    )

    # Filter by scope if specified
    if scope is not None:
        results = [r for r in results if r.memory.frontmatter.scope == scope]

    # Apply access importance boost and update access log.
    # Read the access log ONCE up front so that scoring all candidates is
    # an in-memory dict lookup. We also batch the access-count update at
    # the end into a single write, regardless of how many results we return.
    access_data = load_access_log(memory_dir)

    boosted: list[MemoryResult] = []
    for r in results:
        rel_path = os.path.relpath(r.memory.path, memory_dir)
        importance = importance_from_log(access_data, rel_path)
        boosted.append(MemoryResult(
            memory=r.memory,
            score=r.score * importance,
            match_context=r.match_context,
        ))

    boosted.sort(key=lambda r: r.score, reverse=True)
    final = boosted[:limit]

    rel_paths = [
        os.path.relpath(result.memory.path, memory_dir) for result in final
    ]
    batch_record_access(rel_paths, memory_dir)

    return final


def forget_memory(
    memory_path_or_query: str,
    memory_dir: str,
    archive: bool = True,
) -> bool:
    """Forget a memory by path.

    Args:
        memory_path_or_query: Absolute path to the memory file.
        memory_dir: Root memory directory (used for archive path and audit log).
        archive: If True, move to .archive/. If False, permanently delete.

    Returns:
        True if the memory was found and removed, False otherwise.

    Raises:
        ValueError: If the path resolves outside the memories root directory.
    """
    if not os.path.exists(memory_path_or_query):
        return False

    # Validate path is within the memories root (parent of all memory dirs).
    # This handles both project-scoped and global memories: a global memory's
    # path won't be inside the project memory_dir, but should be inside the
    # overall memories root.
    memories_root = os.path.dirname(os.path.realpath(memory_dir))
    _validate_path_within_dir(memory_path_or_query, memories_root)

    rel_path = os.path.relpath(memory_path_or_query, memory_dir)

    if archive:
        # Move to .archive/ preserving relative path structure
        archive_path = os.path.join(memory_dir, ".archive", rel_path)
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        shutil.move(memory_path_or_query, archive_path)
        record_audit("archive", rel_path, {}, memory_dir)
    else:
        os.unlink(memory_path_or_query)
        record_audit("delete", rel_path, {}, memory_dir)

    return True


def verify_memory(
    memory_path: str,
    project_root: str,
) -> VerifyContext:
    """Check if cited files/symbols still exist.

    Args:
        memory_path: Absolute path to the memory file.
        project_root: Root of the project to check citations against.

    Returns:
        VerifyContext with existence checks for cited files and symbols.
    """
    mf = read_memory(memory_path)

    cited_files_exist: dict[str, bool] = {}
    cited_symbols_exist: dict[str, bool] = {}

    for citation in mf.frontmatter.citations:
        full_path = os.path.join(project_root, citation.file)
        cited_files_exist[citation.file] = os.path.exists(full_path)

        if citation.symbol is not None:
            key = f"{citation.file}::{citation.symbol}"
            # Symbol existence check requires code intelligence (Serena).
            # For now, mark as unknown (False) unless file exists.
            cited_symbols_exist[key] = cited_files_exist.get(citation.file, False)

    return VerifyContext(
        memory=mf,
        cited_files_exist=cited_files_exist,
        cited_symbols_exist=cited_symbols_exist,
    )


def read_memory(memory_path: str) -> MemoryFile:
    """Parse a memory file from disk.

    Args:
        memory_path: Absolute path to the memory markdown file.

    Returns:
        MemoryFile with path, parsed frontmatter, and body content.
    """
    fm, body = parse_frontmatter(memory_path)
    return MemoryFile(path=memory_path, frontmatter=fm, content=body)


def list_memories(
    memory_dir: str,
    type_filter: str | None = None,
    scope: str | None = None,
) -> list[MemoryFile]:
    """List all memory files, optionally filtered.

    Args:
        memory_dir: Root memory directory.
        type_filter: If provided, only list memories in this type subdirectory.
        scope: If provided, only list memories with this scope.

    Returns:
        List of MemoryFile objects.
    """
    if type_filter is not None:
        _validate_memory_type(type_filter)

    results: list[MemoryFile] = []

    if not os.path.isdir(memory_dir):
        return results

    for dirpath, dirnames, filenames in os.walk(memory_dir):
        rel = os.path.relpath(dirpath, memory_dir)
        # Skip hidden directories
        if rel.startswith("."):
            continue
        # Prune hidden subdirectories from traversal
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        # Type filter: check if we're in the right subdirectory
        if type_filter is not None:
            # rel is like "project" or "feedback/sub"
            top_dir = rel.split(os.sep)[0] if rel != "." else ""
            if top_dir != type_filter:
                continue

        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                mf = read_memory(fpath)
                if scope is not None and mf.frontmatter.scope != scope:
                    continue
                results.append(mf)
            except (ValueError, OSError):
                continue

    return results
