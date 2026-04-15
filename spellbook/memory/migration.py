"""SQLite-to-markdown migration for spellbook's memory system.

Exports existing memories from the SQLite database to markdown files
with YAML frontmatter, following the new file-based memory format.
"""

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import date

from spellbook.memory.frontmatter import (
    generate_slug,
    parse_frontmatter,
    write_memory_file,
)
from spellbook.memory.models import Citation, MemoryFrontmatter


@dataclass
class MigrationReport:
    """Summary of a memory migration run."""

    total_memories: int
    migrated: int
    skipped: int  # e.g., empty content
    archived: int  # soft-deleted -> .archive/
    errors: list[str]
    type_distribution: dict[str, int]  # project: N, user: M, ...


@dataclass
class VerificationReport:
    """Summary of migration verification."""

    sqlite_count: int
    markdown_count: int
    hash_matches: int
    hash_mismatches: int
    missing_in_markdown: list[str]  # memory IDs not found


def _content_hash(content: str) -> str:
    """SHA-256 of normalized content (lowercased, whitespace-collapsed)."""
    normalized = " ".join(content.lower().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _infer_type(content: str, memory_type: str) -> str:
    """Infer the memory type (project/user/feedback/reference) from content heuristics.

    Rules:
    - Content mentioning "user prefers", "I prefer" -> user
    - Content mentioning "rule:", "always do", "always run" -> feedback
    - Content mentioning URLs or external systems -> reference
    - Default -> project
    """
    lower = content.lower()

    # User preferences
    if re.search(r"\b(user prefers|i prefer|prefers\b)", lower):
        return "user"

    # Feedback / rules
    if re.search(r"\brule:", lower) or re.search(r"\balways (do|run|use)\b", lower):
        return "feedback"

    # References (URLs)
    if re.search(r"https?://", lower):
        return "reference"

    # Default
    return "project"


def _map_kind(memory_type: str | None) -> str:
    """Map SQLite memory_type to the new kind field."""
    valid_kinds = {"fact", "rule", "antipattern", "preference", "decision"}
    if memory_type and memory_type in valid_kinds:
        return memory_type
    return "fact"


def _parse_date(iso_str: str | None) -> date:
    """Parse an ISO datetime string to a date. Falls back to today."""
    if not iso_str:
        return date.today()
    try:
        # Handle ISO datetime with timezone
        return date.fromisoformat(iso_str[:10])
    except (ValueError, TypeError):
        return date.today()


def _importance_to_access_count(importance: float) -> int:
    """Convert importance score to access count.

    Inverse of: importance = 1.0 + 0.1 * count
    So: count = (importance - 1.0) / 0.1
    """
    if importance <= 1.0:
        return 0
    return round((importance - 1.0) / 0.1)


def migrate_memories(
    db_path: str,
    output_dir: str,
    include_deleted: bool = False,
) -> MigrationReport:
    """Migrate memories from SQLite to markdown files.

    Args:
        db_path: Path to the SQLite database.
        output_dir: Directory where markdown files will be written.
        include_deleted: If True, export soft-deleted memories to .archive/.

    Returns:
        MigrationReport with counts and distribution.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Fetch all memories
    if include_deleted:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY created_at"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE status = 'active' ORDER BY created_at"
        ).fetchall()

    total = len(rows)
    migrated = 0
    skipped = 0
    archived = 0
    errors: list[str] = []
    type_distribution: dict[str, int] = {}
    existing_slugs: dict[str, set[str]] = {}  # type_dir -> set of slugs
    access_log: dict[str, dict] = {}

    for row in rows:
        content = row["content"]
        mem_id = row["id"]
        status = row["status"]
        is_deleted = status == "deleted"

        # Skip empty content
        if not content or not content.strip():
            skipped += 1
            continue

        # Map fields
        kind = _map_kind(row["memory_type"])
        inferred_type = _infer_type(content, row["memory_type"])
        branch = row["branch"] if row["branch"] else None
        scope = row["scope"] or "project"
        importance = row["importance"] or 1.0
        created = _parse_date(row["created_at"])

        # Extract tags from meta JSON
        tags: list[str] = []
        meta_str = row["meta"]
        if meta_str:
            try:
                meta = json.loads(meta_str)
                tags = meta.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
            except (json.JSONDecodeError, TypeError):
                pass

        # Fetch citations
        cit_rows = conn.execute(
            "SELECT file_path, line_range, content_snippet "
            "FROM memory_citations WHERE memory_id = ?",
            (mem_id,),
        ).fetchall()
        citations = [Citation(file=cr["file_path"]) for cr in cit_rows]

        # Compute content hash
        c_hash = _content_hash(content)

        # Determine target directory
        if is_deleted and include_deleted:
            target_type_dir = inferred_type
            base_dir = os.path.join(output_dir, ".archive")
        else:
            target_type_dir = inferred_type
            base_dir = output_dir

        # Generate slug
        if target_type_dir not in existing_slugs:
            existing_slugs[target_type_dir] = set()
        slug = generate_slug(content, existing_slugs[target_type_dir])
        existing_slugs[target_type_dir].add(slug)

        # Build frontmatter
        fm = MemoryFrontmatter(
            type=inferred_type,
            created=created,
            kind=kind,
            citations=citations,
            tags=tags,
            scope=scope,
            branch=branch,
            content_hash=c_hash,
        )

        # Write file
        file_path = os.path.join(base_dir, target_type_dir, f"{slug}.md")
        try:
            write_memory_file(file_path, fm, content)
        except Exception as e:
            errors.append(f"Failed to write {mem_id}: {e}")
            continue

        if is_deleted:
            archived += 1
        else:
            migrated += 1
            type_distribution[inferred_type] = type_distribution.get(inferred_type, 0) + 1

        # Track importance for access log
        access_count = _importance_to_access_count(importance)
        if access_count > 0:
            rel_path = os.path.relpath(file_path, output_dir)
            access_log[rel_path] = {
                "count": access_count,
                "last_accessed": row["accessed_at"] or row["created_at"] or "",
            }

    conn.close()

    # Write access log if any entries
    if access_log:
        os.makedirs(output_dir, exist_ok=True)
        access_log_path = os.path.join(output_dir, ".access-log.json")
        with open(access_log_path, "w") as f:
            json.dump(access_log, f, separators=(",", ":"))

    return MigrationReport(
        total_memories=total,
        migrated=migrated,
        skipped=skipped,
        archived=archived,
        errors=errors,
        type_distribution=type_distribution,
    )


def migrate_raw_events(db_path: str, output_dir: str) -> int:
    """Export unconsolidated raw events as a JSON file.

    Args:
        db_path: Path to the SQLite database.
        output_dir: Directory where raw_events.json will be written.

    Returns:
        Count of exported events.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, session_id, timestamp, project, branch, event_type, "
        "tool_name, subject, summary, tags "
        "FROM raw_events WHERE consolidated = 0 ORDER BY id"
    ).fetchall()

    conn.close()

    if not rows:
        return 0

    events = [
        {
            "id": r["id"],
            "session_id": r["session_id"],
            "timestamp": r["timestamp"],
            "project": r["project"],
            "branch": r["branch"],
            "event_type": r["event_type"],
            "tool_name": r["tool_name"],
            "subject": r["subject"],
            "summary": r["summary"],
            "tags": r["tags"],
        }
        for r in rows
    ]

    os.makedirs(output_dir, exist_ok=True)
    events_path = os.path.join(output_dir, "raw_events.json")
    with open(events_path, "w") as f:
        json.dump(events, f, indent=2)

    return len(events)


def verify_migration(db_path: str, output_dir: str) -> VerificationReport:
    """Verify a migration by comparing SQLite and markdown files.

    Counts memories in SQLite vs markdown files, verifies content hashes match,
    and reports discrepancies.

    Args:
        db_path: Path to the SQLite database.
        output_dir: Directory containing migrated markdown files.

    Returns:
        VerificationReport with comparison results.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get active memories from SQLite
    sqlite_rows = conn.execute(
        "SELECT id, content, content_hash FROM memories WHERE status = 'active'"
    ).fetchall()
    conn.close()

    sqlite_count = len(sqlite_rows)

    # Build a map of content_hash -> memory_id for SQLite memories
    sqlite_hashes: dict[str, str] = {}
    for row in sqlite_rows:
        c_hash = _content_hash(row["content"])
        sqlite_hashes[c_hash] = row["id"]

    # Scan markdown files in a single pass: collect hashes and check integrity
    markdown_count = 0
    markdown_hashes: set[str] = set()
    hash_mismatches = 0

    if os.path.isdir(output_dir):
        for dirpath, _dirnames, filenames in os.walk(output_dir):
            rel = os.path.relpath(dirpath, output_dir)
            # Skip hidden directories (.archive, .access-log, etc.)
            if rel.startswith("."):
                continue
            for fname in filenames:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(dirpath, fname)
                try:
                    fm, body = parse_frontmatter(fpath)
                except (ValueError, OSError):
                    continue
                markdown_count += 1
                if fm.content_hash:
                    markdown_hashes.add(fm.content_hash)
                    # Check integrity: frontmatter hash vs recomputed from body
                    recomputed = _content_hash(body.strip())
                    if fm.content_hash != recomputed:
                        hash_mismatches += 1

    # Compare SQLite hashes against markdown hashes
    hash_matches = 0
    missing_in_markdown: list[str] = []

    for c_hash, mem_id in sqlite_hashes.items():
        if c_hash in markdown_hashes:
            hash_matches += 1
        else:
            missing_in_markdown.append(mem_id)

    return VerificationReport(
        sqlite_count=sqlite_count,
        markdown_count=markdown_count,
        hash_matches=hash_matches,
        hash_mismatches=hash_mismatches,
        missing_in_markdown=missing_in_markdown,
    )
