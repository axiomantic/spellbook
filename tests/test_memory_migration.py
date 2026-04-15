"""Tests for SQLite-to-markdown memory migration.

TDD RED phase: tests written before implementation.

Covers:
- migrate_memories: field mapping, type inference, citation extraction, tag extraction,
  branch handling, content hash computation, slug generation, archive for deleted
- migrate_raw_events: JSON export of unconsolidated events
- verify_migration: count comparison, hash matching, discrepancy detection
"""

import datetime
import hashlib
import json
import os
import sqlite3

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Reproduce the content hash algorithm from filestore."""
    normalized = " ".join(content.lower().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _create_test_db(db_path: str) -> None:
    """Create a minimal SQLite database matching the spellbook schema."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT,
            namespace TEXT NOT NULL,
            branch TEXT,
            scope TEXT DEFAULT 'project',
            importance FLOAT DEFAULT 1.0,
            created_at TEXT,
            accessed_at TEXT,
            status TEXT DEFAULT 'active',
            deleted_at TEXT,
            content_hash TEXT,
            meta TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS memory_citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line_range TEXT,
            content_snippet TEXT,
            UNIQUE(memory_id, file_path, line_range)
        );
        CREATE TABLE IF NOT EXISTS memory_branches (
            memory_id TEXT,
            branch_name TEXT,
            association_type TEXT,
            created_at TEXT,
            PRIMARY KEY (memory_id, branch_name)
        );
        CREATE TABLE IF NOT EXISTS raw_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TEXT NOT NULL,
            project TEXT NOT NULL,
            branch TEXT DEFAULT '',
            event_type TEXT,
            tool_name TEXT,
            subject TEXT,
            summary TEXT,
            tags TEXT,
            consolidated INTEGER DEFAULT 0,
            batch_id TEXT
        );
    """)
    conn.close()


def _insert_memory(
    db_path: str,
    mem_id: str,
    content: str,
    memory_type: str,
    namespace: str = "test-project",
    branch: str = "",
    scope: str = "project",
    importance: float = 1.0,
    created_at: str = "2026-04-14T10:00:00+00:00",
    status: str = "active",
    deleted_at: str | None = None,
    meta: dict | None = None,
) -> None:
    """Insert a memory row into the test database."""
    normalized = " ".join(content.lower().split())
    c_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    meta_json = json.dumps(meta or {})
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO memories (id, content, memory_type, namespace, branch, scope, "
        "importance, created_at, status, deleted_at, content_hash, meta) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mem_id, content, memory_type, namespace, branch, scope,
            importance, created_at, status, deleted_at, c_hash, meta_json,
        ),
    )
    conn.commit()
    conn.close()


def _insert_citation(
    db_path: str,
    memory_id: str,
    file_path: str,
    line_range: str | None = None,
    content_snippet: str | None = None,
) -> None:
    """Insert a citation row into the test database."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO memory_citations (memory_id, file_path, line_range, content_snippet) "
        "VALUES (?, ?, ?, ?)",
        (memory_id, file_path, line_range, content_snippet),
    )
    conn.commit()
    conn.close()


def _insert_raw_event(
    db_path: str,
    session_id: str = "sess-1",
    project: str = "test-project",
    event_type: str = "observation",
    tool_name: str = "memory_store",
    subject: str = "test subject",
    summary: str = "test summary",
    tags: str = "tag1,tag2",
    branch: str = "main",
    consolidated: int = 0,
) -> None:
    """Insert a raw event row into the test database."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO raw_events (session_id, timestamp, project, branch, event_type, "
        "tool_name, subject, summary, tags, consolidated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id, "2026-04-14T10:00:00+00:00", project, branch,
            event_type, tool_name, subject, summary, tags, consolidated,
        ),
    )
    conn.commit()
    conn.close()


def _read_memory_file(path: str) -> tuple[dict, str]:
    """Read a memory markdown file and return (frontmatter_dict, body)."""
    import re

    with open(path, "r") as f:
        raw = f.read()
    match = re.match(r"\A---\n(.*?)\n---\n?(.*)", raw, re.DOTALL)
    assert match is not None, f"File at {path} has no frontmatter"
    fm_dict = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return fm_dict, body


# ---------------------------------------------------------------------------
# MigrationReport and VerificationReport dataclass tests
# ---------------------------------------------------------------------------


class TestMigrationDataModels:
    """Test data model construction and defaults for migration reports."""

    def test_migration_report_construction(self):
        from spellbook.memory.migration import MigrationReport

        report = MigrationReport(
            total_memories=10,
            migrated=8,
            skipped=1,
            archived=1,
            errors=["error one"],
            type_distribution={"project": 5, "user": 3},
        )
        assert report == MigrationReport(
            total_memories=10,
            migrated=8,
            skipped=1,
            archived=1,
            errors=["error one"],
            type_distribution={"project": 5, "user": 3},
        )

    def test_verification_report_construction(self):
        from spellbook.memory.migration import VerificationReport

        report = VerificationReport(
            sqlite_count=10,
            markdown_count=9,
            hash_matches=8,
            hash_mismatches=1,
            missing_in_markdown=["mem-id-1"],
        )
        assert report == VerificationReport(
            sqlite_count=10,
            markdown_count=9,
            hash_matches=8,
            hash_mismatches=1,
            missing_in_markdown=["mem-id-1"],
        )


# ---------------------------------------------------------------------------
# migrate_memories tests
# ---------------------------------------------------------------------------


class TestMigrateMemories:
    """Test SQLite to markdown memory migration."""

    def test_migrate_single_active_memory(self, tmp_path):
        """Migrate one active fact memory with no citations or tags."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        content = "We use exponential backoff with jitter for API retries."
        _insert_memory(
            db_path, "mem-1", content, "fact",
            branch="feature/retry",
            created_at="2026-04-14T10:00:00+00:00",
        )

        report = migrate_memories(db_path, output_dir)

        from spellbook.memory.migration import MigrationReport
        assert report == MigrationReport(
            total_memories=1,
            migrated=1,
            skipped=0,
            archived=0,
            errors=[],
            type_distribution={"project": 1},
        )

        # Verify the file was created in the project/ subdirectory
        project_dir = os.path.join(output_dir, "project")
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        assert len(md_files) == 1

        fm, body = _read_memory_file(os.path.join(project_dir, md_files[0]))
        assert body == content
        assert fm["type"] == "project"
        assert fm["kind"] == "fact"
        assert fm["content_hash"] == _content_hash(content)
        assert fm["branch"] == "feature/retry"
        assert str(fm["created"]) == "2026-04-14"

    def test_migrate_memory_type_to_kind_mapping(self, tmp_path):
        """Verify memory_type maps correctly to kind field."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        type_mapping = {
            "fact": "fact",
            "rule": "rule",
            "antipattern": "antipattern",
            "preference": "preference",
            "decision": "decision",
        }

        for i, (sqlite_type, expected_kind) in enumerate(type_mapping.items()):
            _insert_memory(
                db_path, f"mem-{i}", f"Content for {sqlite_type} type.",
                sqlite_type,
            )

        report = migrate_memories(db_path, output_dir)
        assert report.migrated == 5
        assert report.skipped == 0

        # Collect all written files and verify kinds
        written_kinds = set()
        for dirpath, _dirnames, filenames in os.walk(output_dir):
            for fname in filenames:
                if fname.endswith(".md"):
                    fm, _ = _read_memory_file(os.path.join(dirpath, fname))
                    written_kinds.add(fm["kind"])

        assert written_kinds == {"fact", "rule", "antipattern", "preference", "decision"}

    def test_migrate_type_inference_user(self, tmp_path):
        """Content mentioning user preferences infers type=user."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-user", "I prefer single bundled PRs for refactors.",
            "preference",
        )

        report = migrate_memories(db_path, output_dir)
        assert report.type_distribution == {"user": 1}

        # File should be in user/ subdirectory
        assert os.path.isdir(os.path.join(output_dir, "user"))
        md_files = [
            f for f in os.listdir(os.path.join(output_dir, "user"))
            if f.endswith(".md")
        ]
        assert len(md_files) == 1
        fm, _ = _read_memory_file(os.path.join(output_dir, "user", md_files[0]))
        assert fm["type"] == "user"

    def test_migrate_type_inference_feedback(self, tmp_path):
        """Content with rule-like language infers type=feedback."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-feedback",
            "Rule: always run tests before committing to main.",
            "rule",
        )

        report = migrate_memories(db_path, output_dir)
        assert report.type_distribution == {"feedback": 1}

        assert os.path.isdir(os.path.join(output_dir, "feedback"))

    def test_migrate_type_inference_reference(self, tmp_path):
        """Content mentioning URLs infers type=reference."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-ref",
            "Bugs are tracked in https://linear.app/team/ingest dashboard.",
            "fact",
        )

        report = migrate_memories(db_path, output_dir)
        assert report.type_distribution == {"reference": 1}

        assert os.path.isdir(os.path.join(output_dir, "reference"))

    def test_migrate_type_inference_default_project(self, tmp_path):
        """Content without special markers defaults to type=project."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-proj",
            "The deploy pipeline uses Docker containers.",
            "fact",
        )

        report = migrate_memories(db_path, output_dir)
        assert report.type_distribution == {"project": 1}

    def test_migrate_with_citations(self, tmp_path):
        """Citations from memory_citations table map to frontmatter citations."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        content = "Client retry logic uses exponential backoff."
        _insert_memory(db_path, "mem-cited", content, "fact")
        _insert_citation(db_path, "mem-cited", "src/api/client.py", "10-20", "retry code")
        _insert_citation(db_path, "mem-cited", "src/api/config.py")

        report = migrate_memories(db_path, output_dir)
        assert report.migrated == 1

        # Find the output file
        project_dir = os.path.join(output_dir, "project")
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        fm, _ = _read_memory_file(os.path.join(project_dir, md_files[0]))

        assert len(fm["citations"]) == 2
        citation_files = {c["file"] for c in fm["citations"]}
        assert citation_files == {"src/api/client.py", "src/api/config.py"}

    def test_migrate_with_tags_from_meta(self, tmp_path):
        """Tags extracted from the meta JSON field appear in frontmatter."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-tagged",
            "API rate limiting strategy details.",
            "fact",
            meta={"tags": ["api", "rate-limiting", "strategy"]},
        )

        report = migrate_memories(db_path, output_dir)
        assert report.migrated == 1

        project_dir = os.path.join(output_dir, "project")
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        fm, _ = _read_memory_file(os.path.join(project_dir, md_files[0]))

        assert fm["tags"] == ["api", "rate-limiting", "strategy"]

    def test_migrate_skips_empty_content(self, tmp_path):
        """Memories with empty content are skipped."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(db_path, "mem-empty", "", "fact")
        _insert_memory(
            db_path, "mem-whitespace", "   ", "fact",
        )
        _insert_memory(
            db_path, "mem-good", "Valid content here.", "fact",
        )

        report = migrate_memories(db_path, output_dir)
        assert report.total_memories == 3
        assert report.migrated == 1
        assert report.skipped == 2

    def test_migrate_deleted_memories_excluded_by_default(self, tmp_path):
        """Soft-deleted memories are not migrated when include_deleted=False."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(db_path, "mem-active", "Active memory.", "fact")
        _insert_memory(
            db_path, "mem-deleted", "Deleted memory.", "fact",
            status="deleted",
            deleted_at="2026-04-10T10:00:00+00:00",
        )

        report = migrate_memories(db_path, output_dir, include_deleted=False)
        assert report.migrated == 1
        assert report.archived == 0

        # No .archive/ directory should exist
        assert not os.path.exists(os.path.join(output_dir, ".archive"))

    def test_migrate_deleted_memories_to_archive(self, tmp_path):
        """Soft-deleted memories go to .archive/ when include_deleted=True."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(db_path, "mem-active", "Active memory content.", "fact")
        _insert_memory(
            db_path, "mem-deleted", "Deleted memory content.", "fact",
            status="deleted",
            deleted_at="2026-04-10T10:00:00+00:00",
        )

        report = migrate_memories(db_path, output_dir, include_deleted=True)
        assert report.migrated == 1
        assert report.archived == 1

        # Active memory in regular directory
        project_dir = os.path.join(output_dir, "project")
        assert len([f for f in os.listdir(project_dir) if f.endswith(".md")]) == 1

        # Deleted memory in .archive/
        archive_dir = os.path.join(output_dir, ".archive")
        assert os.path.isdir(archive_dir)
        archive_files = []
        for dirpath, _, filenames in os.walk(archive_dir):
            for f in filenames:
                if f.endswith(".md"):
                    archive_files.append(os.path.join(dirpath, f))
        assert len(archive_files) == 1

        fm, body = _read_memory_file(archive_files[0])
        assert body == "Deleted memory content."

    def test_migrate_content_hash_preservation(self, tmp_path):
        """Content hash in output matches SHA-256 of normalized content."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        content = "Hash preservation test with multiple   spaces."
        _insert_memory(db_path, "mem-hash", content, "fact")

        migrate_memories(db_path, output_dir)

        project_dir = os.path.join(output_dir, "project")
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        fm, _ = _read_memory_file(os.path.join(project_dir, md_files[0]))

        assert fm["content_hash"] == _content_hash(content)

    def test_migrate_slug_generation(self, tmp_path):
        """Slug is generated from content, kebab-case, no stopwords."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-slug",
            "We use exponential backoff with jitter for API retries.",
            "fact",
        )

        migrate_memories(db_path, output_dir)

        project_dir = os.path.join(output_dir, "project")
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        assert len(md_files) == 1
        slug = md_files[0].replace(".md", "")
        # Should contain significant words, kebab-case
        assert "-" in slug
        assert "exponential" in slug or "backoff" in slug

    def test_migrate_multiple_memories_mixed_types(self, tmp_path):
        """Multiple memories with different inferred types go to correct subdirs."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-proj",
            "The deploy pipeline uses containers.",
            "fact",
        )
        _insert_memory(
            db_path, "mem-user",
            "User prefers explicit code reviews.",
            "preference",
        )
        _insert_memory(
            db_path, "mem-ref",
            "Documentation at https://docs.example.com/api for reference.",
            "fact",
        )

        report = migrate_memories(db_path, output_dir)
        assert report.migrated == 3
        assert report.type_distribution == {"project": 1, "user": 1, "reference": 1}

    def test_migrate_importance_to_access_log(self, tmp_path):
        """High-importance memories create access log entries."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-important",
            "Critical fact about deployment.",
            "fact",
            importance=3.5,
        )
        _insert_memory(
            db_path, "mem-normal",
            "Normal fact about logging.",
            "fact",
            importance=1.0,
        )

        migrate_memories(db_path, output_dir)

        access_log_path = os.path.join(output_dir, ".access-log.json")
        assert os.path.exists(access_log_path)
        with open(access_log_path, "r") as f:
            access_data = json.load(f)

        # The high-importance memory should have access count reflecting importance
        # importance = 1.0 + 0.1 * count, so count = (3.5 - 1.0) / 0.1 = 25
        important_entries = [
            v for k, v in access_data.items() if v["count"] > 0
        ]
        assert len(important_entries) >= 1
        # The entry for the high-importance memory should have count = 25
        high_count = max(v["count"] for v in access_data.values())
        assert high_count == 25

    def test_migrate_scope_preserved(self, tmp_path):
        """Scope field is preserved in frontmatter."""
        from spellbook.memory.migration import migrate_memories

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(
            db_path, "mem-global",
            "User prefers dark mode in all projects.",
            "preference",
            scope="global",
        )

        migrate_memories(db_path, output_dir)

        user_dir = os.path.join(output_dir, "user")
        md_files = [f for f in os.listdir(user_dir) if f.endswith(".md")]
        fm, _ = _read_memory_file(os.path.join(user_dir, md_files[0]))
        assert fm["scope"] == "global"




# ---------------------------------------------------------------------------
# migrate_raw_events tests
# ---------------------------------------------------------------------------


class TestMigrateRawEvents:
    """Test raw event export to JSON."""

    def test_export_unconsolidated_events(self, tmp_path):
        """Unconsolidated raw events are exported as JSON."""
        from spellbook.memory.migration import migrate_raw_events

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_raw_event(db_path, summary="First observation", consolidated=0)
        _insert_raw_event(db_path, summary="Second observation", consolidated=0)
        _insert_raw_event(db_path, summary="Already consolidated", consolidated=1)

        count = migrate_raw_events(db_path, output_dir)
        assert count == 2

        events_file = os.path.join(output_dir, "raw_events.json")
        assert os.path.exists(events_file)
        with open(events_file, "r") as f:
            events = json.load(f)
        assert len(events) == 2
        summaries = {e["summary"] for e in events}
        assert summaries == {"First observation", "Second observation"}

    def test_export_no_events(self, tmp_path):
        """Returns 0 when there are no unconsolidated events."""
        from spellbook.memory.migration import migrate_raw_events

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        count = migrate_raw_events(db_path, output_dir)
        assert count == 0

    def test_export_event_fields(self, tmp_path):
        """Exported events contain all expected fields."""
        from spellbook.memory.migration import migrate_raw_events

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_raw_event(
            db_path,
            session_id="sess-abc",
            project="my-project",
            event_type="feedback",
            tool_name="memory_store",
            subject="retry pattern",
            summary="User corrected retry approach",
            tags="retry,api",
            branch="feature/retry",
        )

        migrate_raw_events(db_path, output_dir)

        with open(os.path.join(output_dir, "raw_events.json"), "r") as f:
            events = json.load(f)

        event = events[0]
        assert event == {
            "id": event["id"],  # auto-incremented, just verify it exists
            "session_id": "sess-abc",
            "timestamp": "2026-04-14T10:00:00+00:00",
            "project": "my-project",
            "branch": "feature/retry",
            "event_type": "feedback",
            "tool_name": "memory_store",
            "subject": "retry pattern",
            "summary": "User corrected retry approach",
            "tags": "retry,api",
        }


# ---------------------------------------------------------------------------
# verify_migration tests
# ---------------------------------------------------------------------------


class TestVerifyMigration:
    """Test migration verification."""

    def test_verify_clean_migration(self, tmp_path):
        """Verification passes for a correct migration."""
        from spellbook.memory.migration import migrate_memories, verify_migration

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(db_path, "mem-1", "First memory content.", "fact")
        _insert_memory(db_path, "mem-2", "Second memory content.", "fact")

        migrate_memories(db_path, output_dir)

        report = verify_migration(db_path, output_dir)
        assert report.sqlite_count == 2
        assert report.markdown_count == 2
        assert report.hash_matches == 2
        assert report.hash_mismatches == 0
        assert report.missing_in_markdown == []

    def test_verify_catches_missing_memories(self, tmp_path):
        """Verification detects memories in SQLite but not in markdown."""
        from spellbook.memory.migration import migrate_memories, verify_migration

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(db_path, "mem-1", "First memory content.", "fact")
        _insert_memory(db_path, "mem-2", "Second memory content.", "fact")

        migrate_memories(db_path, output_dir)

        # Delete one markdown file to simulate a missing migration
        project_dir = os.path.join(output_dir, "project")
        md_files = sorted(os.listdir(project_dir))
        os.unlink(os.path.join(project_dir, md_files[0]))

        report = verify_migration(db_path, output_dir)
        assert report.sqlite_count == 2
        assert report.markdown_count == 1
        assert report.hash_matches == 1
        assert report.hash_mismatches == 0
        assert len(report.missing_in_markdown) == 1

    def test_verify_with_no_memories(self, tmp_path):
        """Verification handles empty database gracefully."""
        from spellbook.memory.migration import verify_migration

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)
        os.makedirs(output_dir, exist_ok=True)

        report = verify_migration(db_path, output_dir)
        assert report.sqlite_count == 0
        assert report.markdown_count == 0
        assert report.hash_matches == 0
        assert report.hash_mismatches == 0
        assert report.missing_in_markdown == []

    def test_verify_detects_hash_mismatch(self, tmp_path):
        """Verification detects content hash mismatches."""
        from spellbook.memory.migration import migrate_memories, verify_migration

        db_path = str(tmp_path / "test.db")
        output_dir = str(tmp_path / "output")
        _create_test_db(db_path)

        _insert_memory(db_path, "mem-1", "Original content for hash test.", "fact")
        migrate_memories(db_path, output_dir)

        # Tamper with the markdown file content (change body but not hash)
        project_dir = os.path.join(output_dir, "project")
        md_files = [f for f in os.listdir(project_dir) if f.endswith(".md")]
        file_path = os.path.join(project_dir, md_files[0])
        with open(file_path, "r") as f:
            raw = f.read()
        # Replace body but keep frontmatter (including original hash)
        tampered = raw.replace(
            "Original content for hash test.",
            "TAMPERED content that does not match hash.",
        )
        with open(file_path, "w") as f:
            f.write(tampered)

        report = verify_migration(db_path, output_dir)
        assert report.hash_mismatches == 1
