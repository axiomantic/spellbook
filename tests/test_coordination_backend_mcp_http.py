"""Tests for MCP Streamable HTTP coordination backend."""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from spellbook.coordination.backends.mcp_streamable_http import MCPStreamableHTTPBackend
from spellbook.coordination.backends.base import CoordinationBackend

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    with patch("spellbook.coordination.backends.mcp_streamable_http.httpx.AsyncClient") as mock_client:
        yield mock_client


@pytest.fixture
def backend_config():
    """Default backend configuration."""
    return {
        "backend": "mcp-streamable-http",
        "host": "localhost",
        "port": 7432
    }


class TestMCPStreamableHTTPBackendInstantiation:
    """Test instantiation and initialization of MCPStreamableHTTPBackend."""

    def test_is_subclass_of_coordination_backend(self):
        """MCPStreamableHTTPBackend should be a subclass of CoordinationBackend."""
        assert issubclass(MCPStreamableHTTPBackend, CoordinationBackend)

    def test_can_instantiate_with_config(self, backend_config):
        """Should be able to instantiate MCPStreamableHTTPBackend with config."""
        backend = MCPStreamableHTTPBackend(backend_config)

        assert backend is not None
        assert isinstance(backend, MCPStreamableHTTPBackend)
        assert isinstance(backend, CoordinationBackend)

    def test_stores_host_from_config(self, backend_config):
        """Should store host from config."""
        backend = MCPStreamableHTTPBackend(backend_config)
        assert backend.host == "localhost"

    def test_stores_port_from_config(self, backend_config):
        """Should store port from config."""
        backend = MCPStreamableHTTPBackend(backend_config)
        assert backend.port == 7432

    def test_constructs_base_url(self, backend_config):
        """Should construct base URL from host and port."""
        backend = MCPStreamableHTTPBackend(backend_config)
        assert backend.base_url == "http://localhost:7432"

    def test_uses_default_port_if_missing(self):
        """Should use default port 7432 if not in config."""
        config = {"backend": "mcp-streamable-http", "host": "localhost"}
        backend = MCPStreamableHTTPBackend(config)
        assert backend.port == 7432

    def test_uses_default_host_if_missing(self):
        """Should use default host 127.0.0.1 if not in config."""
        config = {"backend": "mcp-streamable-http", "port": 8000}
        backend = MCPStreamableHTTPBackend(config)
        assert backend.host == "127.0.0.1"


class TestCreateSwarm:
    """Test create_swarm method."""

    async def test_create_swarm_sends_post_request(self, backend_config, mock_httpx_client):
        """create_swarm should send POST request to /swarm/create."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "swarm_id": "swarm-test-123",
            "endpoint": "http://localhost:7432/swarm/swarm-test-123",
            "created_at": "2024-01-01T00:00:00Z",
            "auto_merge": False,
            "notify_on_complete": True
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        swarm_id = await backend.create_swarm(
            feature="test-feature",
            manifest_path="/path/to/manifest.json",
            auto_merge=False
        )

        mock_client_instance.post.assert_called_once_with(
            "http://localhost:7432/swarm/create",
            params={
                "feature": "test-feature",
                "manifest_path": "/path/to/manifest.json",
                "auto_merge": False,
                "notify_on_complete": True
            }
        )

    
    async def test_create_swarm_returns_swarm_id(self, backend_config, mock_httpx_client):
        """create_swarm should return swarm_id from response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "swarm_id": "swarm-test-abc",
            "endpoint": "http://localhost:7432/swarm/swarm-test-abc",
            "created_at": "2024-01-01T00:00:00Z",
            "auto_merge": False,
            "notify_on_complete": True
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        swarm_id = await backend.create_swarm(
            feature="test",
            manifest_path="/manifest.json",
            auto_merge=True
        )

        assert swarm_id == "swarm-test-abc"


class TestRegisterWorker:
    """Test register_worker method."""

    
    async def test_register_worker_sends_post_request(self, backend_config, mock_httpx_client):
        """register_worker should send POST request to /swarm/{swarm_id}/register."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "registered": True,
            "packet_id": 1,
            "packet_name": "core-api",
            "swarm_id": "swarm-123",
            "registered_at": "2024-01-01T00:00:00Z"
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.register_worker(
            swarm_id="swarm-123",
            packet_id=1,
            packet_name="core-api",
            tasks_total=5,
            worktree="/tmp/worktree-1"
        )

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "http://localhost:7432/swarm/swarm-123/register"

    
    async def test_register_worker_returns_response_dict(self, backend_config, mock_httpx_client):
        """register_worker should return response dictionary."""
        mock_response = Mock()
        response_data = {
            "registered": True,
            "packet_id": 2,
            "packet_name": "ui-components",
            "swarm_id": "swarm-xyz",
            "registered_at": "2024-01-01T00:00:00Z"
        }
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.register_worker(
            swarm_id="swarm-xyz",
            packet_id=2,
            packet_name="ui-components",
            tasks_total=3,
            worktree="/tmp/worktree-2"
        )

        assert result == response_data


class TestReportProgress:
    """Test report_progress method."""

    
    async def test_report_progress_sends_post_request(self, backend_config, mock_httpx_client):
        """report_progress should send POST request to /swarm/{swarm_id}/progress."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "acknowledged": True,
            "packet_id": 1,
            "task_id": "task-1",
            "tasks_completed": 2,
            "tasks_total": 5,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.report_progress(
            swarm_id="swarm-123",
            packet_id=1,
            task_id="task-1",
            task_name="Implement API",
            status="completed",
            tasks_completed=2,
            tasks_total=5,
            commit="abc1234"
        )

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "http://localhost:7432/swarm/swarm-123/progress"


class TestReportComplete:
    """Test report_complete method."""

    
    async def test_report_complete_sends_post_request(self, backend_config, mock_httpx_client):
        """report_complete should send POST request to /swarm/{swarm_id}/complete."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "acknowledged": True,
            "packet_id": 1,
            "final_commit": "abc1234567",
            "completed_at": "2024-01-01T00:00:00Z",
            "swarm_complete": False,
            "remaining_workers": 2
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.report_complete(
            swarm_id="swarm-123",
            packet_id=1,
            final_commit="abc1234567",
            tests_passed=True,
            review_passed=True
        )

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "http://localhost:7432/swarm/swarm-123/complete"


class TestReportError:
    """Test report_error method."""

    
    async def test_report_error_sends_post_request(self, backend_config, mock_httpx_client):
        """report_error should send POST request to /swarm/{swarm_id}/error."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "acknowledged": True,
            "packet_id": 1,
            "error_logged": True,
            "retry_scheduled": True,
            "retry_in_seconds": 5
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.report_error(
            swarm_id="swarm-123",
            packet_id=1,
            task_id="task-1",
            error_type="TestFailure",
            message="Tests failed",
            recoverable=True
        )

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "http://localhost:7432/swarm/swarm-123/error"


class TestGetStatus:
    """Test get_status method."""

    
    async def test_get_status_sends_get_request(self, backend_config, mock_httpx_client):
        """get_status should send GET request to /swarm/{swarm_id}/status."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "swarm_id": "swarm-123",
            "status": "running",
            "workers_registered": 3,
            "workers_complete": 1,
            "workers_failed": 0,
            "ready_for_merge": False,
            "workers": [],
            "created_at": "2024-01-01T00:00:00Z",
            "last_update": "2024-01-01T00:05:00Z"
        }
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.get_status(swarm_id="swarm-123")

        mock_client_instance.get.assert_called_once_with(
            "http://localhost:7432/swarm/swarm-123/status"
        )

    
    async def test_get_status_returns_status_dict(self, backend_config, mock_httpx_client):
        """get_status should return status dictionary."""
        mock_response = Mock()
        status_data = {
            "swarm_id": "swarm-123",
            "status": "complete",
            "workers_registered": 2,
            "workers_complete": 2,
            "workers_failed": 0,
            "ready_for_merge": True,
            "workers": [],
            "created_at": "2024-01-01T00:00:00Z",
            "last_update": "2024-01-01T01:00:00Z"
        }
        mock_response.json.return_value = status_data
        mock_response.raise_for_status = Mock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        backend = MCPStreamableHTTPBackend(backend_config)
        result = await backend.get_status(swarm_id="swarm-123")

        assert result == status_data


class TestSubscribeEvents:
    """Test subscribe_events method."""

    
    async def test_subscribe_events_is_async_generator(self, backend_config):
        """subscribe_events should return an async generator."""
        backend = MCPStreamableHTTPBackend(backend_config)
        result = backend.subscribe_events("swarm-123")

        # Check it's an async generator
        assert hasattr(result, "__aiter__")
        assert hasattr(result, "__anext__")


    async def test_subscribe_events_yields_events(self, backend_config, mock_httpx_client):
        """subscribe_events should yield event dictionaries from SSE stream."""
        # Mock SSE response
        mock_response = Mock()

        # Simulate SSE events
        async def mock_lines():
            yield "id: 1"
            yield "event: worker_registered"
            yield 'data: {"event_type": "worker_registered", "packet_id": 1}'
            yield ""
            yield "id: 2"
            yield "event: progress"
            yield 'data: {"event_type": "progress", "packet_id": 1, "task_id": "task-1"}'
            yield ""

        mock_response.aiter_lines.return_value = mock_lines()

        # Create mock context manager for stream using MagicMock
        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock(return_value=mock_stream_context)
        mock_httpx_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=None)

        backend = MCPStreamableHTTPBackend(backend_config)
        events = []

        async for event in backend.subscribe_events("swarm-123"):
            events.append(event)

        assert len(events) == 2
        assert events[0]["event_type"] == "worker_registered"
        assert events[1]["event_type"] == "progress"
