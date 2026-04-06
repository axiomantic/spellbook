"""Test that stint MCP tools are registered on the server."""

import inspect
import sys
from pathlib import Path
import bigfoot
from dirty_equals import IsStr

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


def _get_registered_tool_names() -> list[str]:
    """Get tool names from the FastMCP registry (v2 or v3)."""
    from spellbook.server import mcp

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


def _get_stint_push_tool():
    """Get the FunctionTool object for stint_push from the FastMCP registry."""
    from spellbook.server import mcp

    # FastMCP v3: tools in _local_provider._components dict
    try:
        components = mcp._local_provider._components
        for key, tool in components.items():
            if key.startswith("tool:") and "stint_push" in key:
                return tool
    except AttributeError:
        pass

    # FastMCP v2: tools in _tool_manager._tools dict
    try:
        return mcp._tool_manager._tools["stint_push"]
    except (AttributeError, KeyError):
        pass

    pytest.fail("Cannot find stint_push in FastMCP tool registry")


class TestStintPushBehavioralMode:
    """Verify stint_push MCP tool accepts and passes through behavioral_mode."""

    def test_stint_push_has_behavioral_mode_parameter(self):
        """The stint_push MCP function must accept a behavioral_mode parameter."""
        tool = _get_stint_push_tool()
        sig = inspect.signature(tool.fn)
        assert "behavioral_mode" in sig.parameters, (
            f"stint_push is missing 'behavioral_mode' parameter. "
            f"Parameters: {list(sig.parameters.keys())}"
        )

    def test_stint_push_behavioral_mode_defaults_to_empty_string(self):
        """behavioral_mode must default to empty string."""
        tool = _get_stint_push_tool()
        sig = inspect.signature(tool.fn)
        param = sig.parameters["behavioral_mode"]
        assert param.default == "", (
            f"behavioral_mode default should be '' but is {param.default!r}"
        )

    def test_stint_push_behavioral_mode_annotated_as_str(self):
        """behavioral_mode must be annotated as str."""
        tool = _get_stint_push_tool()
        sig = inspect.signature(tool.fn)
        param = sig.parameters["behavioral_mode"]
        assert param.annotation is str, (
            f"behavioral_mode annotation should be str but is {param.annotation!r}"
        )

    def test_stint_push_passes_behavioral_mode_to_push_stint(self):
        """stint_push must pass behavioral_mode through to push_stint."""
        tool = _get_stint_push_tool()
        fn = tool.fn
        # Unwrap decorators to get the raw function
        while hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__

        mock_result = {"success": True, "depth": 1, "stack": []}
        mock_push = bigfoot.mock("spellbook.coordination.stint:push_stint")
        mock_push.__call__.returns(mock_result)

        with bigfoot:
            result = fn(
                project_path="/tmp/test",
                name="test-stint",
                type="custom",
                purpose="testing",
                behavioral_mode="ORCHESTRATOR: dispatch subagents",
                metadata=None,
            )

        mock_push.__call__.assert_call(
            kwargs={
                "project_path": "/tmp/test",
                "name": "test-stint",
                "stint_type": "custom",
                "purpose": "testing",
                "behavioral_mode": "ORCHESTRATOR: dispatch subagents",
                "metadata": None,
                "session_id": None,
            },
        )
        bigfoot.log_mock.assert_log(
            "WARNING",
            IsStr(regex=r"(No event loop available|Event loop not running) for publish_sync, dropping event"),
            "spellbook.admin.events",
        )
        assert result == {"success": True, "depth": 1, "stack": []}

    def test_stint_push_still_accepts_type_parameter(self):
        """type parameter should still be accepted for backward compatibility."""
        tool = _get_stint_push_tool()
        sig = inspect.signature(tool.fn)
        assert "type" in sig.parameters, (
            f"stint_push must still accept 'type' for backward compatibility. "
            f"Parameters: {list(sig.parameters.keys())}"
        )

    def test_stint_push_no_success_criteria_parameter(self):
        """success_criteria parameter should no longer exist."""
        tool = _get_stint_push_tool()
        sig = inspect.signature(tool.fn)
        assert "success_criteria" not in sig.parameters, (
            f"stint_push should not have 'success_criteria' parameter. "
            f"Parameters: {list(sig.parameters.keys())}"
        )
