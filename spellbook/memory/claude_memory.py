"""Read-side integration with Claude Code's memory directory.

Scans ``~/.claude/projects/<project-encoded>/memory/`` for per-session memory
files written by Claude Code, translates each file's frontmatter into the
spellbook ``MemoryFrontmatter`` shape, and returns a list of
``MemoryResult`` that callers (notably ``search_qmd.search_memories``) can
merge into the recall candidate pool.

This module is *read-only*: it never writes to or mutates Claude's files.
The claude-side schema is decoupled from spellbook's canonical schema —
we translate at scan time and never persist the foreign shape.

Observed Claude frontmatter fields:
    name, description, type, and optionally originSessionId.
``originSessionId`` is preserved as a spellbook tag of the form
``origin_session:<id>`` so its provenance stays searchable without
changing the canonical ``MemoryFrontmatter`` schema.

Backwards-compat gate: ``scan()`` is only invoked from
``search_qmd.search_memories`` when the config key
``worker_llm_read_claude_memory`` is ``True`` (default: ``False``).
See impl plan D5 and design §5.5 for the merge wiring.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import yaml

from spellbook.memory.models import MemoryFile, MemoryFrontmatter, MemoryResult
from spellbook.memory.scoring import compute_score

logger = logging.getLogger(__name__)

# Size cap so a pathologically large file cannot stall memory recall.
# 256 KB is ~4x the largest Claude memory file observed in practice.
MAX_FILE_SIZE = 256 * 1024

# Opaque label; bumped when the translator is verified against a new
# Claude schema. A file whose frontmatter declares a ``schema_version``
# that does not match is skipped with a warning.
SCHEMA_VERSION_LABEL = "claude_memory_schema_v1"

# The default score assigned to a Claude memory when no query terms are
# supplied. Intentionally below spellbook-native hits so that, after
# content-hash dedup at the merge site, a matching native hit wins.
_DEFAULT_SCORE = 0.5

# Index boost: small bump for files enumerated in Claude's MEMORY.md
# summary, preserving Claude's own relevance signal without overwhelming
# the spellbook scoring.
_INDEX_BOOST = 0.05


def _encode_project(project_root: str) -> str:
    """Return the spellbook ``project-encoded`` form of ``project_root``.

    Matches the convention documented in ``CLAUDE.md``: leading ``/`` is
    stripped, remaining slashes are replaced with dashes.
    """
    return project_root.lstrip("/").replace("/", "-")


def _memory_dir(project_root: str) -> Path:
    encoded = _encode_project(project_root)
    return Path.home() / ".claude" / "projects" / encoded / "memory"


def _safe_read(path: Path) -> str | None:
    """Read ``path`` with size and symlink guards. Returns ``None`` on skip."""
    if path.is_symlink():
        logger.warning("claude_memory: skipping symlink %s", path)
        return None
    try:
        st = path.stat()
    except OSError as e:
        logger.warning("claude_memory: stat failed for %s: %s", path, e)
        return None
    if st.st_size > MAX_FILE_SIZE:
        logger.warning(
            "claude_memory: skipping %s (size=%d > cap=%d)",
            path,
            st.st_size,
            MAX_FILE_SIZE,
        )
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("claude_memory: read failed for %s: %s", path, e)
        return None


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.DOTALL)


def _parse_claude_frontmatter(
    path: Path, raw: str
) -> tuple[MemoryFrontmatter, str] | None:
    """Translate a Claude memory file into spellbook's ``MemoryFrontmatter``.

    Claude files use a divergent schema (``name``, ``description``,
    ``type``, optional ``originSessionId``) that lacks the spellbook-
    required ``created`` date. We synthesize ``created=today()`` so the
    spellbook scoring (temporal decay) treats Claude hits as fresh by
    default. ``type`` is propagated verbatim; ``kind`` defaults to
    ``"fact"``; citations are empty (Claude files carry none).

    Returns ``None`` when the frontmatter is missing or malformed — the
    caller logs and moves on.
    """
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        logger.warning(
            "claude_memory: %s missing --- frontmatter delimiters", path
        )
        return None

    yaml_str, body = match.group(1), match.group(2)
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        logger.warning("claude_memory: YAML parse failed for %s: %s", path, e)
        return None

    if not isinstance(data, dict):
        logger.warning("claude_memory: frontmatter is not a mapping in %s", path)
        return None

    # Schema gate: if a file explicitly declares a schema version, it must
    # match the version this translator is known to handle. Unknown
    # versions are skipped (not silently accepted) to prevent drift.
    declared_schema = data.get("schema_version")
    if declared_schema and declared_schema != SCHEMA_VERSION_LABEL:
        logger.warning(
            "claude_memory: schema mismatch in %s (declared=%s, expected=%s)",
            path,
            declared_schema,
            SCHEMA_VERSION_LABEL,
        )
        return None

    # ``type`` is the only claude field that maps 1:1 onto the spellbook
    # schema's required category. Default to "project" when the claude
    # file omits it; do not reject, since the claude schema has drifted
    # historically and forward-compat matters more than strictness.
    claude_type = data.get("type") or "project"

    # Extract origin session id (both snake_case and the observed camelCase
    # key) and record it as a spellbook tag.
    origin = data.get("origin_session_id") or data.get("originSessionId")

    tags: list[str] = list(data.get("tags") or [])
    if origin:
        tag = f"origin_session:{origin}"
        if tag not in tags:
            tags.append(tag)

    fm = MemoryFrontmatter(
        type=str(claude_type),
        # Claude files lack ``created``; synthesize today so temporal decay
        # treats them as fresh. Not persisted — Claude's file is untouched.
        created=date.today(),
        kind="fact",
        citations=[],
        tags=tags,
        scope="project",
        branch=None,
        last_verified=None,
        confidence=None,
        content_hash=None,
    )
    return fm, body


def _load_index_boost(dir_path: Path) -> set[str]:
    """Return the set of filenames referenced in Claude's ``MEMORY.md`` index."""
    idx = dir_path / "MEMORY.md"
    if not idx.exists():
        return set()
    text = _safe_read(idx)
    if text is None:
        return set()
    boosted: set[str] = set()
    for line in text.splitlines():
        # Permissive: anything ending in ``.md`` counts as a reference.
        for token in line.split():
            cleaned = token.strip("()[],`\"'")
            if cleaned.endswith(".md"):
                boosted.add(cleaned)
    return boosted


def scan(
    project_root: str,
    query_terms: list[str] | None = None,
    branch: str | None = None,
) -> list[MemoryResult]:
    """Return the Claude memory files for ``project_root`` as ``MemoryResult``s.

    Args:
        project_root: Absolute project root path. Encoded with
            ``_encode_project`` to locate the per-project memory dir.
        query_terms: Lowercased query tokens. When non-empty, used to
            compute each result's score via ``compute_score``. When empty
            or ``None``, every hit gets ``_DEFAULT_SCORE`` so callers can
            merge-and-rank.
        branch: Current git branch (for branch-weighted scoring).

    Returns:
        A list of ``MemoryResult``. Empty if the memory directory is
        missing, not a directory, or contains no parseable files.
        Never raises: all per-file failures are logged and skipped.
    """
    dir_path = _memory_dir(project_root)
    if not dir_path.exists() or not dir_path.is_dir():
        return []

    boosted = _load_index_boost(dir_path)
    results: list[MemoryResult] = []

    for path in sorted(dir_path.glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        raw = _safe_read(path)
        if raw is None:
            continue
        parsed = _parse_claude_frontmatter(path, raw)
        if parsed is None:
            continue
        fm, body = parsed
        mf = MemoryFile(path=str(path), frontmatter=fm, content=body.strip())

        if query_terms:
            score = compute_score(mf, query_terms, branch)
        else:
            score = _DEFAULT_SCORE
        if path.name in boosted:
            score = min(1.0, score + _INDEX_BOOST)

        results.append(MemoryResult(memory=mf, score=score, match_context=None))

    return results
