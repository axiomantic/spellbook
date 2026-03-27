"""Test SwarmWorker helper class for worker integration."""
import pytest
from pathlib import Path
import bigfoot
import json


def test_swarm_worker_initialization():
    """Test SwarmWorker initializes with correct attributes."""
    from spellbook.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/path/to/worktree",
        tasks_total=10
    )

    assert worker.swarm_id == "test-swarm-123"
    assert worker.packet_id == 1
    assert worker.packet_name == "backend-api"
    assert worker.worktree == "/path/to/worktree"
    assert worker.tasks_total == 10
    assert worker.tasks_completed == 0


def test_swarm_worker_checkpoint_path():
    """Test SwarmWorker computes correct checkpoint file path."""
    from spellbook.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/path/to/worktree",
        tasks_total=10
    )

    expected_path = Path("/path/to/worktree/.spellbook/checkpoints/packet-1-backend-api.json")
    assert worker.checkpoint_path == expected_path


def _make_worker(tmp_path):
    """Create a SwarmWorker pointed at tmp_path for real filesystem writes."""
    from spellbook.coordination.worker import SwarmWorker

    return SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree=str(tmp_path),
        tasks_total=10
    )


def _read_checkpoint(tmp_path):
    """Read and parse the checkpoint file written to tmp_path."""
    checkpoint_path = tmp_path / ".spellbook" / "checkpoints" / "packet-1-backend-api.json"
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


class _FakeBackend:
    """Fake backend with async methods that record calls and return configured values."""

    def __init__(self):
        self.calls = []

    async def register_worker(self, **kwargs):
        self.calls.append(("register_worker", kwargs))
        return {
            "registered": True,
            "packet_id": 1,
            "packet_name": "backend-api",
            "swarm_id": "test-swarm-123",
            "registered_at": "2026-01-05T10:00:00Z"
        }

    async def report_progress(self, **kwargs):
        self.calls.append(("report_progress", kwargs))
        return {
            "acknowledged": True,
            "packet_id": 1,
            "task_id": kwargs.get("task_id", "task-1"),
            "tasks_completed": kwargs.get("tasks_completed", 1),
            "tasks_total": kwargs.get("tasks_total", 10),
            "timestamp": "2026-01-05T10:01:00Z"
        }

    async def report_complete(self, **kwargs):
        self.calls.append(("report_complete", kwargs))
        return {
            "acknowledged": True,
            "packet_id": 1,
            "final_commit": kwargs.get("final_commit", "def5678"),
            "completed_at": "2026-01-05T10:05:00Z",
            "swarm_complete": False,
            "remaining_workers": 2
        }

    async def report_error(self, **kwargs):
        self.calls.append(("report_error", kwargs))
        return {
            "acknowledged": True,
            "packet_id": 1,
            "error_logged": True,
            "retry_scheduled": True,
            "retry_in_seconds": 30
        }


@pytest.mark.asyncio
async def test_register_creates_checkpoint_and_calls_backend(tmp_path):
    """Test register() writes marker file and calls MCP backend."""
    worker = _make_worker(tmp_path)
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend)

    async with bigfoot:
        result = await worker.register()

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify checkpoint written to disk
    checkpoint_data = _read_checkpoint(tmp_path)
    assert checkpoint_data["event"] == "registered"
    assert checkpoint_data["packet_id"] == 1
    assert checkpoint_data["packet_name"] == "backend-api"
    assert checkpoint_data["tasks_total"] == 10
    assert checkpoint_data["tasks_completed"] == 0

    # Verify backend called
    assert len(backend.calls) == 1
    method, kwargs = backend.calls[0]
    assert method == "register_worker"
    assert kwargs == {
        "swarm_id": "test-swarm-123",
        "packet_id": 1,
        "packet_name": "backend-api",
        "tasks_total": 10,
        "worktree": str(tmp_path),
    }

    # Verify response
    assert result["registered"] is True
    assert result["packet_id"] == 1


@pytest.mark.asyncio
async def test_report_progress_increments_counter(tmp_path):
    """Test report_progress() increments tasks_completed counter."""
    worker = _make_worker(tmp_path)
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend)

    async with bigfoot:
        result = await worker.report_progress(
            task_id="task-1",
            task_name="Implement authentication",
            status="completed",
            commit="abc1234"
        )

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify counter incremented
    assert worker.tasks_completed == 1

    # Verify backend called with incremented counter
    assert len(backend.calls) == 1
    method, kwargs = backend.calls[0]
    assert method == "report_progress"
    assert kwargs == {
        "swarm_id": "test-swarm-123",
        "packet_id": 1,
        "task_id": "task-1",
        "task_name": "Implement authentication",
        "status": "completed",
        "tasks_completed": 1,
        "tasks_total": 10,
        "commit": "abc1234",
    }


@pytest.mark.asyncio
async def test_report_progress_writes_checkpoint(tmp_path):
    """Test report_progress() writes checkpoint marker file."""
    worker = _make_worker(tmp_path)
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend)

    async with bigfoot:
        await worker.report_progress(
            task_id="task-1",
            task_name="Implement authentication",
            status="completed"
        )

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify checkpoint written
    checkpoint_data = _read_checkpoint(tmp_path)
    assert checkpoint_data["event"] == "progress"
    assert checkpoint_data["task_id"] == "task-1"
    assert checkpoint_data["task_name"] == "Implement authentication"
    assert checkpoint_data["status"] == "completed"
    assert checkpoint_data["tasks_completed"] == 1


@pytest.mark.asyncio
async def test_report_progress_handles_optional_commit(tmp_path):
    """Test report_progress() handles optional commit parameter."""
    worker = _make_worker(tmp_path)
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend)

    async with bigfoot:
        await worker.report_progress(
            task_id="task-1",
            task_name="Task 1",
            status="completed"
        )

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify backend called without commit (commit=None)
    method, kwargs = backend.calls[0]
    assert kwargs["commit"] is None


@pytest.mark.asyncio
async def test_report_complete_writes_checkpoint_and_calls_backend(tmp_path):
    """Test report_complete() writes marker file and calls backend."""
    worker = _make_worker(tmp_path)
    worker.tasks_completed = 10
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend)

    async with bigfoot:
        result = await worker.report_complete(
            final_commit="def5678",
            tests_passed=True,
            review_passed=True
        )

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify checkpoint written
    checkpoint_data = _read_checkpoint(tmp_path)
    assert checkpoint_data["event"] == "complete"
    assert checkpoint_data["final_commit"] == "def5678"
    assert checkpoint_data["tests_passed"] is True
    assert checkpoint_data["review_passed"] is True
    assert checkpoint_data["tasks_completed"] == 10

    # Verify backend called
    method, kwargs = backend.calls[0]
    assert method == "report_complete"
    assert kwargs == {
        "swarm_id": "test-swarm-123",
        "packet_id": 1,
        "final_commit": "def5678",
        "tests_passed": True,
        "review_passed": True,
    }


@pytest.mark.asyncio
async def test_report_error_writes_checkpoint_and_calls_backend(tmp_path):
    """Test report_error() writes marker file and calls backend."""
    worker = _make_worker(tmp_path)
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend)

    async with bigfoot:
        result = await worker.report_error(
            task_id="task-1",
            error_type="network_error",
            message="Connection timeout",
            recoverable=True
        )

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify checkpoint written
    checkpoint_data = _read_checkpoint(tmp_path)
    assert checkpoint_data["event"] == "error"
    assert checkpoint_data["task_id"] == "task-1"
    assert checkpoint_data["error_type"] == "network_error"
    assert checkpoint_data["message"] == "Connection timeout"
    assert checkpoint_data["recoverable"] is True

    # Verify backend called
    method, kwargs = backend.calls[0]
    assert method == "report_error"
    assert kwargs == {
        "swarm_id": "test-swarm-123",
        "packet_id": 1,
        "task_id": "task-1",
        "error_type": "network_error",
        "message": "Connection timeout",
        "recoverable": True,
    }


@pytest.mark.asyncio
async def test_report_progress_multiple_tasks_increments_correctly(tmp_path):
    """Test multiple progress reports increment counter correctly."""
    worker = _make_worker(tmp_path)
    backend = _FakeBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(backend).returns(backend).returns(backend)

    async with bigfoot:
        await worker.report_progress("task-1", "Task 1", "completed")
        assert worker.tasks_completed == 1

        await worker.report_progress("task-2", "Task 2", "completed")
        assert worker.tasks_completed == 2

        await worker.report_progress("task-3", "Task 3", "completed")
        assert worker.tasks_completed == 3

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))
    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))
    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))


@pytest.mark.asyncio
async def test_dual_write_behavior_on_failure(tmp_path):
    """Test that checkpoint is written even if backend call fails."""
    worker = _make_worker(tmp_path)

    class _FailingBackend:
        async def register_worker(self, **kwargs):
            raise Exception("Network error")

    failing_backend = _FailingBackend()

    mock_get_backend = bigfoot.mock("spellbook.coordination.worker:get_backend")
    mock_get_backend.returns(failing_backend)

    async with bigfoot:
        with pytest.raises(Exception, match="Network error"):
            await worker.register()

    mock_get_backend.assert_call(args=("mcp-streamable-http", {}))

    # Verify checkpoint was written before backend call failed
    checkpoint_data = _read_checkpoint(tmp_path)
    assert checkpoint_data["event"] == "registered"
