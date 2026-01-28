"""Test Pydantic schemas for coordination protocol."""
import pytest
from datetime import UTC, datetime, timedelta
from pydantic import ValidationError


def test_register_request_valid():
    """Test valid RegisterRequest."""
    from spellbook_mcp.coordination.protocol import RegisterRequest

    req = RegisterRequest(
        packet_id=1,
        packet_name="track-1-backend",
        tasks_total=5,
        worktree="/absolute/path/to/worktree"
    )
    assert req.packet_id == 1
    assert req.packet_name == "track-1-backend"
    assert req.tasks_total == 5


def test_register_request_invalid_packet_id():
    """Test RegisterRequest with invalid packet_id."""
    from spellbook_mcp.coordination.protocol import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest(
            packet_id=0,  # Must be positive
            packet_name="track-1",
            tasks_total=5,
            worktree="/path"
        )


def test_register_request_invalid_packet_name():
    """Test RegisterRequest with invalid packet_name."""
    from spellbook_mcp.coordination.protocol import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest(
            packet_id=1,
            packet_name="Track-1",  # Must be lowercase
            tasks_total=5,
            worktree="/path"
        )


def test_register_request_invalid_tasks_total():
    """Test RegisterRequest with invalid tasks_total."""
    from spellbook_mcp.coordination.protocol import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest(
            packet_id=1,
            packet_name="track-1",
            tasks_total=0,  # Must be positive
            worktree="/path"
        )


def test_progress_request_valid():
    """Test valid ProgressRequest."""
    from spellbook_mcp.coordination.protocol import ProgressRequest

    req = ProgressRequest(
        packet_id=1,
        task_id="task-1",
        task_name="Implement feature",
        status="completed",
        tasks_completed=1,
        tasks_total=5,
        commit="abc123def"
    )
    assert req.packet_id == 1
    assert req.status == "completed"
    assert req.commit == "abc123def"


def test_progress_request_invalid_status():
    """Test ProgressRequest with invalid status."""
    from spellbook_mcp.coordination.protocol import ProgressRequest

    with pytest.raises(ValidationError):
        ProgressRequest(
            packet_id=1,
            task_id="task-1",
            task_name="Test",
            status="invalid",  # Must be started/completed/failed
            tasks_completed=1,
            tasks_total=5
        )


def test_progress_request_invalid_commit():
    """Test ProgressRequest with invalid commit."""
    from spellbook_mcp.coordination.protocol import ProgressRequest

    with pytest.raises(ValidationError):
        ProgressRequest(
            packet_id=1,
            task_id="task-1",
            task_name="Test",
            status="completed",
            tasks_completed=1,
            tasks_total=5,
            commit="INVALID"  # Must be hex
        )


def test_progress_request_tasks_completed_exceeds_total():
    """Test ProgressRequest with tasks_completed > tasks_total."""
    from spellbook_mcp.coordination.protocol import ProgressRequest

    with pytest.raises(ValidationError):
        ProgressRequest(
            packet_id=1,
            task_id="task-1",
            task_name="Test",
            status="completed",
            tasks_completed=10,  # Exceeds total
            tasks_total=5
        )


def test_complete_request_valid():
    """Test valid CompleteRequest."""
    from spellbook_mcp.coordination.protocol import CompleteRequest

    req = CompleteRequest(
        packet_id=1,
        final_commit="abc123def456",
        tests_passed=True,
        review_passed=True
    )
    assert req.packet_id == 1
    assert req.tests_passed is True


def test_complete_request_invalid_commit():
    """Test CompleteRequest with invalid commit."""
    from spellbook_mcp.coordination.protocol import CompleteRequest

    with pytest.raises(ValidationError):
        CompleteRequest(
            packet_id=1,
            final_commit="INVALID",  # Must be hex
            tests_passed=True,
            review_passed=True
        )


def test_error_request_valid():
    """Test valid ErrorRequest."""
    from spellbook_mcp.coordination.protocol import ErrorRequest

    req = ErrorRequest(
        packet_id=1,
        task_id="task-3",
        error_type="test_failure",
        message="3 tests failed",
        recoverable=False
    )
    assert req.packet_id == 1
    assert req.recoverable is False


def test_error_request_message_too_long():
    """Test ErrorRequest with message too long."""
    from spellbook_mcp.coordination.protocol import ErrorRequest

    with pytest.raises(ValidationError):
        ErrorRequest(
            packet_id=1,
            task_id="task-1",
            error_type="error",
            message="x" * 6000,  # Exceeds max length
            recoverable=True
        )


def test_swarm_create_response():
    """Test SwarmCreateResponse."""
    from spellbook_mcp.coordination.protocol import SwarmCreateResponse

    resp = SwarmCreateResponse(
        swarm_id="swarm-123",
        endpoint="http://localhost:7432/swarm/swarm-123",
        created_at=datetime.now(UTC),
        auto_merge=False,
        notify_on_complete=True
    )
    assert resp.swarm_id == "swarm-123"
    assert resp.auto_merge is False


def test_register_response():
    """Test RegisterResponse."""
    from spellbook_mcp.coordination.protocol import RegisterResponse

    resp = RegisterResponse(
        registered=True,
        packet_id=1,
        packet_name="track-1",
        swarm_id="swarm-123",
        registered_at=datetime.now(UTC)
    )
    assert resp.registered is True
    assert resp.packet_id == 1


def test_swarm_status():
    """Test SwarmStatus."""
    from spellbook_mcp.coordination.protocol import SwarmStatus, WorkerStatus

    status = SwarmStatus(
        swarm_id="swarm-123",
        status="running",
        workers_registered=2,
        workers_complete=0,
        workers_failed=0,
        ready_for_merge=False,
        workers=[
            WorkerStatus(
                packet_id=1,
                packet_name="track-1",
                status="running",
                tasks_completed=3,
                tasks_total=5,
                last_update=datetime.now(UTC)
            )
        ],
        created_at=datetime.now(UTC),
        last_update=datetime.now(UTC)
    )
    assert status.status == "running"
    assert status.workers_registered == 2
    assert len(status.workers) == 1
