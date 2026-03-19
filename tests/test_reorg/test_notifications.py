"""Tests for the spellbook.notifications domain module.

Verifies that key exports from spellbook_mcp.tts and spellbook_mcp.notify
exist in spellbook.notifications.tts and spellbook.notifications.notify.
"""

import pytest


class TestNotificationsTTS:
    """Verify spellbook.notifications.tts has key exports from spellbook_mcp.tts."""

    def test_tts_module_importable(self):
        import spellbook.notifications.tts

        assert hasattr(spellbook.notifications.tts, "__file__")

    @pytest.mark.parametrize(
        "name",
        [
            "get_status",
            "preload",
            "ensure_loaded",
            "speak",
            "_check_availability",
            "_load_model",
            "_generate_audio",
            "_play_audio",
            "_resolve_setting",
        ],
    )
    def test_tts_has_export(self, name):
        import spellbook.notifications.tts as tts

        assert hasattr(tts, name), f"spellbook.notifications.tts missing {name}"

    def test_tts_imports_from_core_config(self):
        """Verify tts.py imports config from spellbook.core, not spellbook_mcp."""
        import ast
        import inspect

        import spellbook.notifications.tts as tts

        source = inspect.getsource(tts)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("spellbook_mcp"), (
                        f"spellbook.notifications.tts still imports from "
                        f"spellbook_mcp: {node.module}"
                    )


class TestNotificationsNotify:
    """Verify spellbook.notifications.notify has key exports from spellbook_mcp.notify."""

    def test_notify_module_importable(self):
        import spellbook.notifications.notify

        assert hasattr(spellbook.notifications.notify, "__file__")

    @pytest.mark.parametrize(
        "name",
        [
            "get_status",
            "check_availability",
            "send_notification",
            "_detect_platform",
            "_resolve_setting",
            "_send_sync",
        ],
    )
    def test_notify_has_export(self, name):
        import spellbook.notifications.notify as notify

        assert hasattr(notify, name), f"spellbook.notifications.notify missing {name}"

    def test_notify_imports_from_core_config(self):
        """Verify notify.py imports config from spellbook.core, not spellbook_mcp."""
        import ast
        import inspect

        import spellbook.notifications.notify as notify

        source = inspect.getsource(notify)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("spellbook_mcp"), (
                        f"spellbook.notifications.notify still imports from "
                        f"spellbook_mcp: {node.module}"
                    )
