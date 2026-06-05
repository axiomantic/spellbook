"""Tests for MCP tool registration count.

Verifies that register_all_tools() results in the expected number of
registered tools (66 after adding the canvas decision tools; 63 after the
memory-system removal in 0.68.0).
"""



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

    def test_tool_count_is_66(self):
        """After register_all_tools(), exactly 66 tools should be registered.

        Target lowered from 90 after four rounds of MCP tool pruning:
          - 15 tools removed with the ``messaging`` and ``experiments`` module
            deletions (both had zero external callers).
          - 10 further dead tools removed (health/misc debug tools, telemetry
            triad, forge_roundtable_debate, forge_select_skill).
          - 2 more forge_* tools removed with zero skill/command/extension
            callers (forge_feature_update, forge_process_roundtable_response).
          - 7 memory tools removed with the memory-system deletion
            (memory_recall/store/forget/sync/verify/review_events and the
            memory bridge tool).

        Then raised by 3 with the canvas decision tools (canvas_decision_open,
        canvas_decision_await, canvas_decision_cancel): 63 + 3 = 66.

        Exactly 66 tools remain. Full-equality guards against both accidental
        tool loss and accidental tool addition.
        """
        from spellbook.mcp.server import mcp, register_all_tools

        register_all_tools()
        tool_names = _get_tool_names(mcp)
        assert len(tool_names) == 66, (
            f"Expected exactly 66 tools, got {len(tool_names)}. "
            f"If you added or removed a tool, update this count deliberately."
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
