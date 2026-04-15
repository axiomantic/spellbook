"""Tests for MEMORY.md regenerator (spellbook/memory/bootstrap.py).

Tests the generate_memory_md function (static template), _resolve_auto_memory_dir
(path resolution), _bootstrap_existing_memory_md (first-run capture), and
regenerate_memory_md_for_project (orchestrator).
"""

import bigfoot
import pytest
from dirty_equals import IsInstance
from pathlib import Path

from spellbook.core.db import init_db, close_all_connections
from spellbook.memory.store import get_unconsolidated_events


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
    """generate_memory_md returns a static redirect template."""

    def test_returns_string(self):
        """Returns a non-empty string."""
        from spellbook.memory.bootstrap import generate_memory_md

        result = generate_memory_md()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_expected_sections(self):
        """Template contains all key sections and tool references."""
        from spellbook.memory.bootstrap import generate_memory_md

        result = generate_memory_md()
        assert "# Spellbook Memory System" in result
        assert "## Retrieving Knowledge" in result
        assert "## Storing Knowledge" in result
        assert "## How It Works" in result
        assert "memory_recall" in result
        assert "memory_store" in result

    def test_accepts_kwargs_for_backward_compat(self):
        """Accepts arbitrary kwargs without error (backward compatibility)."""
        from spellbook.memory.bootstrap import generate_memory_md

        result = generate_memory_md(
            db_path="/fake/path",
            project_path="/fake/project",
            namespace="fake-namespace",
            branch="main",
            max_summary_lines=100,
        )
        assert "# Spellbook Memory System" in result

    def test_header_exact(self):
        """Template starts with exact expected header."""
        from spellbook.memory.bootstrap import generate_memory_md

        result = generate_memory_md()
        first_line = result.split("\n")[0]
        assert first_line == "# Spellbook Memory System"


class TestResolveAutoMemoryDir:
    """_resolve_auto_memory_dir finds Claude Code's memory directory."""

    def test_dir_exists_with_leading_dash(self, tmp_path):
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        memory_dir = tmp_path / ".claude" / "projects" / "-Users-alice-project" / "memory"
        memory_dir.mkdir(parents=True)

        mock_home = bigfoot.mock("spellbook.memory.bootstrap:Path.home")
        mock_home.__call__.returns(tmp_path)

        with bigfoot:
            result = _resolve_auto_memory_dir("/Users/alice/project")

        mock_home.__call__.assert_call(args=(), kwargs={})
        assert result == memory_dir

    def test_dir_exists_without_leading_dash(self, tmp_path):
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        memory_dir = tmp_path / ".claude" / "projects" / "Users-alice-project" / "memory"
        memory_dir.mkdir(parents=True)

        mock_home = bigfoot.mock("spellbook.memory.bootstrap:Path.home")
        mock_home.__call__.returns(tmp_path)

        with bigfoot:
            result = _resolve_auto_memory_dir("/Users/alice/project")

        mock_home.__call__.assert_call(args=(), kwargs={})
        assert result == memory_dir

    def test_dir_missing_returns_none(self, tmp_path):
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        mock_home = bigfoot.mock("spellbook.memory.bootstrap:Path.home")
        mock_home.__call__.returns(tmp_path)

        with bigfoot:
            result = _resolve_auto_memory_dir("/Users/alice/project")

        mock_home.__call__.assert_call(args=(), kwargs={})
        assert result is None

    def test_path_encoding_multi_segment(self, tmp_path):
        """Project path correctly encoded: leading / stripped, slashes to dashes."""
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        memory_dir = tmp_path / ".claude" / "projects" / "-Users-alice-Development-myproject" / "memory"
        memory_dir.mkdir(parents=True)

        mock_home = bigfoot.mock("spellbook.memory.bootstrap:Path.home")
        mock_home.__call__.returns(tmp_path)

        with bigfoot:
            result = _resolve_auto_memory_dir("/Users/alice/Development/myproject")

        mock_home.__call__.assert_call(args=(), kwargs={})
        assert result == memory_dir

    def test_prefers_dash_prefix_over_no_prefix(self, tmp_path):
        """When both directories exist, prefers the dash-prefixed one (Claude Code format)."""
        from spellbook.memory.bootstrap import _resolve_auto_memory_dir

        dash_dir = tmp_path / ".claude" / "projects" / "-Users-alice-project" / "memory"
        dash_dir.mkdir(parents=True)
        no_dash_dir = tmp_path / ".claude" / "projects" / "Users-alice-project" / "memory"
        no_dash_dir.mkdir(parents=True)

        mock_home = bigfoot.mock("spellbook.memory.bootstrap:Path.home")
        mock_home.__call__.returns(tmp_path)

        with bigfoot:
            result = _resolve_auto_memory_dir("/Users/alice/project")

        mock_home.__call__.assert_call(args=(), kwargs={})
        assert result == dash_dir


class TestRegenerateMemoryMdForProject:
    """regenerate_memory_md_for_project writes MEMORY.md to auto-memory dir."""

    def test_writes_file_with_template(self, db, auto_memory_dir):
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        mock_resolve = bigfoot.mock("spellbook.memory.bootstrap:_resolve_auto_memory_dir")
        mock_resolve.__call__.returns(auto_memory_dir)
        mock_db = bigfoot.mock("spellbook.memory.bootstrap:get_db_path")
        mock_db.__call__.returns(Path(db))
        mock_encode = bigfoot.mock("spellbook.memory.bootstrap:encode_cwd")
        mock_encode.__call__.returns("tmp-test")

        with bigfoot:
            regenerate_memory_md_for_project("/tmp/test")

        mock_resolve.__call__.assert_call(args=("/tmp/test",), kwargs={})
        mock_db.__call__.assert_call(args=(), kwargs={})
        mock_encode.__call__.assert_call(args=("/tmp/test",), kwargs={})

        memory_md = auto_memory_dir / "MEMORY.md"
        assert memory_md.exists()
        content = memory_md.read_text(encoding="utf-8")
        assert content.startswith("# Spellbook Memory System")
        assert "memory_recall" in content
        assert "memory_store" in content

    def test_returns_silently_when_no_memory_dir(self):
        """No auto-memory directory means nothing to do."""
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        mock_resolve = bigfoot.mock("spellbook.memory.bootstrap:_resolve_auto_memory_dir")
        mock_resolve.__call__.returns(None)

        with bigfoot:
            # Should not raise
            regenerate_memory_md_for_project("/tmp/test")

        mock_resolve.__call__.assert_call(args=("/tmp/test",), kwargs={})

    def test_fail_open_on_exception(self):
        """Exception in generation does not propagate (fail-open)."""
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        mock_resolve = bigfoot.mock("spellbook.memory.bootstrap:_resolve_auto_memory_dir")
        mock_resolve.__call__.raises(RuntimeError("boom"))

        with bigfoot:
            # Should not raise
            regenerate_memory_md_for_project("/tmp/test")

        mock_resolve.__call__.assert_call(
            args=("/tmp/test",), kwargs={}, raised=IsInstance(RuntimeError),
        )

    def test_creates_marker_file(self, db, auto_memory_dir):
        """After regeneration, .spellbook-bridge-initialized marker exists."""
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        mock_resolve = bigfoot.mock("spellbook.memory.bootstrap:_resolve_auto_memory_dir")
        mock_resolve.__call__.returns(auto_memory_dir)
        mock_db = bigfoot.mock("spellbook.memory.bootstrap:get_db_path")
        mock_db.__call__.returns(Path(db))
        mock_encode = bigfoot.mock("spellbook.memory.bootstrap:encode_cwd")
        mock_encode.__call__.returns("tmp-test")

        with bigfoot:
            regenerate_memory_md_for_project("/tmp/test")

        mock_resolve.__call__.assert_call(args=("/tmp/test",), kwargs={})
        mock_db.__call__.assert_call(args=(), kwargs={})
        mock_encode.__call__.assert_call(args=("/tmp/test",), kwargs={})

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
