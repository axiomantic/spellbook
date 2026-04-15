"""YAML frontmatter parser/writer for memory files.

Handles parsing markdown files with YAML frontmatter delimited by --- markers,
writing memory files with atomic rename, and generating kebab-case slugs.
"""

import os
import re
import tempfile
from datetime import date
from pathlib import Path

import yaml

from spellbook.core.compat import CrossPlatformLock
from spellbook.memory.models import Citation, MemoryFrontmatter


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.DOTALL)

_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "he", "in", "is", "it", "its", "of", "on", "or",
    "that", "the", "to", "was", "we", "were", "will", "with", "use",
})


def parse_frontmatter(file_path: str) -> tuple[MemoryFrontmatter, str]:
    """Parse a memory file into frontmatter and body.

    Args:
        file_path: Absolute path to the memory markdown file.

    Returns:
        Tuple of (MemoryFrontmatter, body_text).

    Raises:
        ValueError: If frontmatter is missing or malformed.
    """
    with open(file_path, "r") as f:
        raw = f.read()

    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError("Memory file missing YAML frontmatter (expected --- delimiters)")

    yaml_str, body = match.group(1), match.group(2)
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed YAML frontmatter: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    fm = _dict_to_frontmatter(data)
    return fm, body


def write_memory_file(
    path: str,
    frontmatter: MemoryFrontmatter,
    body: str,
) -> None:
    """Write a memory file with atomic rename.

    Uses temp file + os.rename for atomicity (same filesystem).

    Args:
        path: Absolute path where the file should be written.
        frontmatter: Structured frontmatter data.
        body: Markdown body text.
    """
    content = _render(frontmatter, body)
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)

    lock_path = Path(path + ".lock")
    with CrossPlatformLock(lock_path, shared=False, blocking=True):
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".tmp_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise


def generate_slug(content: str, existing_slugs: set[str]) -> str:
    """Generate a kebab-case slug from content.

    Extracts first 6 significant words (after removing stopwords and punctuation),
    joins with hyphens. Appends numeric suffix on collision.

    Args:
        content: The memory content text.
        existing_slugs: Set of slugs already in use.

    Returns:
        A unique kebab-case slug string.
    """
    # Strip punctuation and lowercase
    cleaned = re.sub(r"[^\w\s-]", "", content.lower())
    words = cleaned.split()

    # Filter stopwords and very short words
    significant = [w for w in words if w not in _STOPWORDS and len(w) > 1]

    # Take first 6 (or fewer)
    slug_words = significant[:6] if len(significant) > 6 else significant
    if not slug_words:
        slug_words = [w for w in words if len(w) > 1][:3]
    if not slug_words:
        slug_words = ["memory"]

    base_slug = "-".join(slug_words)

    if base_slug not in existing_slugs:
        return base_slug

    # Collision: append suffix
    suffix = 2
    while f"{base_slug}-{suffix}" in existing_slugs:
        suffix += 1
    return f"{base_slug}-{suffix}"


def _render(frontmatter: MemoryFrontmatter, body: str) -> str:
    """Render frontmatter + body into a complete memory file string."""
    d = _frontmatter_to_dict(frontmatter)
    yaml_str = yaml.dump(
        d,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    body_stripped = body.strip()
    return f"---\n{yaml_str}---\n\n{body_stripped}\n"


def _frontmatter_to_dict(fm: MemoryFrontmatter) -> dict:
    """Convert frontmatter dataclass to dict for YAML serialization."""
    d: dict = {"type": fm.type, "created": fm.created}
    if fm.kind is not None:
        d["kind"] = fm.kind
    if fm.citations:
        d["citations"] = [_citation_to_dict(c) for c in fm.citations]
    if fm.tags:
        d["tags"] = fm.tags
    if fm.scope != "project":
        d["scope"] = fm.scope
    if fm.branch is not None:
        d["branch"] = fm.branch
    if fm.last_verified is not None:
        d["last_verified"] = fm.last_verified
    if fm.confidence is not None:
        d["confidence"] = fm.confidence
    if fm.content_hash is not None:
        d["content_hash"] = fm.content_hash
    return d


def _citation_to_dict(c: Citation) -> dict:
    """Convert a Citation dataclass to a dict for YAML."""
    d: dict = {"file": c.file}
    if c.symbol is not None:
        d["symbol"] = c.symbol
    if c.symbol_type is not None:
        d["symbol_type"] = c.symbol_type
    if c.line_start is not None:
        d["line_start"] = c.line_start
    if c.line_end is not None:
        d["line_end"] = c.line_end
    return d


def _dict_to_frontmatter(data: dict) -> MemoryFrontmatter:
    """Parse a YAML dict into MemoryFrontmatter.

    Raises:
        ValueError: If required fields (type, created) are missing or invalid.
    """
    mem_type = data.get("type")
    if mem_type is None:
        raise ValueError("Memory frontmatter missing required field 'type'")

    created_raw = data.get("created")
    if created_raw is None:
        raise ValueError("Memory frontmatter missing required field 'created'")

    # Parse created date
    if isinstance(created_raw, date):
        created = created_raw
    elif isinstance(created_raw, str):
        created = date.fromisoformat(created_raw)
    else:
        raise ValueError(
            f"Memory frontmatter 'created' must be a date or ISO date string, got {type(created_raw).__name__}"
        )

    # Parse citations
    citations_raw = data.get("citations", [])
    citations = []
    if citations_raw:
        for c in citations_raw:
            citations.append(Citation(
                file=c["file"],
                symbol=c.get("symbol"),
                symbol_type=c.get("symbol_type"),
                line_start=c.get("line_start"),
                line_end=c.get("line_end"),
            ))

    # Parse last_verified
    lv_raw = data.get("last_verified")
    last_verified = None
    if isinstance(lv_raw, date):
        last_verified = lv_raw
    elif isinstance(lv_raw, str):
        last_verified = date.fromisoformat(lv_raw)

    return MemoryFrontmatter(
        type=mem_type,
        created=created,
        kind=data.get("kind"),
        citations=citations,
        tags=data.get("tags", []),
        scope=data.get("scope", "project"),
        branch=data.get("branch"),
        last_verified=last_verified,
        confidence=data.get("confidence"),
        content_hash=data.get("content_hash"),
    )
