"""Tests for MCP swarm coordination tools."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from spellbook_mcp.preferences import CoordinationConfig, CoordinationBackend, MCPSSEConfig


@pytest.fixture
def mock_backend():
    """Create a mock coordination backend."""
    backend = AsyncMock()
    backend.create_swarm.return_value = "swarm-123"
    backend.register_worker.return_value = {
        "status": "registered",
        "packet_id": 1
    }
    backend.report_progress.return_value = {
        "status": "recorded",
        "tasks_completed": 2,
        "tasks_total": 5
    }
    backend.report_complete.return_value = {
        "status": "complete",
        "all_workers_done": False
    }
    backend.report_error.return_value = {
        "status": "error_recorded",
        "will_retry": True
    }
    backend.get_status.return_value = {
        "swarm_id": "swarm-123",
        "status": "running",
        "workers_registered": 3,
        "workers_complete": 1,
        "workers_failed": 0,
        "ready_for_merge": False
    }
    return backend


@pytest.fixture
def coordination_config():
    """Create a coordination config."""
    return CoordinationConfig(
        backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
        mcp_sse=MCPSSEConfig(port=7432, host="127.0.0.1")
    )


class TestSwarmCreate:
    """Tests for swarm_create tool."""

    def test_creates_swarm_successfully(self, mock_backend, coordination_config):
        """Test successful swarm creation."""
        from spellbook_mcp.swarm_tools import swarm_create

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_create(
                    feature="user-authentication",
                    manifest_path="/path/to/manifest.json",
                    auto_merge=True
                )

                assert result["swarm_id"] == "swarm-123"
                assert result["status"] == "created"
                mock_backend.create_swarm.assert_called_once_with(
                    "user-authentication",
                    "/path/to/manifest.json",
                    True
                )

    def test_auto_merge_defaults_to_false(self, mock_backend, coordination_config):
        """Test auto_merge defaults to False."""
        from spellbook_mcp.swarm_tools import swarm_create

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                swarm_create(
                    feature="test-feature",
                    manifest_path="/path/to/manifest.json"
                )

                mock_backend.create_swarm.assert_called_once_with(
                    "test-feature",
                    "/path/to/manifest.json",
                    False
                )

    def test_raises_when_backend_none(self):
        """Test error when backend is NONE."""
        from spellbook_mcp.swarm_tools import swarm_create

        config = CoordinationConfig(backend=CoordinationBackend.NONE)
        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=config):
            with pytest.raises(ValueError, match="No coordination backend configured"):
                swarm_create(
                    feature="test",
                    manifest_path="/path"
                )


class TestSwarmRegister:
    """Tests for swarm_register tool."""

    def test_registers_worker_successfully(self, mock_backend, coordination_config):
        """Test successful worker registration."""
        from spellbook_mcp.swarm_tools import swarm_register

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_register(
                    swarm_id="swarm-123",
                    packet_id=1,
                    packet_name="auth-packet",
                    tasks_total=5,
                    worktree="/path/to/worktree"
                )

                assert result["status"] == "registered"
                assert result["packet_id"] == 1
                mock_backend.register_worker.assert_called_once_with(
                    "swarm-123",
                    1,
                    "auth-packet",
                    5,
                    "/path/to/worktree"
                )


class TestSwarmProgress:
    """Tests for swarm_progress tool."""

    def test_reports_progress_successfully(self, mock_backend, coordination_config):
        """Test successful progress reporting."""
        from spellbook_mcp.swarm_tools import swarm_progress

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_progress(
                    swarm_id="swarm-123",
                    packet_id=1,
                    task_id="task-1",
                    task_name="Implement login",
                    status="completed",
                    tasks_completed=2,
                    tasks_total=5,
                    commit="abc1234"
                )

                assert result["status"] == "recorded"
                assert result["tasks_completed"] == 2
                assert result["tasks_total"] == 5
                mock_backend.report_progress.assert_called_once_with(
                    "swarm-123",
                    1,
                    "task-1",
                    "Implement login",
                    "completed",
                    2,
                    5,
                    "abc1234"
                )

    def test_commit_optional(self, mock_backend, coordination_config):
        """Test commit parameter is optional."""
        from spellbook_mcp.swarm_tools import swarm_progress

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                swarm_progress(
                    swarm_id="swarm-123",
                    packet_id=1,
                    task_id="task-1",
                    task_name="Task name",
                    status="started",
                    tasks_completed=0,
                    tasks_total=5
                )

                mock_backend.report_progress.assert_called_once_with(
                    "swarm-123",
                    1,
                    "task-1",
                    "Task name",
                    "started",
                    0,
                    5,
                    None
                )


class TestSwarmComplete:
    """Tests for swarm_complete tool."""

    def test_reports_completion_successfully(self, mock_backend, coordination_config):
        """Test successful completion reporting."""
        from spellbook_mcp.swarm_tools import swarm_complete

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_complete(
                    swarm_id="swarm-123",
                    packet_id=1,
                    final_commit="abc1234",
                    tests_passed=True,
                    review_passed=True
                )

                assert result["status"] == "complete"
                assert result["all_workers_done"] is False
                mock_backend.report_complete.assert_called_once_with(
                    "swarm-123",
                    1,
                    "abc1234",
                    True,
                    True
                )


class TestSwarmError:
    """Tests for swarm_error tool."""

    def test_reports_error_successfully(self, mock_backend, coordination_config):
        """Test successful error reporting."""
        from spellbook_mcp.swarm_tools import swarm_error

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_error(
                    swarm_id="swarm-123",
                    packet_id=1,
                    task_id="task-1",
                    error_type="TestFailure",
                    message="Tests failed in auth module",
                    recoverable=True
                )

                assert result["status"] == "error_recorded"
                assert result["will_retry"] is True
                mock_backend.report_error.assert_called_once_with(
                    "swarm-123",
                    1,
                    "task-1",
                    "TestFailure",
                    "Tests failed in auth module",
                    True
                )


class TestSwarmMonitor:
    """Tests for swarm_monitor tool."""

    def test_gets_status_successfully(self, mock_backend, coordination_config):
        """Test successful status retrieval."""
        from spellbook_mcp.swarm_tools import swarm_monitor

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=mock_backend):
                result = swarm_monitor(swarm_id="swarm-123")

                assert result["swarm_id"] == "swarm-123"
                assert result["status"] == "running"
                assert result["workers_registered"] == 3
                assert result["workers_complete"] == 1
                assert result["workers_failed"] == 0
                assert result["ready_for_merge"] is False
                mock_backend.get_status.assert_called_once_with("swarm-123")


class TestBackendInitialization:
    """Tests for backend initialization."""

    def test_gets_mcp_http_backend(self):
        """Test getting MCP HTTP backend."""
        from spellbook_mcp.swarm_tools import _get_backend
        from spellbook_mcp.coordination.backends.mcp_streamable_http import MCPStreamableHTTPBackend

        config = CoordinationConfig(
            backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
            mcp_sse=MCPSSEConfig(port=7432, host="127.0.0.1")
        )

        backend = _get_backend(config)
        assert isinstance(backend, MCPStreamableHTTPBackend)
        assert backend.host == "127.0.0.1"
        assert backend.port == 7432

    def test_raises_for_unsupported_backend(self):
        """Test error for unsupported backend types."""
        from spellbook_mcp.swarm_tools import _get_backend

        config = CoordinationConfig(
            backend=CoordinationBackend.N8N
        )

        with pytest.raises(ValueError, match="Unsupported backend type"):
            _get_backend(config)

    def test_raises_for_none_backend(self):
        """Test error when backend is NONE."""
        from spellbook_mcp.swarm_tools import _get_backend

        config = CoordinationConfig(backend=CoordinationBackend.NONE)

        with pytest.raises(ValueError, match="No coordination backend configured"):
            _get_backend(config)


class TestAsyncToSyncConversion:
    """Tests for async to sync conversion in tools."""

    def test_swarm_create_handles_async_backend(self, coordination_config):
        """Test that swarm_create properly handles async backend methods."""
        from spellbook_mcp.swarm_tools import swarm_create

        async_backend = AsyncMock()
        async_backend.create_swarm.return_value = "swarm-456"

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=async_backend):
                result = swarm_create(
                    feature="test-feature",
                    manifest_path="/path/to/manifest.json"
                )

                # Should successfully convert async to sync
                assert result["swarm_id"] == "swarm-456"
                assert result["status"] == "created"

    def test_swarm_monitor_handles_async_backend(self, coordination_config):
        """Test that swarm_monitor properly handles async backend methods."""
        from spellbook_mcp.swarm_tools import swarm_monitor

        async_backend = AsyncMock()
        async_backend.get_status.return_value = {
            "swarm_id": "swarm-789",
            "status": "complete",
            "workers_registered": 2,
            "workers_complete": 2,
            "workers_failed": 0,
            "ready_for_merge": True
        }

        with patch("spellbook_mcp.swarm_tools.load_coordination_config", return_value=coordination_config):
            with patch("spellbook_mcp.swarm_tools._get_backend", return_value=async_backend):
                result = swarm_monitor(swarm_id="swarm-789")

                # Should successfully convert async to sync
                assert result["swarm_id"] == "swarm-789"
                assert result["status"] == "complete"
                assert result["ready_for_merge"] is True
