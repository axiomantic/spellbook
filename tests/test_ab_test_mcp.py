"""Tests for A/B test MCP tools."""

import pytest


class TestABTestMCPTools:
    """Test that A/B test tools are registered."""

    def test_experiment_create_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_create" in tool_names

    def test_experiment_start_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_start" in tool_names

    def test_experiment_pause_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_pause" in tool_names

    def test_experiment_complete_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_complete" in tool_names

    def test_experiment_status_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_status" in tool_names

    def test_experiment_list_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_list" in tool_names

    def test_experiment_results_tool_exists(self):
        from spellbook_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "experiment_results" in tool_names
