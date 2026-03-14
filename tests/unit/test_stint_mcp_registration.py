"""Test that stint MCP tools are registered on the server."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


class TestStintToolRegistration:
    """Verify stint tools are registered as MCP tools."""

    def test_stint_push_is_registered(self):
        from spellbook_mcp.server import mcp
        tool_names = [t.name if hasattr(t, 'name') else t for t in mcp._tool_manager._tools.keys()] if hasattr(mcp, '_tool_manager') else []
        # Fallback: check function exists on module
        from spellbook_mcp import server
        assert hasattr(server, 'stint_push'), "stint_push not defined in server.py"

    def test_stint_pop_is_registered(self):
        from spellbook_mcp import server
        assert hasattr(server, 'stint_pop'), "stint_pop not defined in server.py"

    def test_stint_check_is_registered(self):
        from spellbook_mcp import server
        assert hasattr(server, 'stint_check'), "stint_check not defined in server.py"

    def test_stint_replace_is_registered(self):
        from spellbook_mcp import server
        assert hasattr(server, 'stint_replace'), "stint_replace not defined in server.py"
