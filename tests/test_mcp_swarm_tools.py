"""Tests for MCP swarm coordination tools."""
import asyncio

import pytest

from spellbook.core.preferences import CoordinationConfig, CoordinationBackend, MCPSSEConfig


class _FakeBackend:
    """Fake async backend for testing swarm tools."""

    def __init__(self, **returns):
        self._returns = returns

    async def create_swarm(self, feature, manifest_path, auto_merge):
        return self._returns.get("create_swarm", "swarm-123")

    async def register_worker(self, swarm_id, packet_id, packet_name, tasks_total, worktree):
        return self._returns.get("register_worker", {"status": "registered", "packet_id": 1})

    async def report_progress(self, swarm_id, packet_id, task_id, task_name, status, tasks_completed, tasks_total, commit):
        return self._returns.get("report_progress", {"status": "recorded", "tasks_completed": 2, "tasks_total": 5})

    async def report_complete(self, swarm_id, packet_id, final_commit, tests_passed, review_passed):
        return self._returns.get("report_complete", {"status": "complete", "all_workers_done": False})

    async def report_error(self, swarm_id, packet_id, task_id, error_type, message, recoverable):
        return self._returns.get("report_error", {"status": "error_recorded", "will_retry": True})

    async def get_status(self, swarm_id):
        return self._returns.get("get_status", {
            "swarm_id": "swarm-123",
            "status": "running",
            "workers_registered": 3,
            "workers_complete": 1,
            "workers_failed": 0,
            "ready_for_merge": False,
        })


@pytest.fixture
def fake_backend():
    """Create a fake coordination backend with default return values."""
    return _FakeBackend()


@pytest.fixture
def coordination_config():
    """Create a coordination config."""
    return CoordinationConfig(
        backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
        mcp_sse=MCPSSEConfig(port=7432, host="127.0.0.1")
    )


def _patch_swarm(monkeypatch, config, backend):
    """Patch swarm module's load_coordination_config and _get_backend."""
    monkeypatch.setattr(
        "spellbook.coordination.swarm.load_coordination_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "spellbook.coordination.swarm._get_backend",
        lambda c: backend,
    )


class TestSwarmCreate:
    """Tests for swarm_create tool."""

    def test_creates_swarm_successfully(self, monkeypatch, fake_backend, coordination_config):
        """Test successful swarm creation."""
        from spellbook.coordination.swarm import swarm_create

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

        result = swarm_create(
            feature="user-authentication",
            manifest_path="/path/to/manifest.json",
            auto_merge=True
        )

        assert result["swarm_id"] == "swarm-123"
        assert result["status"] == "created"

    def test_auto_merge_defaults_to_false(self, monkeypatch, fake_backend, coordination_config):
        """Test auto_merge defaults to False."""
        from spellbook.coordination.swarm import swarm_create

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

        result = swarm_create(
            feature="test-feature",
            manifest_path="/path/to/manifest.json"
        )

        assert result["swarm_id"] == "swarm-123"
        assert result["status"] == "created"

    def test_raises_when_backend_none(self, monkeypatch):
        """Test error when backend is NONE."""
        from spellbook.coordination.swarm import swarm_create

        config = CoordinationConfig(backend=CoordinationBackend.NONE)
        monkeypatch.setattr(
            "spellbook.coordination.swarm.load_coordination_config",
            lambda: config,
        )

        with pytest.raises(ValueError, match="No coordination backend configured"):
            swarm_create(
                feature="test",
                manifest_path="/path"
            )


class TestSwarmRegister:
    """Tests for swarm_register tool."""

    def test_registers_worker_successfully(self, monkeypatch, fake_backend, coordination_config):
        """Test successful worker registration."""
        from spellbook.coordination.swarm import swarm_register

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

        result = swarm_register(
            swarm_id="swarm-123",
            packet_id=1,
            packet_name="auth-packet",
            tasks_total=5,
            worktree="/path/to/worktree"
        )

        assert result["status"] == "registered"
        assert result["packet_id"] == 1


class TestSwarmProgress:
    """Tests for swarm_progress tool."""

    def test_reports_progress_successfully(self, monkeypatch, fake_backend, coordination_config):
        """Test successful progress reporting."""
        from spellbook.coordination.swarm import swarm_progress

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

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

    def test_commit_optional(self, monkeypatch, fake_backend, coordination_config):
        """Test commit parameter is optional."""
        from spellbook.coordination.swarm import swarm_progress

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

        result = swarm_progress(
            swarm_id="swarm-123",
            packet_id=1,
            task_id="task-1",
            task_name="Task name",
            status="started",
            tasks_completed=0,
            tasks_total=5
        )

        assert result["status"] == "recorded"


class TestSwarmComplete:
    """Tests for swarm_complete tool."""

    def test_reports_completion_successfully(self, monkeypatch, fake_backend, coordination_config):
        """Test successful completion reporting."""
        from spellbook.coordination.swarm import swarm_complete

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

        result = swarm_complete(
            swarm_id="swarm-123",
            packet_id=1,
            final_commit="abc1234",
            tests_passed=True,
            review_passed=True
        )

        assert result["status"] == "complete"
        assert result["all_workers_done"] is False


class TestSwarmError:
    """Tests for swarm_error tool."""

    def test_reports_error_successfully(self, monkeypatch, fake_backend, coordination_config):
        """Test successful error reporting."""
        from spellbook.coordination.swarm import swarm_error

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

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


class TestSwarmMonitor:
    """Tests for swarm_monitor tool."""

    def test_gets_status_successfully(self, monkeypatch, fake_backend, coordination_config):
        """Test successful status retrieval."""
        from spellbook.coordination.swarm import swarm_monitor

        _patch_swarm(monkeypatch, coordination_config, fake_backend)

        result = swarm_monitor(swarm_id="swarm-123")

        assert result["swarm_id"] == "swarm-123"
        assert result["status"] == "running"
        assert result["workers_registered"] == 3
        assert result["workers_complete"] == 1
        assert result["workers_failed"] == 0
        assert result["ready_for_merge"] is False


class TestBackendInitialization:
    """Tests for backend initialization."""

    def test_gets_mcp_http_backend(self):
        """Test getting MCP HTTP backend."""
        from spellbook.coordination.swarm import _get_backend
        from spellbook.coordination.backends.mcp_streamable_http import MCPStreamableHTTPBackend

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
        from spellbook.coordination.swarm import _get_backend

        config = CoordinationConfig(
            backend=CoordinationBackend.N8N
        )

        with pytest.raises(ValueError, match="Unsupported backend type"):
            _get_backend(config)

    def test_raises_for_none_backend(self):
        """Test error when backend is NONE."""
        from spellbook.coordination.swarm import _get_backend

        config = CoordinationConfig(backend=CoordinationBackend.NONE)

        with pytest.raises(ValueError, match="No coordination backend configured"):
            _get_backend(config)


class TestAsyncToSyncConversion:
    """Tests for async to sync conversion in tools."""

    def test_swarm_create_handles_async_backend(self, monkeypatch, coordination_config):
        """Test that swarm_create properly handles async backend methods."""
        from spellbook.coordination.swarm import swarm_create

        fake = _FakeBackend(create_swarm="swarm-456")
        _patch_swarm(monkeypatch, coordination_config, fake)

        result = swarm_create(
            feature="test-feature",
            manifest_path="/path/to/manifest.json"
        )

        # Should successfully convert async to sync
        assert result["swarm_id"] == "swarm-456"
        assert result["status"] == "created"

    def test_swarm_monitor_handles_async_backend(self, monkeypatch, coordination_config):
        """Test that swarm_monitor properly handles async backend methods."""
        from spellbook.coordination.swarm import swarm_monitor

        fake = _FakeBackend(get_status={
            "swarm_id": "swarm-789",
            "status": "complete",
            "workers_registered": 2,
            "workers_complete": 2,
            "workers_failed": 0,
            "ready_for_merge": True,
        })
        _patch_swarm(monkeypatch, coordination_config, fake)

        result = swarm_monitor(swarm_id="swarm-789")

        # Should successfully convert async to sync
        assert result["swarm_id"] == "swarm-789"
        assert result["status"] == "complete"
        assert result["ready_for_merge"] is True
