"""Tests for the import migration script."""

import subprocess
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

# The script is not a module we import; we test it by importing its functions
# after adding scripts/ to sys.path, or by running it as a subprocess.

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "migrate_imports.py"


def _load_migrate_module():
    """Load migrate_imports.py as a module for unit testing."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("migrate_imports", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDryRun:
    """Test that --dry-run mode reports changes without writing."""

    def test_dry_run_does_not_modify_file(self, tmp_path):
        """Dry-run should report what would change but not modify files."""
        test_file = tmp_path / "example.py"
        original = "from spellbook_mcp.db import get_db\n"
        test_file.write_text(original)

        mod = _load_migrate_module()
        changes = mod.migrate_file(str(test_file), dry_run=True)

        assert len(changes) > 0, "Should report at least one change"
        assert test_file.read_text() == original, "File should not be modified in dry-run"

    def test_dry_run_cli_flag(self, tmp_path):
        """Test that --dry-run works as a CLI flag."""
        test_file = tmp_path / "example.py"
        original = "from spellbook_mcp.db import get_db\n"
        test_file.write_text(original)

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--dry-run", "--file", str(test_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert test_file.read_text() == original, "File should not be modified"


class TestPythonImportRewriting:
    """Test rewriting of Python import statements."""

    def test_from_import(self, tmp_path):
        """Rewrite 'from spellbook_mcp.db import X' to new namespace."""
        test_file = tmp_path / "example.py"
        test_file.write_text("from spellbook_mcp.db import get_db\n")

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == "from spellbook.db import get_db\n"

    def test_import_statement(self, tmp_path):
        """Rewrite 'import spellbook_mcp.db'."""
        test_file = tmp_path / "example.py"
        test_file.write_text("import spellbook_mcp.db\n")

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == "import spellbook.db\n"

    def test_subpackage_import(self, tmp_path):
        """Rewrite subpackage imports like spellbook_mcp.security.check."""
        test_file = tmp_path / "example.py"
        test_file.write_text("from spellbook_mcp.security.check import scan\n")

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == "from spellbook.security.check import scan\n"

    def test_multiple_imports(self, tmp_path):
        """Rewrite multiple imports in a single file."""
        test_file = tmp_path / "example.py"
        test_file.write_text(
            textwrap.dedent("""\
            from spellbook_mcp.db import get_db
            from spellbook_mcp.memory_tools import store
            import spellbook_mcp.server
            """)
        )

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        expected = textwrap.dedent("""\
            from spellbook.db import get_db
            from spellbook.memory_tools import store
            import spellbook.server
        """)
        assert test_file.read_text() == expected

    def test_fallback_for_unmapped_module(self, tmp_path):
        """Unmapped modules should get spellbook_mcp -> spellbook fallback."""
        test_file = tmp_path / "example.py"
        test_file.write_text("from spellbook_mcp.unknown_thing import foo\n")

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == "from spellbook.unknown_thing import foo\n"

    def test_no_false_positive_on_spellbook_mcp_substring(self, tmp_path):
        """Should not replace 'spellbook_mcp' when it's part of a larger word."""
        test_file = tmp_path / "example.py"
        test_file.write_text('name = "my_spellbook_mcp_thing"\n')

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        # The word boundary regex should NOT match inside a larger identifier
        assert test_file.read_text() == 'name = "my_spellbook_mcp_thing"\n'


class TestMockPatchRewriting:
    """Test rewriting of mock.patch target strings."""

    def test_patch_decorator_string(self, tmp_path):
        """Rewrite mock.patch('spellbook_mcp.db.get_db')."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            textwrap.dedent("""\
            @mock.patch("spellbook_mcp.db.get_db")
            def test_something(mock_db):
                pass
            """)
        )

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        expected = textwrap.dedent("""\
            @mock.patch("spellbook.db.get_db")
            def test_something(mock_db):
                pass
        """)
        assert test_file.read_text() == expected

    def test_patch_with_single_quotes(self, tmp_path):
        """Rewrite mock.patch with single-quoted strings."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("    mock.patch('spellbook_mcp.memory_store.MemoryStore')\n")

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == "    mock.patch('spellbook.memory_store.MemoryStore')\n"

    def test_patch_object_string(self, tmp_path):
        """Rewrite patch target in mock.patch.object context."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            '    with mock.patch("spellbook_mcp.config_tools.get_config") as m:\n'
        )

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == (
            '    with mock.patch("spellbook.config_tools.get_config") as m:\n'
        )


class TestMarkdownFiles:
    """Test handling of markdown files."""

    def test_markdown_code_block(self, tmp_path):
        """Rewrite spellbook_mcp references in markdown."""
        test_file = tmp_path / "doc.md"
        test_file.write_text(
            textwrap.dedent("""\
            # Migration Guide

            Old import:
            ```python
            from spellbook_mcp.db import get_db
            ```

            The `spellbook_mcp.server` module has moved.
            """)
        )

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        content = test_file.read_text()
        assert "spellbook.db" in content
        assert "spellbook.server" in content
        assert "spellbook_mcp" not in content

    def test_markdown_inline_reference(self, tmp_path):
        """Rewrite inline spellbook_mcp references in markdown."""
        test_file = tmp_path / "readme.md"
        test_file.write_text("See `spellbook_mcp.health` for health checks.\n")

        mod = _load_migrate_module()
        mod.migrate_file(str(test_file), dry_run=False)

        assert test_file.read_text() == "See `spellbook.health` for health checks.\n"


class TestRewriteLine:
    """Unit tests for the rewrite_line function."""

    def test_longest_match_first(self):
        """Longer module paths should be matched before shorter prefixes."""
        mod = _load_migrate_module()

        # spellbook_mcp.security.check should match security subpackage
        line = "from spellbook_mcp.security.check import scan"
        result = mod.rewrite_line(line)
        assert result == "from spellbook.security.check import scan"

    def test_no_change_returns_original(self):
        """Lines without spellbook_mcp should be returned unchanged."""
        mod = _load_migrate_module()
        line = "import os\n"
        assert mod.rewrite_line(line) == line

    def test_preserves_indentation(self):
        """Indented lines should keep their indentation."""
        mod = _load_migrate_module()
        line = "    from spellbook_mcp.db import get_db\n"
        result = mod.rewrite_line(line)
        assert result == "    from spellbook.db import get_db\n"
