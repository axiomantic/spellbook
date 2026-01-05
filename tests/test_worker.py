"""Test SwarmWorker helper class for worker integration."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import json


def test_swarm_worker_initialization():
    """Test SwarmWorker initializes with correct attributes."""
    from spellbook_mcp.coordination.worker import SwarmWorker

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
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/path/to/worktree",
        tasks_total=10
    )

    expected_path = Path("/path/to/worktree/.spellbook/checkpoints/packet-1-backend-api.json")
    assert worker.checkpoint_path == expected_path


@pytest.mark.asyncio
async def test_register_creates_checkpoint_and_calls_backend():
    """Test register() writes marker file and calls MCP backend."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.register_worker.return_value = {
        "registered": True,
        "packet_id": 1,
        "packet_name": "backend-api",
        "swarm_id": "test-swarm-123",
        "registered_at": "2026-01-05T10:00:00Z"
    }

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir") as mock_mkdir:
            with patch("spellbook_mcp.coordination.worker.Path.write_text") as mock_write:
                result = await worker.register()

    # Verify checkpoint directory created
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # Verify marker file written
    assert mock_write.call_count == 1
    checkpoint_data = json.loads(mock_write.call_args[0][0])
    assert checkpoint_data["event"] == "registered"
    assert checkpoint_data["packet_id"] == 1
    assert checkpoint_data["packet_name"] == "backend-api"
    assert checkpoint_data["tasks_total"] == 10
    assert checkpoint_data["tasks_completed"] == 0

    # Verify backend called
    mock_backend.register_worker.assert_called_once_with(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        tasks_total=10,
        worktree="/tmp/test-worktree"
    )

    # Verify response
    assert result["registered"] is True
    assert result["packet_id"] == 1


@pytest.mark.asyncio
async def test_report_progress_increments_counter():
    """Test report_progress() increments tasks_completed counter."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.report_progress.return_value = {
        "acknowledged": True,
        "packet_id": 1,
        "task_id": "task-1",
        "tasks_completed": 1,
        "tasks_total": 10,
        "timestamp": "2026-01-05T10:01:00Z"
    }

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir"):
            with patch("spellbook_mcp.coordination.worker.Path.write_text"):
                result = await worker.report_progress(
                    task_id="task-1",
                    task_name="Implement authentication",
                    status="completed",
                    commit="abc1234"
                )

    # Verify counter incremented
    assert worker.tasks_completed == 1

    # Verify backend called with incremented counter
    mock_backend.report_progress.assert_called_once_with(
        swarm_id="test-swarm-123",
        packet_id=1,
        task_id="task-1",
        task_name="Implement authentication",
        status="completed",
        tasks_completed=1,
        tasks_total=10,
        commit="abc1234"
    )


@pytest.mark.asyncio
async def test_report_progress_writes_checkpoint():
    """Test report_progress() writes checkpoint marker file."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.report_progress.return_value = {
        "acknowledged": True,
        "packet_id": 1,
        "task_id": "task-1",
        "tasks_completed": 1,
        "tasks_total": 10,
        "timestamp": "2026-01-05T10:01:00Z"
    }

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir") as mock_mkdir:
            with patch("spellbook_mcp.coordination.worker.Path.write_text") as mock_write:
                await worker.report_progress(
                    task_id="task-1",
                    task_name="Implement authentication",
                    status="completed"
                )

    # Verify checkpoint written
    assert mock_write.call_count == 1
    checkpoint_data = json.loads(mock_write.call_args[0][0])
    assert checkpoint_data["event"] == "progress"
    assert checkpoint_data["task_id"] == "task-1"
    assert checkpoint_data["task_name"] == "Implement authentication"
    assert checkpoint_data["status"] == "completed"
    assert checkpoint_data["tasks_completed"] == 1


@pytest.mark.asyncio
async def test_report_progress_handles_optional_commit():
    """Test report_progress() handles optional commit parameter."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.report_progress.return_value = {"acknowledged": True}

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir"):
            with patch("spellbook_mcp.coordination.worker.Path.write_text"):
                # Without commit
                await worker.report_progress(
                    task_id="task-1",
                    task_name="Task 1",
                    status="completed"
                )

    # Verify backend called without commit
    call_args = mock_backend.report_progress.call_args
    assert call_args.kwargs["commit"] is None


@pytest.mark.asyncio
async def test_report_complete_writes_checkpoint_and_calls_backend():
    """Test report_complete() writes marker file and calls backend."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )
    worker.tasks_completed = 10

    mock_backend = AsyncMock()
    mock_backend.report_complete.return_value = {
        "acknowledged": True,
        "packet_id": 1,
        "final_commit": "def5678",
        "completed_at": "2026-01-05T10:05:00Z",
        "swarm_complete": False,
        "remaining_workers": 2
    }

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir"):
            with patch("spellbook_mcp.coordination.worker.Path.write_text") as mock_write:
                result = await worker.report_complete(
                    final_commit="def5678",
                    tests_passed=True,
                    review_passed=True
                )

    # Verify checkpoint written
    checkpoint_data = json.loads(mock_write.call_args[0][0])
    assert checkpoint_data["event"] == "complete"
    assert checkpoint_data["final_commit"] == "def5678"
    assert checkpoint_data["tests_passed"] is True
    assert checkpoint_data["review_passed"] is True
    assert checkpoint_data["tasks_completed"] == 10

    # Verify backend called
    mock_backend.report_complete.assert_called_once_with(
        swarm_id="test-swarm-123",
        packet_id=1,
        final_commit="def5678",
        tests_passed=True,
        review_passed=True
    )


@pytest.mark.asyncio
async def test_report_error_writes_checkpoint_and_calls_backend():
    """Test report_error() writes marker file and calls backend."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.report_error.return_value = {
        "acknowledged": True,
        "packet_id": 1,
        "error_logged": True,
        "retry_scheduled": True,
        "retry_in_seconds": 30
    }

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir"):
            with patch("spellbook_mcp.coordination.worker.Path.write_text") as mock_write:
                result = await worker.report_error(
                    task_id="task-1",
                    error_type="network_error",
                    message="Connection timeout",
                    recoverable=True
                )

    # Verify checkpoint written
    checkpoint_data = json.loads(mock_write.call_args[0][0])
    assert checkpoint_data["event"] == "error"
    assert checkpoint_data["task_id"] == "task-1"
    assert checkpoint_data["error_type"] == "network_error"
    assert checkpoint_data["message"] == "Connection timeout"
    assert checkpoint_data["recoverable"] is True

    # Verify backend called
    mock_backend.report_error.assert_called_once_with(
        swarm_id="test-swarm-123",
        packet_id=1,
        task_id="task-1",
        error_type="network_error",
        message="Connection timeout",
        recoverable=True
    )


@pytest.mark.asyncio
async def test_report_progress_multiple_tasks_increments_correctly():
    """Test multiple progress reports increment counter correctly."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.report_progress.return_value = {"acknowledged": True}

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir"):
            with patch("spellbook_mcp.coordination.worker.Path.write_text"):
                await worker.report_progress("task-1", "Task 1", "completed")
                assert worker.tasks_completed == 1

                await worker.report_progress("task-2", "Task 2", "completed")
                assert worker.tasks_completed == 2

                await worker.report_progress("task-3", "Task 3", "completed")
                assert worker.tasks_completed == 3


@pytest.mark.asyncio
async def test_dual_write_behavior_on_failure():
    """Test that checkpoint is written even if backend call fails."""
    from spellbook_mcp.coordination.worker import SwarmWorker

    worker = SwarmWorker(
        swarm_id="test-swarm-123",
        packet_id=1,
        packet_name="backend-api",
        worktree="/tmp/test-worktree",
        tasks_total=10
    )

    mock_backend = AsyncMock()
    mock_backend.register_worker.side_effect = Exception("Network error")

    with patch("spellbook_mcp.coordination.worker.get_backend", return_value=mock_backend):
        with patch("spellbook_mcp.coordination.worker.Path.mkdir"):
            with patch("spellbook_mcp.coordination.worker.Path.write_text") as mock_write:
                with pytest.raises(Exception, match="Network error"):
                    await worker.register()

    # Verify checkpoint was written before backend call
    assert mock_write.call_count == 1
