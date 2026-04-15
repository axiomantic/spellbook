"""Tests for memory tools integration layer.

Tests the new file-based memory tool functions that wrap filestore operations,
backward-compatibility shims for old tool names, and the _get_memory_dir helper.

TDD RED phase: all tests written before implementation.
"""

import datetime
import hashlib
import json
import os

import pytest
import yaml

from tests._memory_marker import requires_memory_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Mirror the content hash logic used by filestore."""
    normalized = " ".join(content.lower().split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _write_memory_file(path: str, type_: str, content: str, **extra_fm):
    """Write a minimal memory file for test setup."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fm = {
        "type": type_,
        "created": datetime.date(2026, 4, 14),
        "content_hash": _content_hash(content),
    }
    fm.update(extra_fm)
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    with open(path, "w") as f:
        f.write(f"---\n{yaml_str}---\n\n{content}\n")


# ---------------------------------------------------------------------------
# _get_memory_dir
# ---------------------------------------------------------------------------


class TestGetMemoryDir:
    """Test _get_memory_dir returns correct paths for project and global scope."""

    def test_project_scope_encodes_namespace(self):
        from spellbook.memory.tools import _get_memory_dir

        result = _get_memory_dir("/Users/alice/myproject", scope="project")
        expected = os.path.expanduser("~/.local/spellbook/memories/Users-alice-myproject")
        assert result == expected

    def test_global_scope_returns_global_dir(self):
        from spellbook.memory.tools import _get_memory_dir

        result = _get_memory_dir("anything", scope="global")
        expected = os.path.expanduser("~/.local/spellbook/memories/_global")
        assert result == expected

    def test_project_scope_strips_leading_separator(self):
        from spellbook.memory.tools import _get_memory_dir

        result = _get_memory_dir("/Users/bob/project", scope="project")
        # Leading / becomes leading - which is stripped
        assert not os.path.basename(result).startswith("-")

    def test_project_scope_replaces_slashes(self):
        from spellbook.memory.tools import _get_memory_dir

        result = _get_memory_dir("/a/b/c", scope="project")
        basename = os.path.basename(result)
        assert "/" not in basename
        assert basename == "a-b-c"


# ---------------------------------------------------------------------------
# do_memory_store
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestDoMemoryStore:
    """Test do_memory_store creates markdown files via filestore."""

    def test_store_creates_file(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_store, _get_memory_dir

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        result = do_memory_store(
            content="The retry module uses exponential backoff with jitter for all HTTP calls",
            type="project",
            kind="fact",
            citations=None,
            tags=["retry", "http"],
            scope="project",
            namespace="/Users/test/proj",
        )

        assert result["status"] == "stored"
        assert result["path"].endswith(".md")
        assert os.path.exists(result["path"])

        # Verify file content structure (frontmatter + body)
        from spellbook.memory.frontmatter import parse_frontmatter

        fm, body = parse_frontmatter(result["path"])
        assert fm.type == "project"
        assert fm.kind == "fact"
        assert fm.tags == ["retry", "http"]
        assert fm.content_hash is not None
        assert body.strip() == "The retry module uses exponential backoff with jitter for all HTTP calls"

    def test_store_dedup_returns_existing(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        content = "SQLite WAL mode allows concurrent readers with a single writer"
        result1 = do_memory_store(
            content=content, type="project", namespace="/test",
        )
        result2 = do_memory_store(
            content=content, type="project", namespace="/test",
        )

        assert result1["path"] == result2["path"]
        assert result2["status"] == "stored"

    def test_store_with_citations(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        result = do_memory_store(
            content="The config module reads from spellbook.json with fallback to defaults",
            type="project",
            kind="fact",
            citations=[{"file": "spellbook/core/config.py", "symbol": "config_get"}],
            tags=["config"],
            scope="project",
            namespace="/test",
        )

        assert result["status"] == "stored"
        # Verify citation is in frontmatter with full structure
        from spellbook.memory.frontmatter import parse_frontmatter

        fm, body = parse_frontmatter(result["path"])
        assert len(fm.citations) == 1
        assert fm.citations[0].file == "spellbook/core/config.py"
        assert fm.citations[0].symbol == "config_get"
        assert fm.tags == ["config"]


# ---------------------------------------------------------------------------
# do_memory_recall
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestDoMemoryRecall:
    """Test do_memory_recall finds stored memories via filestore search."""

    def test_recall_finds_stored_memory(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_recall

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        # Seed a memory file
        _write_memory_file(
            os.path.join(memory_dir, "project", "sqlite-wal-concurrent.md"),
            type_="project",
            content="SQLite WAL mode allows concurrent readers with a single writer",
            tags=["sqlite", "database"],
        )

        result = do_memory_recall(
            query="SQLite WAL",
            namespace="/test",
            limit=10,
            scope="project",
        )

        assert result["count"] == 1
        mem = result["memories"][0]
        assert mem["content"].strip() == "SQLite WAL mode allows concurrent readers with a single writer"
        assert "score" in mem
        assert isinstance(mem["score"], float)
        assert mem["score"] > 0.0
        assert "path" in mem

    def test_recall_empty_query_returns_all(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_recall

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        _write_memory_file(
            os.path.join(memory_dir, "project", "test-mem.md"),
            type_="project",
            content="Some test memory content that should be returned for empty queries",
        )

        result = do_memory_recall(
            query="",
            namespace="/test",
            limit=10,
            scope="project",
        )

        assert result["count"] == 1
        assert result["memories"][0]["content"].strip() == "Some test memory content that should be returned for empty queries"

    def test_recall_with_tags_filter(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_recall

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        _write_memory_file(
            os.path.join(memory_dir, "project", "tagged-memory.md"),
            type_="project",
            content="This memory has specific tags for filtering tests",
            tags=["special-tag", "test"],
        )
        _write_memory_file(
            os.path.join(memory_dir, "project", "untagged-memory.md"),
            type_="project",
            content="This memory has no matching tags at all here",
            tags=["other"],
        )

        result = do_memory_recall(
            query="memory",
            namespace="/test",
            tags=["special-tag"],
            scope="project",
        )

        assert result["count"] == 1
        mem = result["memories"][0]
        assert mem["content"].strip() == "This memory has specific tags for filtering tests"

    def test_recall_with_file_path_filter(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_recall

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        _write_memory_file(
            os.path.join(memory_dir, "project", "config-memory.md"),
            type_="project",
            content="Config module uses JSON with fallback defaults",
            citations=[{"file": "spellbook/core/config.py"}],
        )

        result = do_memory_recall(
            query="config",
            namespace="/test",
            file_path="spellbook/core/config.py",
            scope="project",
        )

        assert result["count"] == 1
        mem = result["memories"][0]
        assert mem["content"].strip() == "Config module uses JSON with fallback defaults"
        assert "path" in mem

    def test_recall_returns_score_and_content(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_recall

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        _write_memory_file(
            os.path.join(memory_dir, "project", "scored-memory.md"),
            type_="project",
            content="The scoring system uses BM25 with temporal decay and branch multiplier",
            tags=["scoring"],
        )

        result = do_memory_recall(
            query="scoring BM25",
            namespace="/test",
            scope="project",
        )

        assert result["count"] == 1
        mem = result["memories"][0]
        assert mem["content"].strip() == "The scoring system uses BM25 with temporal decay and branch multiplier"
        assert "score" in mem
        assert "path" in mem
        assert isinstance(mem["score"], float)
        assert mem["score"] > 0.1  # Direct match should score meaningfully, not near-zero


# ---------------------------------------------------------------------------
# do_memory_forget
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestDoMemoryForget:
    """Test do_memory_forget archives or deletes a memory file."""

    def test_forget_archives_file(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_forget

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        mem_path = os.path.join(memory_dir, "project", "to-forget.md")
        _write_memory_file(mem_path, type_="project", content="This memory will be archived")

        result = do_memory_forget(
            memory_id_or_query=mem_path,
            namespace="/test",
            archive=True,
        )

        assert result["status"] == "archived"
        assert not os.path.exists(mem_path)
        # Should exist in .archive/
        archive_path = os.path.join(memory_dir, ".archive", "project", "to-forget.md")
        assert os.path.exists(archive_path)

    def test_forget_permanent_delete(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_forget

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        mem_path = os.path.join(memory_dir, "project", "to-delete.md")
        _write_memory_file(mem_path, type_="project", content="This memory will be permanently deleted")

        result = do_memory_forget(
            memory_id_or_query=mem_path,
            namespace="/test",
            archive=False,
        )

        assert result["status"] == "deleted"
        assert not os.path.exists(mem_path)

    def test_forget_nonexistent_returns_not_found(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_forget

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        result = do_memory_forget(
            memory_id_or_query="/nonexistent/path.md",
            namespace="/test",
        )

        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# do_memory_sync
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestDoMemorySync:
    """Test do_memory_sync runs sync pipeline and returns a plan."""

    def test_sync_returns_plan_structure(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_sync

        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root, exist_ok=True)
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        # Create a source file
        src_file = os.path.join(project_root, "src", "main.py")
        os.makedirs(os.path.dirname(src_file), exist_ok=True)
        with open(src_file, "w") as f:
            f.write("def main(): pass\n")

        # Create a memory citing that file
        _write_memory_file(
            os.path.join(memory_dir, "project", "main-function.md"),
            type_="project",
            content="The main function is the entry point for the application",
            citations=[{"file": "src/main.py", "symbol": "main"}],
        )

        result = do_memory_sync(
            namespace="/test",
            project_root=project_root,
            changed_files=["src/main.py"],
        )

        assert result["status"] == "plan_ready"
        assert "factcheck_items" in result
        assert "prompt_template" in result
        assert "stats" in result
        assert isinstance(result["factcheck_items"], list)

    def test_sync_no_changes_returns_empty_plan(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_sync

        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root, exist_ok=True)
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        result = do_memory_sync(
            namespace="/test",
            project_root=project_root,
            changed_files=[],
        )

        assert result["status"] == "plan_ready"
        assert result["factcheck_items"] == []


# ---------------------------------------------------------------------------
# do_memory_verify
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestDoMemoryVerify:
    """Test do_memory_verify returns verification context."""

    def test_verify_returns_context(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_verify

        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        # Create a cited file
        cited_file = os.path.join(project_root, "src", "config.py")
        os.makedirs(os.path.dirname(cited_file), exist_ok=True)
        with open(cited_file, "w") as f:
            f.write("def config_get(): pass\n")

        # Create memory with citation
        mem_path = os.path.join(memory_dir, "project", "config-fact.md")
        _write_memory_file(
            mem_path,
            type_="project",
            content="The config_get function reads from spellbook.json",
            citations=[{"file": "src/config.py", "symbol": "config_get"}],
        )

        result = do_memory_verify(
            memory_path=mem_path,
            namespace="/test",
            project_root=project_root,
        )

        assert result["status"] == "context_ready"
        assert result["cited_files_exist"]["src/config.py"] is True
        assert "memory_content" in result

    def test_verify_detects_missing_file(self, tmp_path, monkeypatch):
        from spellbook.memory.tools import do_memory_verify

        memory_dir = str(tmp_path / "memories")
        project_root = str(tmp_path / "project")
        os.makedirs(project_root, exist_ok=True)
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        mem_path = os.path.join(memory_dir, "project", "stale-fact.md")
        _write_memory_file(
            mem_path,
            type_="project",
            content="The old_module.py handles legacy requests",
            citations=[{"file": "src/old_module.py"}],
        )

        result = do_memory_verify(
            memory_path=mem_path,
            namespace="/test",
            project_root=project_root,
        )

        assert result["status"] == "context_ready"
        assert result["cited_files_exist"]["src/old_module.py"] is False


# ---------------------------------------------------------------------------
# do_memory_review_events
# ---------------------------------------------------------------------------


@requires_memory_tools
class TestDoMemoryReviewEvents:
    """Test do_memory_review_events returns pending raw events."""

    def test_review_events_delegates_to_get_unconsolidated(self, tmp_path, monkeypatch):
        """Verify do_memory_review_events calls the SQLite event store."""
        import bigfoot

        from spellbook.memory.tools import do_memory_review_events

        # Must mock where the name is looked up: tools module holds its own reference
        mock_get_uncons = bigfoot.mock("spellbook.memory.tools:get_unconsolidated_events")
        mock_get_uncons.returns([
            {
                "id": 1,
                "session_id": "sess-1",
                "timestamp": "2026-04-14T10:00:00Z",
                "project": "test",
                "event_type": "tool_use",
                "tool_name": "Read",
                "subject": "config.py",
                "summary": "Read: config.py",
                "tags": "read",
            },
        ])

        mock_db_path = bigfoot.mock("spellbook.memory.tools:_get_db_path")
        mock_db_path.returns("/tmp/fake.db")

        # Mock build_consolidation_prompt since it's called on non-empty events
        mock_prompt = bigfoot.mock("spellbook.memory.tools:build_consolidation_prompt")
        mock_prompt.returns("Synthesize these events into memories.")

        with bigfoot:
            result = do_memory_review_events(namespace="test-project", limit=50)

        # Assert in execution order: _get_db_path -> get_unconsolidated_events -> build_consolidation_prompt
        mock_db_path.assert_call(args=(), kwargs={})
        mock_get_uncons.assert_call(
            args=("/tmp/fake.db",),
            kwargs={"limit": 50, "namespace": "test-project"},
        )
        mock_prompt.assert_call(
            args=([
                {
                    "id": 1,
                    "session_id": "sess-1",
                    "timestamp": "2026-04-14T10:00:00Z",
                    "project": "test",
                    "event_type": "tool_use",
                    "tool_name": "Read",
                    "subject": "config.py",
                    "summary": "Read: config.py",
                    "tags": "read",
                },
            ],),
            kwargs={},
        )

        assert result["count"] == 1
        assert result["events"][0]["id"] == 1
        assert result["events"][0]["summary"] == "Read: config.py"
        assert result["consolidation_prompt"] == "Synthesize these events into memories."

