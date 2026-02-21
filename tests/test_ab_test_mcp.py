"""Tests for A/B test MCP tools."""

import asyncio

import pytest


def _get_tool_names():
    """Get tool names from the FastMCP server's public API.

    Uses the async ``mcp.get_tools()`` method (wrapped with asyncio.run)
    rather than poking at private internals like ``_tool_manager._tools``,
    which may be empty before the server event-loop starts on some
    Python / FastMCP versions (notably Python 3.11 in CI).
    """
    from spellbook_mcp.server import mcp

    try:
        tools = asyncio.run(mcp.get_tools())
        return list(tools.keys())
    except Exception:
        # Last-resort fallback: try the private dict (works on some versions)
        try:
            return list(mcp._tool_manager._tools.keys())
        except AttributeError:
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
