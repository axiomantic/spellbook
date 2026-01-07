"""Test that MCP server does NOT expose skill tools after cleanup."""

import pytest
from pathlib import Path


def test_skill_tools_removed_from_server():
    """Verify find_spellbook_skills and use_spellbook_skill tools are removed."""
    from spellbook_mcp import server

    # Get all attributes that have .fn method (FastMCP tools)
    tool_names = [name for name in dir(server)
                  if not name.startswith('_') and hasattr(getattr(server, name), 'fn')]

    # Verify skill tools are NOT present
    assert "find_spellbook_skills" not in tool_names, "find_spellbook_skills should be removed"
    assert "use_spellbook_skill" not in tool_names, "use_spellbook_skill should be removed"


def test_session_tools_still_present():
    """Verify session management tools are still present after cleanup."""
    from spellbook_mcp import server

    # Get all attributes that have .fn method (FastMCP tools)
    tool_names = [name for name in dir(server)
                  if not name.startswith('_') and hasattr(getattr(server, name), 'fn')]

    # Verify session management tools are present
    assert "find_session" in tool_names, "find_session should remain"
    assert "split_session" in tool_names, "split_session should remain"
    assert "list_sessions" in tool_names, "list_sessions should remain"
    assert "spawn_claude_session" in tool_names, "spawn_claude_session should remain"


def test_swarm_tools_still_present():
    """Verify swarm coordination tools are still present after cleanup."""
    from spellbook_mcp import server

    # Get all attributes that have .fn method (FastMCP tools)
    tool_names = [name for name in dir(server)
                  if not name.startswith('_') and hasattr(getattr(server, name), 'fn')]

    # Verify swarm tools are present
    assert "mcp_swarm_create" in tool_names, "mcp_swarm_create should remain"
    assert "mcp_swarm_register" in tool_names, "mcp_swarm_register should remain"
    assert "mcp_swarm_progress" in tool_names, "mcp_swarm_progress should remain"
    assert "mcp_swarm_complete" in tool_names, "mcp_swarm_complete should remain"
    assert "mcp_swarm_error" in tool_names, "mcp_swarm_error should remain"
    assert "mcp_swarm_monitor" in tool_names, "mcp_swarm_monitor should remain"


def test_skill_ops_module_does_not_exist():
    """Verify skill_ops.py has been deleted."""
    # Try to import skill_ops - should fail
    with pytest.raises(ImportError):
        from spellbook_mcp import skill_ops


def test_no_skill_ops_imports_in_server():
    """Verify server.py does not import from skill_ops."""
    from spellbook_mcp import server
    import inspect

    # Read the server.py source code
    server_source = inspect.getsource(server)

    # Verify no imports from skill_ops
    assert "from skill_ops import" not in server_source, "server.py should not import from skill_ops"
    assert "import skill_ops" not in server_source, "server.py should not import skill_ops"


def test_no_get_skill_dirs_helper():
    """Verify get_skill_dirs helper function has been removed."""
    from spellbook_mcp import server

    # Verify get_skill_dirs does not exist on server module
    assert not hasattr(server, 'get_skill_dirs'), "get_skill_dirs helper should be removed"


def test_server_docstring_updated():
    """Verify server docstring no longer references skill tools."""
    from spellbook_mcp import server

    docstring = server.__doc__

    # Verify skill tools are not mentioned in docstring
    assert "find_spellbook_skills" not in docstring, "Docstring should not mention find_spellbook_skills"
    assert "use_spellbook_skill" not in docstring, "Docstring should not mention use_spellbook_skill"

    # Verify session and swarm tools are mentioned
    assert "find_session" in docstring or "Session Management" in docstring, "Docstring should mention session tools"
    assert "swarm_create" in docstring or "Swarm Coordination" in docstring, "Docstring should mention swarm tools"
