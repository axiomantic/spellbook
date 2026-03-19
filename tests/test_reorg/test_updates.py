"""Tests for the spellbook.updates domain module.

Verifies that key exports from spellbook.updates.tools and
spellbook.updates.watcher exist in spellbook.updates.tools
and spellbook.updates.watcher.
"""

import pytest


class TestUpdatesTools:
    """Verify spellbook.updates.tools has key exports from spellbook.updates.tools."""

    def test_tools_module_importable(self):
        import spellbook.updates.tools

        assert hasattr(spellbook.updates.tools, "__file__")

    @pytest.mark.parametrize(
        "name",
        [
            "classify_version_bump",
            "get_changelog_between",
            "check_for_updates",
            "apply_update",
            "rollback_update",
            "get_update_status",
        ],
    )
    def test_tools_has_export(self, name):
        import spellbook.updates.tools as tools

        assert hasattr(tools, name), f"spellbook.updates.tools missing {name}"

    def test_tools_imports_from_core_config(self):
        """Verify tools.py imports config from spellbook.core, not spellbook."""
        import ast
        import inspect

        import spellbook.updates.tools as tools

        source = inspect.getsource(tools)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("spellbook"), (
                    f"spellbook.updates.tools still imports from "
                    f"spellbook: {node.module}"
                )


class TestUpdatesWatcher:
    """Verify spellbook.updates.watcher has key exports from spellbook.updates.watcher."""

    def test_watcher_module_importable(self):
        import spellbook.updates.watcher

        assert hasattr(spellbook.updates.watcher, "__file__")

    @pytest.mark.parametrize(
        "name",
        [
            "UpdateWatcher",
        ],
    )
    def test_watcher_has_export(self, name):
        import spellbook.updates.watcher as watcher

        assert hasattr(watcher, name), f"spellbook.updates.watcher missing {name}"

    def test_watcher_imports_from_core_config(self):
        """Verify watcher.py imports config from spellbook.core, not spellbook."""
        import ast
        import inspect

        import spellbook.updates.watcher as watcher

        source = inspect.getsource(watcher)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("spellbook"), (
                    f"spellbook.updates.watcher still imports from "
                    f"spellbook: {node.module}"
                )
