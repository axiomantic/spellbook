"""Test that stint MCP tools are registered on the server."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


def _get_registered_tool_names() -> list[str]:
    """Get tool names from the FastMCP registry (v2 or v3)."""
    from spellbook_mcp.server import mcp

    # FastMCP v2: tools in _tool_manager._tools dict
    try:
        return list(mcp._tool_manager._tools.keys())
    except AttributeError:
        pass

    # FastMCP v3: tools in _local_provider._components dict
    try:
        components = mcp._local_provider._components
        return [
            key.split(":", 1)[1].rsplit("@", 1)[0]
            for key in components
            if key.startswith("tool:")
        ]
    except AttributeError:
        pass

    pytest.fail("Cannot access FastMCP tool registry via _tool_manager or _local_provider")


class TestStintToolRegistration:
    """Verify stint tools are registered as MCP tools."""

    def test_stint_push_is_registered(self):
        tool_names = _get_registered_tool_names()
        assert "stint_push" in tool_names, (
            f"stint_push not in FastMCP tool registry. Registered tools: {sorted(tool_names)}"
        )

    def test_stint_pop_is_registered(self):
        tool_names = _get_registered_tool_names()
        assert "stint_pop" in tool_names, (
            f"stint_pop not in FastMCP tool registry. Registered tools: {sorted(tool_names)}"
        )

    def test_stint_check_is_registered(self):
        tool_names = _get_registered_tool_names()
        assert "stint_check" in tool_names, (
            f"stint_check not in FastMCP tool registry. Registered tools: {sorted(tool_names)}"
        )

    def test_stint_replace_is_registered(self):
        tool_names = _get_registered_tool_names()
        assert "stint_replace" in tool_names, (
            f"stint_replace not in FastMCP tool registry. Registered tools: {sorted(tool_names)}"
        )
