"""Tests for spellbook.mcp.routes module.

Verifies that the routes module is importable and contains the expected
custom route handler functions.
"""

import pytest


class TestMcpRoutesImportable:
    """Test that spellbook.mcp.routes is importable with expected exports."""

    def test_module_importable(self):
        import spellbook.mcp.routes  # noqa: F401

    def test_api_health_exists(self):
        from spellbook.mcp.routes import api_health

        assert callable(api_health)

    def test_api_memory_event_exists(self):
        from spellbook.mcp.routes import api_memory_event

        assert callable(api_memory_event)

    def test_api_memory_recall_exists(self):
        from spellbook.mcp.routes import api_memory_recall

        assert callable(api_memory_recall)
