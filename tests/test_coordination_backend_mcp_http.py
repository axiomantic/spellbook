"""Tests for MCP Streamable HTTP coordination backend."""
import json
import pytest
import bigfoot
from spellbook.coordination.backends.mcp_streamable_http import MCPStreamableHTTPBackend
from spellbook.coordination.backends.base import CoordinationBackend

pytestmark = pytest.mark.anyio


class _FakeResponse:
    """Fake httpx response with configurable json() return and raise_for_status()."""

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class _FakeClient:
    """Fake httpx.AsyncClient that records calls and returns configured responses."""

    def __init__(self):
        self.post_calls = []
        self.get_calls = []
        self.stream_calls = []
        self._post_response = None
        self._get_response = None
        self._stream_response = None

    def set_post_response(self, data):
        self._post_response = _FakeResponse(data)

    def set_get_response(self, data):
        self._get_response = _FakeResponse(data)

    def set_stream_response(self, response):
        self._stream_response = response

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self._post_response

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self._get_response

    def stream(self, method, url, **kwargs):
        self.stream_calls.append((method, url, kwargs))
        return self._stream_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        pass


class _FakeStreamResponse:
    """Fake streaming response for SSE tests."""

    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        pass


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

    async def test_create_swarm_sends_post_request(self, backend_config):
        """create_swarm should send POST request to /swarm/create."""
        fake_client = _FakeClient()
        fake_client.set_post_response({
            "swarm_id": "swarm-test-123",
            "endpoint": "http://localhost:7432/swarm/swarm-test-123",
            "created_at": "2024-01-01T00:00:00Z",
            "auto_merge": False,
            "notify_on_complete": True
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            await backend.create_swarm(
                feature="test-feature",
                manifest_path="/path/to/manifest.json",
                auto_merge=False
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(fake_client.post_calls) == 1
        url, kwargs = fake_client.post_calls[0]
        assert url == "http://localhost:7432/swarm/create"
        assert kwargs == {
            "params": {
                "feature": "test-feature",
                "manifest_path": "/path/to/manifest.json",
                "auto_merge": False,
                "notify_on_complete": True
            }
        }

    async def test_create_swarm_returns_swarm_id(self, backend_config):
        """create_swarm should return swarm_id from response."""
        fake_client = _FakeClient()
        fake_client.set_post_response({
            "swarm_id": "swarm-test-abc",
            "endpoint": "http://localhost:7432/swarm/swarm-test-abc",
            "created_at": "2024-01-01T00:00:00Z",
            "auto_merge": False,
            "notify_on_complete": True
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            swarm_id = await backend.create_swarm(
                feature="test",
                manifest_path="/manifest.json",
                auto_merge=True
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert swarm_id == "swarm-test-abc"


class TestRegisterWorker:
    """Test register_worker method."""

    async def test_register_worker_sends_post_request(self, backend_config):
        """register_worker should send POST request to /swarm/{swarm_id}/register."""
        fake_client = _FakeClient()
        fake_client.set_post_response({
            "registered": True,
            "packet_id": 1,
            "packet_name": "core-api",
            "swarm_id": "swarm-123",
            "registered_at": "2024-01-01T00:00:00Z"
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            await backend.register_worker(
                swarm_id="swarm-123",
                packet_id=1,
                packet_name="core-api",
                tasks_total=5,
                worktree="/tmp/worktree-1"
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(fake_client.post_calls) == 1
        url, _kwargs = fake_client.post_calls[0]
        assert url == "http://localhost:7432/swarm/swarm-123/register"

    async def test_register_worker_returns_response_dict(self, backend_config):
        """register_worker should return response dictionary."""
        response_data = {
            "registered": True,
            "packet_id": 2,
            "packet_name": "ui-components",
            "swarm_id": "swarm-xyz",
            "registered_at": "2024-01-01T00:00:00Z"
        }
        fake_client = _FakeClient()
        fake_client.set_post_response(response_data)

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            result = await backend.register_worker(
                swarm_id="swarm-xyz",
                packet_id=2,
                packet_name="ui-components",
                tasks_total=3,
                worktree="/tmp/worktree-2"
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert result == response_data


class TestReportProgress:
    """Test report_progress method."""

    async def test_report_progress_sends_post_request(self, backend_config):
        """report_progress should send POST request to /swarm/{swarm_id}/progress."""
        fake_client = _FakeClient()
        fake_client.set_post_response({
            "acknowledged": True,
            "packet_id": 1,
            "task_id": "task-1",
            "tasks_completed": 2,
            "tasks_total": 5,
            "timestamp": "2024-01-01T00:00:00Z"
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            await backend.report_progress(
                swarm_id="swarm-123",
                packet_id=1,
                task_id="task-1",
                task_name="Implement API",
                status="completed",
                tasks_completed=2,
                tasks_total=5,
                commit="abc1234"
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(fake_client.post_calls) == 1
        url, _kwargs = fake_client.post_calls[0]
        assert url == "http://localhost:7432/swarm/swarm-123/progress"


class TestReportComplete:
    """Test report_complete method."""

    async def test_report_complete_sends_post_request(self, backend_config):
        """report_complete should send POST request to /swarm/{swarm_id}/complete."""
        fake_client = _FakeClient()
        fake_client.set_post_response({
            "acknowledged": True,
            "packet_id": 1,
            "final_commit": "abc1234567",
            "completed_at": "2024-01-01T00:00:00Z",
            "swarm_complete": False,
            "remaining_workers": 2
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            await backend.report_complete(
                swarm_id="swarm-123",
                packet_id=1,
                final_commit="abc1234567",
                tests_passed=True,
                review_passed=True
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(fake_client.post_calls) == 1
        url, _kwargs = fake_client.post_calls[0]
        assert url == "http://localhost:7432/swarm/swarm-123/complete"


class TestReportError:
    """Test report_error method."""

    async def test_report_error_sends_post_request(self, backend_config):
        """report_error should send POST request to /swarm/{swarm_id}/error."""
        fake_client = _FakeClient()
        fake_client.set_post_response({
            "acknowledged": True,
            "packet_id": 1,
            "error_logged": True,
            "retry_scheduled": True,
            "retry_in_seconds": 5
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            await backend.report_error(
                swarm_id="swarm-123",
                packet_id=1,
                task_id="task-1",
                error_type="TestFailure",
                message="Tests failed",
                recoverable=True
            )

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(fake_client.post_calls) == 1
        url, _kwargs = fake_client.post_calls[0]
        assert url == "http://localhost:7432/swarm/swarm-123/error"


class TestGetStatus:
    """Test get_status method."""

    async def test_get_status_sends_get_request(self, backend_config):
        """get_status should send GET request to /swarm/{swarm_id}/status."""
        fake_client = _FakeClient()
        fake_client.set_get_response({
            "swarm_id": "swarm-123",
            "status": "running",
            "workers_registered": 3,
            "workers_complete": 1,
            "workers_failed": 0,
            "ready_for_merge": False,
            "workers": [],
            "created_at": "2024-01-01T00:00:00Z",
            "last_update": "2024-01-01T00:05:00Z"
        })

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            await backend.get_status(swarm_id="swarm-123")

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(fake_client.get_calls) == 1
        url, kwargs = fake_client.get_calls[0]
        assert url == "http://localhost:7432/swarm/swarm-123/status"
        assert kwargs == {}

    async def test_get_status_returns_status_dict(self, backend_config):
        """get_status should return status dictionary."""
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
        fake_client = _FakeClient()
        fake_client.set_get_response(status_data)

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            result = await backend.get_status(swarm_id="swarm-123")

        mock_async_client.assert_call(args=(), kwargs={})
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

    async def test_subscribe_events_yields_events(self, backend_config):
        """subscribe_events should yield event dictionaries from SSE stream."""
        sse_lines = [
            "id: 1",
            "event: worker_registered",
            'data: {"event_type": "worker_registered", "packet_id": 1}',
            "",
            "id: 2",
            "event: progress",
            'data: {"event_type": "progress", "packet_id": 1, "task_id": "task-1"}',
            "",
        ]

        fake_stream_response = _FakeStreamResponse(sse_lines)
        fake_client = _FakeClient()
        fake_client.set_stream_response(fake_stream_response)

        mock_async_client = bigfoot.mock("httpx:AsyncClient")
        mock_async_client.returns(fake_client)

        async with bigfoot:
            backend = MCPStreamableHTTPBackend(backend_config)
            events = []
            async for event in backend.subscribe_events("swarm-123"):
                events.append(event)

        mock_async_client.assert_call(args=(), kwargs={})
        assert len(events) == 2
        assert events[0]["event_type"] == "worker_registered"
        assert events[1]["event_type"] == "progress"
