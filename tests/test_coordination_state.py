"""Test SQLite state management."""
import pytest
from pathlib import Path
from datetime import datetime, timedelta


@pytest.fixture
def state_manager(tmp_path):
    """Create temporary state manager."""
    # Import here to ensure test fails if module doesn't exist
    from spellbook.coordination.state import StateManager

    db_path = tmp_path / "test.db"
    return StateManager(str(db_path))


def test_create_swarm(state_manager):
    """Test creating a swarm."""
    swarm_id = state_manager.create_swarm(
        feature="test-feature",
        manifest_path="/path/to/manifest.json",
        auto_merge=False,
        notify_on_complete=True
    )
    assert swarm_id.startswith("swarm-")

    swarm = state_manager.get_swarm(swarm_id)
    assert swarm["feature"] == "test-feature"
    assert swarm["status"] == "created"


def test_register_worker(state_manager):
    """Test registering a worker."""
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

    swarm = state_manager.get_swarm(swarm_id)
    assert swarm["status"] == "running"


def test_update_progress(state_manager):
    """Test updating worker progress."""
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

    events = state_manager.get_events(swarm_id, since_event_id=0)
    assert len(events) >= 2  # registration + progress


def test_mark_complete(state_manager):
    """Test marking worker as complete."""
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

    events = state_manager.get_events(swarm_id, since_event_id=0)
    complete_events = [e for e in events if e["event_type"] == "worker_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["packet_id"] == 1


def test_record_error(state_manager):
    """Test recording an error."""
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

    events = state_manager.get_events(swarm_id, since_event_id=0)
    error_events = [e for e in events if e["event_type"] == "worker_error"]
    assert len(error_events) == 1
    assert error_events[0]["error_type"] == "test_failure"


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
