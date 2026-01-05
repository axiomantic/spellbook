"""Test SQLite state management."""
import re
import pytest
from pathlib import Path
from datetime import datetime, timedelta, UTC


@pytest.fixture
def state_manager(tmp_path):
    """Create temporary state manager."""
    # Import here to ensure test fails if module doesn't exist
    from spellbook_mcp.coordination.state import StateManager

    db_path = tmp_path / "test.db"
    return StateManager(str(db_path))


def test_create_swarm(state_manager):
    """Test creating a swarm with full field verification."""
    swarm_id = state_manager.create_swarm(
        feature="test-feature",
        manifest_path="/path/to/manifest.json",
        auto_merge=False,
        notify_on_complete=True
    )

    # Verify swarm_id structure: swarm-YYYYMMDD-HHMMSS-XXXXXX
    assert re.match(r"^swarm-\d{8}-\d{6}-[a-f0-9]{6}$", swarm_id), \
        f"Swarm ID '{swarm_id}' doesn't match expected format"

    # Verify ALL fields in database
    swarm = state_manager.get_swarm(swarm_id)
    assert swarm["swarm_id"] == swarm_id
    assert swarm["feature"] == "test-feature"
    assert swarm["manifest_path"] == "/path/to/manifest.json"
    assert swarm["status"] == "created"
    assert swarm["auto_merge"] == False
    assert swarm["notify_on_complete"] == True

    # Verify timestamps are valid ISO8601 with Z suffix
    assert swarm["created_at"].endswith("Z")
    assert swarm["updated_at"].endswith("Z")
    datetime.fromisoformat(swarm["created_at"].replace("Z", "+00:00"))
    assert swarm["created_at"] == swarm["updated_at"]  # Same on creation
    assert swarm["completed_at"] is None


def test_register_worker(state_manager):
    """Test registering a worker with database verification."""
    swarm_id = state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json"
    )

    worker_id = state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1-backend",
        tasks_total=5,
        worktree="/path/to/worktree"
    )
    assert worker_id > 0

    # VERIFY WORKER IN DATABASE (Finding #1 fix)
    conn = state_manager._get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workers WHERE worker_id = ?",
            (worker_id,)
        ).fetchone()

        assert row is not None, "Worker not found in database"
        assert row["worker_id"] == worker_id
        assert row["swarm_id"] == swarm_id
        assert row["packet_id"] == 1
        assert row["packet_name"] == "track-1-backend"
        assert row["worktree"] == "/path/to/worktree"
        assert row["status"] == "registered"
        assert row["tasks_total"] == 5
        assert row["tasks_completed"] == 0
        assert row["final_commit"] is None
        assert row["tests_passed"] is None
        assert row["review_passed"] is None
        assert row["completed_at"] is None
    finally:
        conn.close()

    # VERIFY REGISTRATION EVENT LOGGED (Finding #13 fix)
    events = state_manager.get_events(swarm_id, since_event_id=0)
    registration_events = [e for e in events if e["event_type"] == "worker_registered"]
    assert len(registration_events) == 1
    reg_event = registration_events[0]
    assert reg_event["packet_id"] == 1

    # Verify swarm status changed to running
    swarm = state_manager.get_swarm(swarm_id)
    assert swarm["status"] == "running"


def test_update_progress(state_manager):
    """Test updating worker progress with state verification."""
    swarm_id = state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json"
    )
    state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree"
    )

    state_manager.update_progress(
        swarm_id=swarm_id,
        packet_id=1,
        task_id="task-2",
        task_name="Implement feature",
        status="completed",
        tasks_completed=2,
        tasks_total=5,
        commit="abc123"
    )

    # VERIFY WORKER STATE UPDATED (Finding #2 fix)
    conn = state_manager._get_connection()
    try:
        worker = conn.execute(
            "SELECT * FROM workers WHERE swarm_id = ? AND packet_id = ?",
            (swarm_id, 1)
        ).fetchone()

        assert worker is not None
        assert worker["status"] == "running"
        assert worker["tasks_completed"] == 2
    finally:
        conn.close()

    # VERIFY EVENT CONTENT
    events = state_manager.get_events(swarm_id, since_event_id=0)
    assert len(events) == 2  # Exact count: registration + progress

    progress_events = [e for e in events if e["event_type"] == "progress"]
    assert len(progress_events) == 1

    progress_event = progress_events[0]
    assert progress_event["packet_id"] == 1
    assert progress_event["task_id"] == "task-2"
    assert progress_event["task_name"] == "Implement feature"
    assert progress_event["commit"] == "abc123"


def test_mark_complete(state_manager):
    """Test marking worker as complete with database verification."""
    swarm_id = state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json"
    )
    state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree"
    )

    state_manager.mark_complete(
        swarm_id=swarm_id,
        packet_id=1,
        final_commit="def456",
        tests_passed=True,
        review_passed=True
    )

    # VERIFY WORKER STATE IN DATABASE (Finding #4 fix)
    conn = state_manager._get_connection()
    try:
        worker = conn.execute(
            "SELECT * FROM workers WHERE swarm_id = ? AND packet_id = ?",
            (swarm_id, 1)
        ).fetchone()

        assert worker["status"] == "complete"
        assert worker["final_commit"] == "def456"
        assert worker["tests_passed"] == 1  # SQLite stores as 1/0
        assert worker["review_passed"] == 1
        assert worker["completed_at"] is not None
        datetime.fromisoformat(worker["completed_at"].replace("Z", "+00:00"))
    finally:
        conn.close()

    # VERIFY EVENT
    events = state_manager.get_events(swarm_id, since_event_id=0)
    complete_events = [e for e in events if e["event_type"] == "worker_complete"]
    assert len(complete_events) == 1

    complete_event = complete_events[0]
    assert complete_event["packet_id"] == 1
    assert complete_event["commit"] == "def456"


def test_record_error(state_manager):
    """Test recording an error with worker status verification."""
    swarm_id = state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json"
    )
    state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree"
    )

    state_manager.record_error(
        swarm_id=swarm_id,
        packet_id=1,
        task_id="task-3",
        error_type="test_failure",
        message="3 tests failed",
        recoverable=False
    )

    # VERIFY WORKER STATUS CHANGED TO FAILED (Finding #5 fix)
    conn = state_manager._get_connection()
    try:
        worker = conn.execute(
            "SELECT status FROM workers WHERE swarm_id = ? AND packet_id = ?",
            (swarm_id, 1)
        ).fetchone()

        assert worker["status"] == "failed"
    finally:
        conn.close()

    # VERIFY EVENT CONTENT
    events = state_manager.get_events(swarm_id, since_event_id=0)
    error_events = [e for e in events if e["event_type"] == "worker_error"]
    assert len(error_events) == 1

    error_event = error_events[0]
    assert error_event["error_type"] == "test_failure"
    assert error_event["error_message"] == "3 tests failed"
    assert error_event["task_id"] == "task-3"
    assert error_event["packet_id"] == 1
    assert error_event["recoverable"] == 0  # SQLite stores as 0


def test_get_events_since_id(state_manager):
    """Test getting events since specific ID."""
    swarm_id = state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json"
    )
    state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree"
    )

    # Get all events
    all_events = state_manager.get_events(swarm_id, since_event_id=0)
    assert len(all_events) >= 1

    first_event_id = all_events[0]["event_id"]

    # Add another event
    state_manager.update_progress(
        swarm_id=swarm_id,
        packet_id=1,
        task_id="task-1",
        task_name="First task",
        status="completed",
        tasks_completed=1,
        tasks_total=5,
        commit="abc123"
    )

    # Get only new events
    new_events = state_manager.get_events(swarm_id, since_event_id=first_event_id)
    assert len(new_events) >= 1
    assert all(e["event_id"] > first_event_id for e in new_events)


def test_cleanup_old_swarms(state_manager):
    """Test cleanup of old swarms."""
    # Create a recent swarm
    recent_swarm_id = state_manager.create_swarm(
        feature="recent",
        manifest_path="/path/to/manifest.json"
    )

    # Create an old swarm by directly manipulating the database
    old_date = (datetime.utcnow() - timedelta(days=10)).isoformat() + "Z"
    conn = state_manager._get_connection()
    try:
        conn.execute("""
            INSERT INTO swarms (swarm_id, feature, manifest_path, status,
                              auto_merge, notify_on_complete, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("swarm-old-123", "old-feature", "/path", "complete",
              False, True, old_date, old_date))
        conn.commit()
    finally:
        conn.close()

    # Cleanup swarms older than 7 days
    state_manager.cleanup_old_swarms(days=7)

    # Recent swarm should still exist
    assert state_manager.get_swarm(recent_swarm_id) is not None

    # Old swarm should be deleted
    with pytest.raises(ValueError, match="Swarm not found"):
        state_manager.get_swarm("swarm-old-123")
