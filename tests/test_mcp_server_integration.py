"""Integration tests for MCP server with swarm tools."""
import pytest
from unittest.mock import patch, AsyncMock
from spellbook_mcp.preferences import CoordinationConfig, CoordinationBackend, MCPSSEConfig


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


class TestAnalyticsSummaryTool:
    """Tests for spellbook_analytics_summary MCP tool."""

    def test_analytics_summary_returns_metrics(self, tmp_path, monkeypatch):
        """Test that analytics summary returns skill metrics from database."""
        from spellbook_mcp.db import init_db, get_connection, get_db_path
        from spellbook_mcp.skill_analyzer import OUTCOME_COMPLETED

        # Set up test database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr(
            "spellbook_mcp.db.get_db_path",
            lambda: db_path
        )

        # Insert test data
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO skill_outcomes
            (skill_name, skill_version, session_id, project_encoded, start_time, outcome, tokens_used)
            VALUES
            ('debugging', 'v1', 's1', 'test-project', '2026-01-26T10:00:00', 'completed', 1000),
            ('debugging', 'v1', 's2', 'test-project', '2026-01-26T11:00:00', 'completed', 1500),
            ('debugging', 'v2', 's3', 'test-project', '2026-01-26T12:00:00', 'abandoned', 500)
        """)
        conn.commit()

        # Import the function (not the tool decorator version)
        from spellbook_mcp.skill_analyzer import get_analytics_summary

        result = get_analytics_summary(
            project_encoded="test-project",
            days=30,
        )

        assert result["total_outcomes"] == 3
        assert "by_skill" in result
        assert "debugging" in result["by_skill"]


class TestTelemetryTools:
    """Tests for telemetry MCP tools."""

    def test_telemetry_enable_via_server(self, tmp_path, monkeypatch):
        """Test telemetry enable through server function."""
        from spellbook_mcp.db import init_db, get_db_path
        from spellbook_mcp.config_tools import telemetry_enable, telemetry_status

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = telemetry_enable(db_path=str(db_path))
        assert result["status"] == "enabled"

        status = telemetry_status(db_path=str(db_path))
        assert status["enabled"] is True

    def test_telemetry_disable(self, tmp_path):
        """Test telemetry disable through server function."""
        from spellbook_mcp.db import init_db
        from spellbook_mcp.config_tools import telemetry_enable, telemetry_disable, telemetry_status

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Enable first
        telemetry_enable(db_path=str(db_path))

        # Then disable
        result = telemetry_disable(db_path=str(db_path))
        assert result["status"] == "disabled"

        # Verify via status
        status = telemetry_status(db_path=str(db_path))
        assert status["enabled"] is False

    def test_telemetry_status_when_not_configured(self, tmp_path):
        """Test telemetry_status when no config exists."""
        from spellbook_mcp.db import init_db
        from spellbook_mcp.config_tools import telemetry_status

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        status = telemetry_status(db_path=str(db_path))

        assert status["enabled"] is False
        assert status["endpoint_url"] is None
        assert status["last_sync"] is None
