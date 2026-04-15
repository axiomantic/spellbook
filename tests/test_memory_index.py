"""Tests for spellbook.memory.memory_index sidecar index."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_memory_file(
    memory_dir: Path,
    rel_path: str,
    content: str,
    fm_overrides: dict | None = None,
) -> Path:
    """Write a minimal memory markdown file with YAML frontmatter."""
    from spellbook.memory.frontmatter import write_memory_file
    from spellbook.memory.models import MemoryFrontmatter
    from spellbook.memory.utils import content_hash

    full_path = memory_dir / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    fm_kwargs = dict(
        type="project",
        created=date(2026, 4, 14),
        kind="fact",
        citations=[],
        tags=[],
        scope="project",
        branch=None,
        confidence="high",
        content_hash=content_hash(content),
    )
    if fm_overrides:
        fm_kwargs.update(fm_overrides)
    fm = MemoryFrontmatter(**fm_kwargs)
    write_memory_file(str(full_path), fm, content)
    return full_path


def _frontmatter_for(content: str, **overrides):
    from spellbook.memory.models import MemoryFrontmatter
    from spellbook.memory.utils import content_hash

    kwargs = dict(
        type="project",
        created=date(2026, 4, 14),
        kind="fact",
        citations=[],
        tags=[],
        scope="project",
        branch=None,
        confidence="high",
        content_hash=content_hash(content),
    )
    kwargs.update(overrides)
    return MemoryFrontmatter(**kwargs)


# ---------------------------------------------------------------------------
# record_store / record_delete
# ---------------------------------------------------------------------------


class TestRecordStore:
    def test_record_store_adds_entry(self, tmp_path):
        from spellbook.memory import memory_index

        content = "alpha"
        fm = _frontmatter_for(content)
        memory_index.record_store(
            str(tmp_path),
            "project/alpha.md",
            fm,
            fm.content_hash,
            mtime_ns=1234567890,
        )

        index_path = tmp_path / ".memory-index.json"
        data = json.loads(index_path.read_text())
        assert data == {
            "version": 1,
            "entries": {
                "project/alpha.md": {
                    "content_hash": fm.content_hash,
                    "type": "project",
                    "kind": "fact",
                    "created": "2026-04-14",
                    "mtime_ns": 1234567890,
                }
            },
        }


class TestRecordDelete:
    def test_record_delete_removes_entry(self, tmp_path):
        from spellbook.memory import memory_index

        fm_a = _frontmatter_for("alpha")
        fm_b = _frontmatter_for("beta")
        memory_index.record_store(
            str(tmp_path), "project/alpha.md", fm_a, fm_a.content_hash, mtime_ns=1
        )
        memory_index.record_store(
            str(tmp_path), "project/beta.md", fm_b, fm_b.content_hash, mtime_ns=2
        )

        memory_index.record_delete(str(tmp_path), "project/alpha.md")

        data = json.loads((tmp_path / ".memory-index.json").read_text())
        assert data == {
            "version": 1,
            "entries": {
                "project/beta.md": {
                    "content_hash": fm_b.content_hash,
                    "type": "project",
                    "kind": "fact",
                    "created": "2026-04-14",
                    "mtime_ns": 2,
                }
            },
        }

    def test_record_delete_missing_is_noop(self, tmp_path):
        from spellbook.memory import memory_index

        # Should not raise even with no index yet.
        memory_index.record_delete(str(tmp_path), "project/ghost.md")

        # Should produce an empty index file.
        data = json.loads((tmp_path / ".memory-index.json").read_text())
        assert data == {"version": 1, "entries": {}}


# ---------------------------------------------------------------------------
# find_by_hash
# ---------------------------------------------------------------------------


class TestFindByHash:
    def test_find_by_hash_returns_all_matches(self, tmp_path):
        from spellbook.memory import memory_index

        # Two entries share the same content_hash (possible across scopes / types).
        fm_a = _frontmatter_for("shared", type="project")
        fm_b = _frontmatter_for("shared", type="reference")
        shared_hash = fm_a.content_hash
        assert fm_b.content_hash == shared_hash

        memory_index.record_store(
            str(tmp_path), "project/a.md", fm_a, shared_hash, mtime_ns=1
        )
        memory_index.record_store(
            str(tmp_path), "reference/b.md", fm_b, shared_hash, mtime_ns=2
        )
        fm_c = _frontmatter_for("other")
        memory_index.record_store(
            str(tmp_path), "project/c.md", fm_c, fm_c.content_hash, mtime_ns=3
        )

        matches = memory_index.find_by_hash(str(tmp_path), shared_hash)
        assert sorted(matches) == ["project/a.md", "reference/b.md"]

    def test_find_by_hash_empty_on_miss(self, tmp_path):
        from spellbook.memory import memory_index

        fm = _frontmatter_for("alpha")
        memory_index.record_store(
            str(tmp_path), "project/a.md", fm, fm.content_hash, mtime_ns=1
        )

        matches = memory_index.find_by_hash(str(tmp_path), "sha256:nomatch")
        assert matches == []


# ---------------------------------------------------------------------------
# list_entries
# ---------------------------------------------------------------------------


class TestListEntries:
    def test_list_entries_sorted_by_created_desc(self, tmp_path):
        from spellbook.memory import memory_index

        fm_old = _frontmatter_for("old", created=date(2024, 1, 1))
        fm_mid = _frontmatter_for("mid", created=date(2025, 6, 15))
        fm_new = _frontmatter_for("new", created=date(2026, 4, 14))

        memory_index.record_store(
            str(tmp_path), "project/old.md", fm_old, fm_old.content_hash, mtime_ns=1
        )
        memory_index.record_store(
            str(tmp_path), "project/new.md", fm_new, fm_new.content_hash, mtime_ns=3
        )
        memory_index.record_store(
            str(tmp_path), "project/mid.md", fm_mid, fm_mid.content_hash, mtime_ns=2
        )

        entries = memory_index.list_entries(str(tmp_path))
        assert entries == [
            {
                "rel_path": "project/new.md",
                "content_hash": fm_new.content_hash,
                "type": "project",
                "kind": "fact",
                "created": "2026-04-14",
                "mtime_ns": 3,
            },
            {
                "rel_path": "project/mid.md",
                "content_hash": fm_mid.content_hash,
                "type": "project",
                "kind": "fact",
                "created": "2025-06-15",
                "mtime_ns": 2,
            },
            {
                "rel_path": "project/old.md",
                "content_hash": fm_old.content_hash,
                "type": "project",
                "kind": "fact",
                "created": "2024-01-01",
                "mtime_ns": 1,
            },
        ]

    def test_list_entries_empty_when_no_index(self, tmp_path):
        from spellbook.memory import memory_index

        entries = memory_index.list_entries(str(tmp_path))
        assert entries == []


# ---------------------------------------------------------------------------
# rebuild_if_stale
# ---------------------------------------------------------------------------


class TestRebuildIfStale:
    def test_rebuild_detects_new_file_on_disk(self, tmp_path):
        from spellbook.memory import memory_index

        # Write a memory file WITHOUT going through record_store.
        full = _write_memory_file(tmp_path, "project/sneaked.md", "hello world")
        stat = full.stat()

        memory_index.rebuild_if_stale(str(tmp_path), force=True)

        data = json.loads((tmp_path / ".memory-index.json").read_text())
        from spellbook.memory.utils import content_hash as _ch

        assert data == {
            "version": 1,
            "entries": {
                "project/sneaked.md": {
                    "content_hash": _ch("hello world"),
                    "type": "project",
                    "kind": "fact",
                    "created": "2026-04-14",
                    "mtime_ns": stat.st_mtime_ns,
                }
            },
        }

    def test_rebuild_detects_deleted_file(self, tmp_path):
        from spellbook.memory import memory_index

        fm = _frontmatter_for("alpha")
        memory_index.record_store(
            str(tmp_path),
            "project/alpha.md",
            fm,
            fm.content_hash,
            mtime_ns=1,
        )
        # Record a second real file that we'll delete outside the index.
        full = _write_memory_file(tmp_path, "project/beta.md", "beta content")
        stat = full.stat()
        fm_b = _frontmatter_for("beta content")
        memory_index.record_store(
            str(tmp_path),
            "project/beta.md",
            fm_b,
            fm_b.content_hash,
            mtime_ns=stat.st_mtime_ns,
        )

        # Remove beta.md from disk without updating the index.
        full.unlink()

        memory_index.rebuild_if_stale(str(tmp_path), force=True)

        data = json.loads((tmp_path / ".memory-index.json").read_text())
        # alpha.md was never written to disk so it also drops out of the index.
        # beta.md is gone. Result: empty entries.
        assert data == {"version": 1, "entries": {}}

    def test_rebuild_noop_when_in_sync(self, tmp_path):
        from spellbook.memory import memory_index

        # Write a real file AND record it in the index with the true mtime.
        full = _write_memory_file(tmp_path, "project/alpha.md", "alpha content")
        stat = full.stat()
        fm = _frontmatter_for("alpha content")
        memory_index.record_store(
            str(tmp_path),
            "project/alpha.md",
            fm,
            fm.content_hash,
            mtime_ns=stat.st_mtime_ns,
        )

        index_path = tmp_path / ".memory-index.json"
        index_mtime_before = index_path.stat().st_mtime_ns

        # Now force rebuild-check; should detect in-sync and not rewrite.
        memory_index.rebuild_if_stale(str(tmp_path), force=True)

        index_mtime_after = index_path.stat().st_mtime_ns
        assert index_mtime_after == index_mtime_before
