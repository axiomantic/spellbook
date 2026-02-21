"""Tests for A/B test MCP tools."""

import pytest


def _get_tool_names():
    """Get tool names from the FastMCP server's internal tool registry."""
    from spellbook_mcp.server import mcp

    # FastMCP stores registered tools in _tool_manager._tools dict.
    # This mirrors the approach used in server.py's own _get_tool_names().
    try:
        return list(mcp._tool_manager._tools.keys())
    except AttributeError:
        # Fallback: empty list if internal structure changes
        return []


class TestABTestMCPTools:
    """Test that A/B test tools are registered."""

    def test_experiment_create_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_create" in tool_names

    def test_experiment_start_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_start" in tool_names

    def test_experiment_pause_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_pause" in tool_names

    def test_experiment_complete_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_complete" in tool_names

    def test_experiment_status_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_status" in tool_names

    def test_experiment_list_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_list" in tool_names

    def test_experiment_results_tool_exists(self):
        tool_names = _get_tool_names()
        assert "experiment_results" in tool_names
