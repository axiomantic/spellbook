"""Integration tests for MCP server with swarm tools."""
import pytest
from unittest.mock import patch, AsyncMock
from spellbook.preferences import CoordinationConfig, CoordinationBackend, MCPSSEConfig


class TestMCPServerSwarmToolsIntegration:
    """Test that swarm tools are properly integrated into MCP server."""

    def test_swarm_tools_are_importable(self):
        """Test that swarm tools can be imported from server module."""
        from spellbook_mcp import server

        assert hasattr(server, 'mcp_swarm_create')
        assert hasattr(server, 'mcp_swarm_register')
        assert hasattr(server, 'mcp_swarm_progress')
        assert hasattr(server, 'mcp_swarm_complete')
        assert hasattr(server, 'mcp_swarm_error')
        assert hasattr(server, 'mcp_swarm_monitor')

    def test_swarm_create_tool_is_callable(self):
        """Test that mcp_swarm_create tool is callable."""
        from spellbook_mcp.swarm_tools import swarm_create

        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=7432, host="127.0.0.1")
        )

        mock_backend = AsyncMock()
        mock_backend.create_swarm.return_value = "swarm-test-123"

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_create(
                    feature="test-feature",
                    manifest_path="/path/to/manifest.json"
                )

                assert result["swarm_id"] == "swarm-test-123"
                assert result["status"] == "created"

    def test_swarm_register_tool_is_callable(self):
        """Test that mcp_swarm_register tool is callable."""
        from spellbook_mcp.swarm_tools import swarm_register

        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=7432, host="127.0.0.1")
        )

        mock_backend = AsyncMock()
        mock_backend.register_worker.return_value = {
            "status": "registered",
            "packet_id": 1
        }

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_register(
                    swarm_id="swarm-123",
                    packet_id=1,
                    packet_name="test-packet",
                    tasks_total=5,
                    worktree="/path/to/worktree"
                )

                assert result["status"] == "registered"
                assert result["packet_id"] == 1

    def test_swarm_monitor_tool_is_callable(self):
        """Test that mcp_swarm_monitor tool is callable."""
        from spellbook_mcp.swarm_tools import swarm_monitor

        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=7432, host="127.0.0.1")
        )

        mock_backend = AsyncMock()
        mock_backend.get_status.return_value = {
            "swarm_id": "swarm-123",
            "status": "running",
            "workers_registered": 3,
            "workers_complete": 1,
            "workers_failed": 0,
            "ready_for_merge": False
        }

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_monitor(swarm_id="swarm-123")

                assert result["swarm_id"] == "swarm-123"
                assert result["status"] == "running"
                assert result["workers_registered"] == 3

    def test_server_module_loads_without_errors(self):
        """Test that the server module loads without errors."""
        try:
            import spellbook_mcp.server
            assert True
        except Exception as e:
            pytest.fail(f"Server module failed to load: {e}")

    def test_mcp_instance_exists(self):
        """Test that mcp FastMCP instance exists."""
        from spellbook_mcp.server import mcp

        assert mcp is not None
        assert hasattr(mcp, 'tool')

    def test_all_swarm_tools_have_docstrings(self):
        """Test that all swarm MCP tools have proper docstrings."""
        from spellbook_mcp import server

        tools = [
            'mcp_swarm_create',
            'mcp_swarm_register',
            'mcp_swarm_progress',
            'mcp_swarm_complete',
            'mcp_swarm_error',
            'mcp_swarm_monitor'
        ]

        for tool_name in tools:
            tool = getattr(server, tool_name)
            # FunctionTool objects have a description attribute
            assert hasattr(tool, 'description'), f"{tool_name} missing description"
            assert tool.description is not None, f"{tool_name} description is None"
            assert len(tool.description) > 50, f"{tool_name} description too short"
