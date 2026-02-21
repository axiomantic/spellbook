"""Tests for A/B test MCP tools."""

import asyncio

import pytest


def _get_tool_names():
    """Get tool names from the FastMCP server using the public async API."""
    from spellbook_mcp.server import mcp

    tools = asyncio.run(mcp.get_tools())
    return list(tools.keys())


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
