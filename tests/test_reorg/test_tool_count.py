"""Tests for MCP tool registration count.

Verifies that register_all_tools() results in the expected number of
registered tools (targeting 101 from the original monolith).
"""

import pytest


def _get_tool_names(mcp_instance):
    """Get registered tool names from FastMCP, supporting v2 and v3."""
    # FastMCP v2: tools in _tool_manager._tools dict
    try:
        return list(mcp_instance._tool_manager._tools.keys())
    except AttributeError:
        pass

    # FastMCP v3: tools in _local_provider._components dict
    try:
        components = mcp_instance._local_provider._components
        return [
            key.split(":", 1)[1].rsplit("@", 1)[0]
            for key in components
            if key.startswith("tool:")
        ]
    except AttributeError:
        return []


class TestToolRegistrationCount:
    """Verify all MCP tools are registered after decomposition."""

    def test_tool_count_at_least_65(self):
        """After register_all_tools(), at least 65 tools should be registered.

        Target lowered from 90 after three rounds of MCP tool pruning:
          - 15 tools removed with the ``messaging`` and ``experiments`` module
            deletions (both had zero external callers).
          - 10 further dead tools removed (health/misc debug tools, telemetry
            triad, forge_roundtable_debate, forge_select_skill).
          - 2 more forge_* tools removed with zero skill/command/extension
            callers (forge_feature_update, forge_process_roundtable_response).

        65 tools remain. This floor guards against accidental further
        regression.
        """
        from spellbook.mcp.server import mcp, register_all_tools

        register_all_tools()
        tool_names = _get_tool_names(mcp)
        assert len(tool_names) >= 65, (
            f"Expected >= 65 tools, got {len(tool_names)}. "
            f"Missing tools need to be added to the appropriate tool module."
        )

    def test_key_tools_present(self):
        """Verify a representative sample of tools from each module are registered."""
        from spellbook.mcp.server import mcp, register_all_tools

        register_all_tools()
        tool_names = set(_get_tool_names(mcp))

        # One tool from each module
        expected_tools = [
            "find_session",          # sessions
            "spellbook_config_get",  # config
            "spellbook_health_check",  # health
            "memory_recall",         # memory
            "security_check_tool_input",  # security
            "pr_fetch",              # pr
            "forge_iteration_start", # forged
            "fractal_create_graph",  # fractal
            "stint_push",            # coordination
            "spellbook_check_for_updates",  # updates
            "workflow_state_save",   # misc
            "tooling_discover",      # tooling
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names, (
                f"Expected tool '{tool_name}' not found in registered tools"
            )
