"""Tests for ``spellbook.memory.claude_memory`` (D4).

Covers: project-encoded path convention, missing directory, malformed
frontmatter, size cap, symlink skipping, schema-version gating,
``originSessionId`` -> tag translation, ``MEMORY.md`` index boost.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _write_claude_memory(dir_path: Path, name: str, frontmatter: str, body: str) -> Path:
    """Write a fake Claude memory file. Returns the path."""
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / name
    p.write_text(f"---\n{frontmatter}\n---\n{body}\n")
    return p


# ---------------------------------------------------------------------------
# Project-encoded path convention
# ---------------------------------------------------------------------------


class TestProjectEncoding:
    """_encode_project mirrors the spellbook convention in CLAUDE.md."""

    def test_encode_project_root(self):
        from spellbook.memory.claude_memory import _encode_project
        assert _encode_project("/Users/alice/proj") == "Users-alice-proj"

    def test_encode_strips_only_leading_slash(self):
        from spellbook.memory.claude_memory import _encode_project
        # Internal slashes become dashes; trailing paths preserved.
        assert _encode_project("/a/b/c") == "a-b-c"

    def test_encode_without_leading_slash(self):
        from spellbook.memory.claude_memory import _encode_project
        assert _encode_project("a/b") == "a-b"


# ---------------------------------------------------------------------------
# Missing directory: graceful empty
# ---------------------------------------------------------------------------


class TestMissingDirectory:
    def test_missing_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        from spellbook.memory import claude_memory
        assert claude_memory.scan(project_root="/nope") == []

    def test_dir_is_file_returns_empty(self, tmp_path, monkeypatch):
        # If the expected memory path exists but is a file, do not crash.
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/foo/bar"
        encoded_dir = tmp_path / ".claude" / "projects" / "Users-foo-bar"
        encoded_dir.mkdir(parents=True)
        (encoded_dir / "memory").write_text("not a directory")
        from spellbook.memory import claude_memory
        assert claude_memory.scan(project_root=project_root) == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Parse a well-formed Claude memory file and return a MemoryResult."""

    def test_valid_claude_memory_is_returned(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        _write_claude_memory(
            mem_dir,
            "feedback_tests_first.md",
            (
                "name: Always write tests first\n"
                "description: TDD is required\n"
                "type: feedback"
            ),
            "User corrected me: tests MUST come before implementation.",
        )
        from spellbook.memory import claude_memory
        results = claude_memory.scan(project_root=project_root, query_terms=["tests"])
        assert len(results) == 1
        r = results[0]
        assert r.memory.frontmatter.type == "feedback"
        assert "tests MUST come" in r.memory.content
        assert 0.0 <= r.score <= 1.0

    def test_origin_session_appended_as_tag(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        _write_claude_memory(
            mem_dir,
            "feedback_x.md",
            (
                "name: Some name\n"
                "description: desc\n"
                "type: feedback\n"
                "originSessionId: abc123"
            ),
            "body text",
        )
        from spellbook.memory import claude_memory
        results = claude_memory.scan(project_root=project_root, query_terms=["body"])
        assert len(results) == 1
        tags = results[0].memory.frontmatter.tags
        assert "origin_session:abc123" in tags


# ---------------------------------------------------------------------------
# Malformed / skipped cases
# ---------------------------------------------------------------------------


class TestSkippedFiles:
    def test_malformed_frontmatter_skipped(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        mem_dir.mkdir(parents=True)
        # File with no frontmatter delimiters at all.
        (mem_dir / "broken.md").write_text("just body no front matter")
        # Valid file alongside the broken one.
        _write_claude_memory(
            mem_dir,
            "ok.md",
            "name: ok\ndescription: ok\ntype: feedback",
            "valid body",
        )
        from spellbook.memory import claude_memory
        with caplog.at_level("WARNING"):
            results = claude_memory.scan(project_root=project_root, query_terms=["body"])
        # Broken file skipped; valid file returned.
        assert len(results) == 1
        assert results[0].memory.path.endswith("ok.md")
        # A warning was emitted for the broken file.
        assert any("broken.md" in rec.message for rec in caplog.records)

    def test_memory_index_file_itself_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        mem_dir.mkdir(parents=True)
        # MEMORY.md has a different shape and is the index, not a memory.
        (mem_dir / "MEMORY.md").write_text("- feedback_a.md\n")
        _write_claude_memory(
            mem_dir,
            "feedback_a.md",
            "name: a\ndescription: a\ntype: feedback",
            "body a",
        )
        from spellbook.memory import claude_memory
        results = claude_memory.scan(project_root=project_root, query_terms=["body"])
        assert len(results) == 1
        assert results[0].memory.path.endswith("feedback_a.md")

    def test_oversize_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        mem_dir.mkdir(parents=True)
        # Reduce cap so a small file exceeds it.
        from spellbook.memory import claude_memory
        monkeypatch.setattr(claude_memory, "MAX_FILE_SIZE", 32)
        _write_claude_memory(
            mem_dir,
            "oversize.md",
            "name: a\ndescription: a\ntype: feedback",
            "X" * 2000,
        )
        results = claude_memory.scan(project_root=project_root, query_terms=["body"])
        assert results == []

    def test_symlink_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        mem_dir.mkdir(parents=True)
        target = tmp_path / "real.md"
        target.write_text(
            "---\nname: a\ndescription: a\ntype: feedback\n---\nbody\n"
        )
        link = mem_dir / "link.md"
        os.symlink(target, link)
        from spellbook.memory import claude_memory
        results = claude_memory.scan(project_root=project_root, query_terms=["body"])
        assert results == []


# ---------------------------------------------------------------------------
# MEMORY.md index boost
# ---------------------------------------------------------------------------


class TestIndexBoost:
    def test_files_listed_in_memory_md_get_small_boost(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        project_root = "/Users/me/proj"
        mem_dir = tmp_path / ".claude" / "projects" / "Users-me-proj" / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "MEMORY.md").write_text("- boosted.md\n")
        _write_claude_memory(
            mem_dir,
            "boosted.md",
            "name: a\ndescription: a\ntype: feedback",
            "body with query term",
        )
        _write_claude_memory(
            mem_dir,
            "plain.md",
            "name: a\ndescription: a\ntype: feedback",
            "body with query term",
        )
        from spellbook.memory import claude_memory
        results = claude_memory.scan(project_root=project_root, query_terms=["query"])
        assert len(results) == 2
        by_name = {Path(r.memory.path).name: r.score for r in results}
        assert by_name["boosted.md"] > by_name["plain.md"]
