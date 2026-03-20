"""Tests for MEMORY.md regenerator (spellbook/memory/bootstrap.py).

Tests the generate_memory_md function (content generation), _resolve_auto_memory_dir
(path resolution), _bootstrap_existing_memory_md (first-run capture), and
regenerate_memory_md_for_project (orchestrator).
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from spellbook.core.db import init_db, close_all_connections
from spellbook.memory.store import insert_memory, get_unconsolidated_events


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


@pytest.fixture
def auto_memory_dir(tmp_path):
    """Create a mock auto-memory directory structure."""
    memory_dir = tmp_path / ".claude" / "projects" / "-tmp-test" / "memory"
    memory_dir.mkdir(parents=True)
    return memory_dir


class TestGenerateMemoryMd:
    """generate_memory_md produces valid hybrid MEMORY.md content."""

    def test_with_memories(self, db):
        """Generates markdown with instruction header and memory summary."""
        from spellbook.memory.bootstrap import generate_memory_md

        insert_memory(
            db_path=db,
            content="Project uses FastAPI for REST endpoints",
            memory_type="fact",
            namespace="Users-alice-project",
            tags=["fastapi"],
            citations=[],
        )
        insert_memory(
            db_path=db,
            content="Always run pytest with -x flag",
            memory_type="convention",
            namespace="Users-alice-project",
            tags=["testing"],
            citations=[],
        )

        result = generate_memory_md(
            db_path=db,
            project_path="/Users/alice/project",
            namespace="Users-alice-project",
        )

        # Must contain the spellbook-managed header
        assert result.startswith("# Project Memory (spellbook-managed)")
        # Must contain MCP tool references in instructions
        assert "memory_store_memories" in result
        assert "memory_recall" in result
        # Must contain the actual memories
        assert "FastAPI" in result
        assert "pytest" in result
        # Must have Key Memories section
        assert "## Key Memories" in result

    def test_empty_store(self, db):
        """Generates instructions-only MEMORY.md when no memories exist."""
        from spellbook.memory.bootstrap import generate_memory_md

        result = generate_memory_md(
            db_path=db,
            project_path="/Users/alice/project",
            namespace="Users-alice-project",
        )

        assert result.startswith("# Project Memory (spellbook-managed)")
        assert "memory_store_memories" in result
        # No Key Memories section when empty
        assert "## Key Memories" not in result
        lines = result.strip().split("\n")
        assert len(lines) < 30

    def test_respects_200_line_limit(self, db):
        """Output stays within 200 lines even with many memories."""
        from spellbook.memory.bootstrap import generate_memory_md

        for i in range(50):
            insert_memory(
                db_path=db,
                content=f"Memory fact number {i}: this is a detailed description of something important about the project that spans multiple words and provides context",
                memory_type="fact",
                namespace="Users-alice-project",
                tags=[f"tag{i}"],
                citations=[],
            )

        result = generate_memory_md(
            db_path=db,
            project_path="/Users/alice/project",
            namespace="Users-alice-project",
        )

        line_count = len(result.split("\n"))
        assert line_count <= 200, f"MEMORY.md has {line_count} lines, exceeds 200 limit"

    def test_groups_by_memory_type(self, db):
        """Memories are grouped by memory_type in the output."""
        from spellbook.memory.bootstrap import generate_memory_md

        insert_memory(
            db_path=db,
            content="Always use type hints",
            memory_type="convention",
            namespace="Users-alice-project",
            tags=[],
            citations=[],
        )
        insert_memory(
            db_path=db,
            content="Database uses PostgreSQL",
            memory_type="fact",
            namespace="Users-alice-project",
            tags=[],
            citations=[],
        )

        result = generate_memory_md(
            db_path=db,
            project_path="/Users/alice/project",
            namespace="Users-alice-project",
        )

        # Both types should appear as subsection headers (### Fact, ### Convention)
        assert "### Fact" in result
        assert "### Convention" in result
        # Content from each type is present under correct grouping
        assert "- Database uses PostgreSQL" in result
        assert "- Always use type hints" in result

    def test_bootstrap_header_exact(self, db):
        """Bootstrap header starts with exact expected marker."""
        from spellbook.memory.bootstrap import generate_memory_md

        result = generate_memory_md(
            db_path=db,
            project_path="/Users/alice/project",
            namespace="Users-alice-project",
        )

        first_line = result.split("\n")[0]
        assert first_line == "# Project Memory (spellbook-managed)"


class TestResolveAutoMemoryDir:
    """_resolve_auto_memory_dir finds Claude Code's memory directory."""

    def test_dir_exists_with_leading_dash(self, tmp_path):
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        memory_dir = tmp_path / ".claude" / "projects" / "-Users-alice-project" / "memory"
        memory_dir.mkdir(parents=True)

        with patch("spellbook.memory.bootstrap.Path.home", return_value=tmp_path):
            result = _resolve_auto_memory_dir("/Users/alice/project")

        assert result == memory_dir

    def test_dir_exists_without_leading_dash(self, tmp_path):
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        memory_dir = tmp_path / ".claude" / "projects" / "Users-alice-project" / "memory"
        memory_dir.mkdir(parents=True)

        with patch("spellbook.memory.bootstrap.Path.home", return_value=tmp_path):
            result = _resolve_auto_memory_dir("/Users/alice/project")

        assert result == memory_dir

    def test_dir_missing_returns_none(self, tmp_path):
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        with patch("spellbook.memory.bootstrap.Path.home", return_value=tmp_path):
            result = _resolve_auto_memory_dir("/Users/alice/project")

        assert result is None

    def test_path_encoding_multi_segment(self, tmp_path):
        """Project path correctly encoded: leading / stripped, slashes to dashes."""
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        memory_dir = tmp_path / ".claude" / "projects" / "-Users-alice-Development-myproject" / "memory"
        memory_dir.mkdir(parents=True)

        with patch("spellbook.memory.bootstrap.Path.home", return_value=tmp_path):
            result = _resolve_auto_memory_dir("/Users/alice/Development/myproject")

        assert result == memory_dir

    def test_prefers_dash_prefix_over_no_prefix(self, tmp_path):
        """When both directories exist, prefers the dash-prefixed one (Claude Code format)."""
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        dash_dir = tmp_path / ".claude" / "projects" / "-Users-alice-project" / "memory"
        dash_dir.mkdir(parents=True)
        no_dash_dir = tmp_path / ".claude" / "projects" / "Users-alice-project" / "memory"
        no_dash_dir.mkdir(parents=True)

        with patch("spellbook.memory.bootstrap.Path.home", return_value=tmp_path):
            result = _resolve_auto_memory_dir("/Users/alice/project")

        assert result == dash_dir


class TestRegenerateMemoryMdForProject:
    """regenerate_memory_md_for_project writes MEMORY.md to auto-memory dir."""

    def test_writes_file_with_content(self, db, auto_memory_dir):
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        insert_memory(
            db_path=db,
            content="Test memory content",
            memory_type="fact",
            namespace="tmp-test",
            tags=[],
            citations=[],
        )

        with patch("spellbook.memory.bootstrap._resolve_auto_memory_dir", return_value=auto_memory_dir), \
             patch("spellbook.memory.bootstrap.get_db_path", return_value=Path(db)), \
             patch("spellbook.memory.bootstrap.encode_cwd", return_value="tmp-test"), \
             patch("spellbook.memory.bootstrap.resolve_repo_root", return_value="/tmp/test"), \
             patch("spellbook.memory.bootstrap.get_current_branch", return_value="main"):
            regenerate_memory_md_for_project("/tmp/test")

        memory_md = auto_memory_dir / "MEMORY.md"
        assert memory_md.exists()
        content = memory_md.read_text(encoding="utf-8")
        assert content.startswith("# Project Memory (spellbook-managed)")
        assert "Test memory content" in content

    def test_returns_silently_when_no_memory_dir(self):
        """No auto-memory directory means nothing to do."""
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        with patch("spellbook.memory.bootstrap._resolve_auto_memory_dir", return_value=None):
            # Should not raise
            regenerate_memory_md_for_project("/tmp/test")

    def test_fail_open_on_exception(self):
        """Exception in generation does not propagate (fail-open)."""
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        with patch("spellbook.memory.bootstrap._resolve_auto_memory_dir", side_effect=RuntimeError("boom")):
            # Should not raise
            regenerate_memory_md_for_project("/tmp/test")

    def test_creates_marker_file(self, db, auto_memory_dir):
        """After regeneration, .spellbook-bridge-initialized marker exists."""
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        with patch("spellbook.memory.bootstrap._resolve_auto_memory_dir", return_value=auto_memory_dir), \
             patch("spellbook.memory.bootstrap.get_db_path", return_value=Path(db)), \
             patch("spellbook.memory.bootstrap.encode_cwd", return_value="tmp-test"), \
             patch("spellbook.memory.bootstrap.resolve_repo_root", return_value="/tmp/test"), \
             patch("spellbook.memory.bootstrap.get_current_branch", return_value="main"):
            regenerate_memory_md_for_project("/tmp/test")

        marker = auto_memory_dir / ".spellbook-bridge-initialized"
        assert marker.exists()


class TestBootstrapExistingMemoryMd:
    """_bootstrap_existing_memory_md captures pre-bridge content once."""

    def test_captures_existing_content(self, db, auto_memory_dir):
        from spellbook.memory.bootstrap import _bootstrap_existing_memory_md

        memory_md = auto_memory_dir / "MEMORY.md"
        memory_md.write_text("# Pre-existing\n- Old fact 1\n- Old fact 2", encoding="utf-8")

        _bootstrap_existing_memory_md(auto_memory_dir, db, "tmp-test")

        # Marker was created
        marker = auto_memory_dir / ".spellbook-bridge-initialized"
        assert marker.exists()

        # Content was captured as raw event
        events = get_unconsolidated_events(db, limit=10)
        assert len(events) == 1
        assert events[0]["event_type"] == "auto_memory_bridge"
        assert events[0]["summary"] == "# Pre-existing\n- Old fact 1\n- Old fact 2"

    def test_skips_if_already_bootstrapped(self, db, auto_memory_dir):
        from spellbook.memory.bootstrap import _bootstrap_existing_memory_md

        marker = auto_memory_dir / ".spellbook-bridge-initialized"
        marker.write_text("initialized", encoding="utf-8")

        memory_md = auto_memory_dir / "MEMORY.md"
        memory_md.write_text("# Should not be captured", encoding="utf-8")

        _bootstrap_existing_memory_md(auto_memory_dir, db, "tmp-test")

        events = get_unconsolidated_events(db, limit=10)
        assert len(events) == 0

    def test_skips_spellbook_managed_content(self, db, auto_memory_dir):
        """Does not capture content that was already generated by spellbook."""
        from spellbook.memory.bootstrap import _bootstrap_existing_memory_md

        memory_md = auto_memory_dir / "MEMORY.md"
        memory_md.write_text(
            "# Project Memory (spellbook-managed)\n\nGenerated content",
            encoding="utf-8",
        )

        _bootstrap_existing_memory_md(auto_memory_dir, db, "tmp-test")

        events = get_unconsolidated_events(db, limit=10)
        assert len(events) == 0

        # Marker still created (even though content wasn't captured)
        marker = auto_memory_dir / ".spellbook-bridge-initialized"
        assert marker.exists()

    def test_no_memory_md_creates_marker_only(self, db, auto_memory_dir):
        """If no MEMORY.md exists, still creates marker (no events captured)."""
        from spellbook.memory.bootstrap import _bootstrap_existing_memory_md

        _bootstrap_existing_memory_md(auto_memory_dir, db, "tmp-test")

        events = get_unconsolidated_events(db, limit=10)
        assert len(events) == 0

        marker = auto_memory_dir / ".spellbook-bridge-initialized"
        assert marker.exists()
