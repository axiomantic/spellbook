"""Test async ORM state management for coordination.

These tests verify StateManager behavior through the ORM interface.
Replaces the original sync sqlite3 tests after the ORM migration.
"""

import re
import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from spellbook.db.coordination_models import Swarm, SwarmWorker, SwarmEvent


@pytest.fixture
def coordination_session_fixture(request):
    """Delegate to conftest coordination_session via indirect fixture."""
    # This will use the conftest from test_orm_migration if available,
    # otherwise we define it inline
    pass


# Use the conftest from test_orm_migration
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def state_manager():
    """Create StateManager with in-memory ORM session."""
    from sqlalchemy import event as sa_event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from spellbook.db.base import CoordinationBase
    from spellbook.coordination.state import StateManager

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def _pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sa_event.listen(engine.sync_engine, "connect", _pragmas)

    async with engine.begin() as conn:
        await conn.run_sync(CoordinationBase.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield StateManager(session=session)

    await engine.dispose()


async def test_create_swarm(state_manager):
    """Test creating a swarm with full field verification."""
    swarm_id = await state_manager.create_swarm(
        feature="test-feature",
        manifest_path="/path/to/manifest.json",
        auto_merge=False,
        notify_on_complete=True,
    )

    assert re.match(r"^swarm-\d{8}-\d{6}-[a-f0-9]{6}$", swarm_id), \
        f"Swarm ID '{swarm_id}' doesn't match expected format"

    swarm = await state_manager.get_swarm(swarm_id)
    assert swarm["swarm_id"] == swarm_id
    assert swarm["feature"] == "test-feature"
    assert swarm["manifest_path"] == "/path/to/manifest.json"
    assert swarm["status"] == "created"
    assert swarm["auto_merge"] is False
    assert swarm["notify_on_complete"] is True
    assert swarm["created_at"].endswith("Z")
    assert swarm["updated_at"].endswith("Z")
    datetime.fromisoformat(swarm["created_at"].replace("Z", "+00:00"))
    assert swarm["created_at"] == swarm["updated_at"]
    assert swarm["completed_at"] is None


async def test_register_worker(state_manager):
    """Test registering a worker with database verification."""
    swarm_id = await state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json",
    )

    worker_id = await state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1-backend",
        tasks_total=5,
        worktree="/path/to/worktree",
    )
    assert worker_id > 0

    # Verify registration event logged
    events = await state_manager.get_events(swarm_id, since_event_id=0)
    registration_events = [e for e in events if e["event_type"] == "worker_registered"]
    assert len(registration_events) == 1
    assert registration_events[0]["packet_id"] == 1

    # Verify swarm status changed to running
    swarm = await state_manager.get_swarm(swarm_id)
    assert swarm["status"] == "running"


async def test_update_progress(state_manager):
    """Test updating worker progress with state verification."""
    swarm_id = await state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json",
    )
    await state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree",
    )

    await state_manager.update_progress(
        swarm_id=swarm_id,
        packet_id=1,
        task_id="task-2",
        task_name="Implement feature",
        status="completed",
        tasks_completed=2,
        tasks_total=5,
        commit="abc123",
    )

    # Verify event content
    events = await state_manager.get_events(swarm_id, since_event_id=0)
    assert len(events) == 2  # registration + progress

    progress_events = [e for e in events if e["event_type"] == "progress"]
    assert len(progress_events) == 1
    assert progress_events[0]["packet_id"] == 1
    assert progress_events[0]["task_id"] == "task-2"
    assert progress_events[0]["task_name"] == "Implement feature"
    assert progress_events[0]["commit"] == "abc123"


async def test_mark_complete(state_manager):
    """Test marking worker as complete with database verification."""
    swarm_id = await state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json",
    )
    await state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree",
    )

    await state_manager.mark_complete(
        swarm_id=swarm_id,
        packet_id=1,
        final_commit="def456",
        tests_passed=True,
        review_passed=True,
    )

    # Verify event
    events = await state_manager.get_events(swarm_id, since_event_id=0)
    complete_events = [e for e in events if e["event_type"] == "worker_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["packet_id"] == 1
    assert complete_events[0]["commit"] == "def456"

    # Verify swarm completed
    swarm = await state_manager.get_swarm(swarm_id)
    assert swarm["status"] == "complete"


async def test_record_error(state_manager):
    """Test recording an error with worker status verification."""
    swarm_id = await state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json",
    )
    await state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree",
    )

    await state_manager.record_error(
        swarm_id=swarm_id,
        packet_id=1,
        task_id="task-3",
        error_type="test_failure",
        message="3 tests failed",
        recoverable=False,
    )

    # Verify event content
    events = await state_manager.get_events(swarm_id, since_event_id=0)
    error_events = [e for e in events if e["event_type"] == "worker_error"]
    assert len(error_events) == 1
    assert error_events[0]["error_type"] == "test_failure"
    assert error_events[0]["error_message"] == "3 tests failed"
    assert error_events[0]["task_id"] == "task-3"
    assert error_events[0]["packet_id"] == 1
    assert error_events[0]["recoverable"] is False


async def test_get_events_since_id(state_manager):
    """Test getting events since specific ID."""
    swarm_id = await state_manager.create_swarm(
        feature="test",
        manifest_path="/path/to/manifest.json",
    )
    await state_manager.register_worker(
        swarm_id=swarm_id,
        packet_id=1,
        packet_name="track-1",
        tasks_total=5,
        worktree="/path/to/worktree",
    )

    all_events = await state_manager.get_events(swarm_id, since_event_id=0)
    assert len(all_events) >= 1
    first_event_id = all_events[0]["event_id"]

    await state_manager.update_progress(
        swarm_id=swarm_id,
        packet_id=1,
        task_id="task-1",
        task_name="First task",
        status="completed",
        tasks_completed=1,
        tasks_total=5,
        commit="abc123",
    )

    new_events = await state_manager.get_events(swarm_id, since_event_id=first_event_id)
    assert len(new_events) >= 1
    assert all(e["event_id"] > first_event_id for e in new_events)


async def test_cleanup_old_swarms(state_manager):
    """Test cleanup of old swarms."""
    recent_swarm_id = await state_manager.create_swarm(
        feature="recent",
        manifest_path="/path/to/manifest.json",
    )

    # Insert old swarm via ORM
    session = await state_manager._get_session()
    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    old = Swarm(
        swarm_id="swarm-old-123",
        feature="old-feature",
        manifest_path="/path",
        status="complete",
        auto_merge=False,
        notify_on_complete=True,
        created_at=old_date,
        updated_at=old_date,
    )
    session.add(old)
    await session.flush()

    await state_manager.cleanup_old_swarms(days=7)

    # Recent swarm should still exist
    swarm = await state_manager.get_swarm(recent_swarm_id)
    assert swarm is not None

    # Old swarm should be deleted
    with pytest.raises(ValueError, match="Swarm not found"):
        await state_manager.get_swarm("swarm-old-123")
