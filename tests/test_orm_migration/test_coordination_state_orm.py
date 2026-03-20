"""Tests for coordination StateManager ORM migration.

Verifies that StateManager uses async SQLAlchemy sessions with
Swarm, SwarmWorker, and SwarmEvent ORM models.
"""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from spellbook.db.coordination_models import Swarm, SwarmWorker, SwarmEvent


@pytest.mark.asyncio
class TestCreateSwarmORM:
    """StateManager.create_swarm must use ORM."""

    async def test_create_swarm(self, coordination_session):
        """Create swarm persists a Swarm ORM object."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(
            feature="test-feature",
            manifest_path="/path/to/manifest.json",
            auto_merge=False,
            notify_on_complete=True,
        )

        assert re.match(r"^swarm-\d{8}-\d{6}-[a-f0-9]{6}$", swarm_id)

        # Verify ORM object
        stmt = select(Swarm).where(Swarm.swarm_id == swarm_id)
        swarm = (await coordination_session.execute(stmt)).scalar_one()
        assert swarm.feature == "test-feature"
        assert swarm.manifest_path == "/path/to/manifest.json"
        assert swarm.status == "created"
        assert swarm.auto_merge is False
        assert swarm.notify_on_complete is True
        assert swarm.created_at.endswith("Z")
        assert swarm.completed_at is None


@pytest.mark.asyncio
class TestGetSwarmORM:
    async def test_get_swarm(self, coordination_session):
        """Get swarm returns dict with all fields."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(
            feature="feat",
            manifest_path="/path",
        )

        swarm = await mgr.get_swarm(swarm_id)
        assert swarm["swarm_id"] == swarm_id
        assert swarm["feature"] == "feat"
        assert swarm["status"] == "created"

    async def test_get_swarm_not_found(self, coordination_session):
        """Get nonexistent swarm raises ValueError."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        with pytest.raises(ValueError, match="Swarm not found"):
            await mgr.get_swarm("nonexistent")


@pytest.mark.asyncio
class TestRegisterWorkerORM:
    async def test_register_worker(self, coordination_session):
        """Register worker creates SwarmWorker and SwarmEvent."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(feature="feat", manifest_path="/p")
        worker_id = await mgr.register_worker(
            swarm_id=swarm_id,
            packet_id=1,
            packet_name="track-1",
            tasks_total=5,
            worktree="/worktree",
        )

        assert worker_id > 0

        # Verify worker in DB
        stmt = select(SwarmWorker).where(SwarmWorker.worker_id == worker_id)
        w = (await coordination_session.execute(stmt)).scalar_one()
        assert w.swarm_id == swarm_id
        assert w.packet_id == 1
        assert w.packet_name == "track-1"
        assert w.status == "registered"
        assert w.tasks_total == 5
        assert w.tasks_completed == 0

        # Verify swarm set to running
        swarm = await mgr.get_swarm(swarm_id)
        assert swarm["status"] == "running"

        # Verify event logged
        stmt = select(SwarmEvent).where(
            SwarmEvent.swarm_id == swarm_id,
            SwarmEvent.event_type == "worker_registered",
        )
        events = (await coordination_session.execute(stmt)).scalars().all()
        assert len(events) == 1
        assert events[0].packet_id == 1


@pytest.mark.asyncio
class TestUpdateProgressORM:
    async def test_update_progress(self, coordination_session):
        """Progress update changes worker state and logs event."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(feature="feat", manifest_path="/p")
        await mgr.register_worker(
            swarm_id=swarm_id, packet_id=1,
            packet_name="track-1", tasks_total=5, worktree="/wt",
        )

        await mgr.update_progress(
            swarm_id=swarm_id, packet_id=1,
            task_id="task-2", task_name="Implement",
            status="completed", tasks_completed=2,
            tasks_total=5, commit="abc123",
        )

        # Verify worker updated
        stmt = select(SwarmWorker).where(
            SwarmWorker.swarm_id == swarm_id,
            SwarmWorker.packet_id == 1,
        )
        w = (await coordination_session.execute(stmt)).scalar_one()
        assert w.status == "running"
        assert w.tasks_completed == 2

        # Verify progress event
        stmt = select(SwarmEvent).where(
            SwarmEvent.swarm_id == swarm_id,
            SwarmEvent.event_type == "progress",
        )
        events = (await coordination_session.execute(stmt)).scalars().all()
        assert len(events) == 1
        assert events[0].task_id == "task-2"
        assert events[0].commit == "abc123"


@pytest.mark.asyncio
class TestMarkCompleteORM:
    async def test_mark_complete_single_worker(self, coordination_session):
        """Mark complete updates worker and swarm status."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(feature="feat", manifest_path="/p")
        await mgr.register_worker(
            swarm_id=swarm_id, packet_id=1,
            packet_name="track-1", tasks_total=3, worktree="/wt",
        )

        await mgr.mark_complete(
            swarm_id=swarm_id, packet_id=1,
            final_commit="def456", tests_passed=True,
            review_passed=True,
        )

        # Verify worker
        stmt = select(SwarmWorker).where(
            SwarmWorker.swarm_id == swarm_id,
            SwarmWorker.packet_id == 1,
        )
        w = (await coordination_session.execute(stmt)).scalar_one()
        assert w.status == "complete"
        assert w.final_commit == "def456"
        assert w.tests_passed is True
        assert w.review_passed is True
        assert w.completed_at is not None

        # Verify swarm complete (all workers done)
        swarm = await mgr.get_swarm(swarm_id)
        assert swarm["status"] == "complete"

        # Verify all_complete event
        stmt = select(SwarmEvent).where(
            SwarmEvent.swarm_id == swarm_id,
            SwarmEvent.event_type == "all_complete",
        )
        events = (await coordination_session.execute(stmt)).scalars().all()
        assert len(events) == 1


@pytest.mark.asyncio
class TestRecordErrorORM:
    async def test_non_recoverable_error_fails_worker(self, coordination_session):
        """Non-recoverable error sets worker status to failed."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(feature="feat", manifest_path="/p")
        await mgr.register_worker(
            swarm_id=swarm_id, packet_id=1,
            packet_name="track-1", tasks_total=5, worktree="/wt",
        )

        await mgr.record_error(
            swarm_id=swarm_id, packet_id=1,
            task_id="task-3", error_type="test_failure",
            message="3 tests failed", recoverable=False,
        )

        # Verify worker failed
        stmt = select(SwarmWorker).where(
            SwarmWorker.swarm_id == swarm_id,
            SwarmWorker.packet_id == 1,
        )
        w = (await coordination_session.execute(stmt)).scalar_one()
        assert w.status == "failed"

        # Verify error event
        stmt = select(SwarmEvent).where(
            SwarmEvent.swarm_id == swarm_id,
            SwarmEvent.event_type == "worker_error",
        )
        events = (await coordination_session.execute(stmt)).scalars().all()
        assert len(events) == 1
        assert events[0].error_type == "test_failure"
        assert events[0].error_message == "3 tests failed"
        assert events[0].recoverable is False


@pytest.mark.asyncio
class TestGetEventsORM:
    async def test_get_events_since_id(self, coordination_session):
        """Events filtered by since_event_id."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        swarm_id = await mgr.create_swarm(feature="feat", manifest_path="/p")
        await mgr.register_worker(
            swarm_id=swarm_id, packet_id=1,
            packet_name="track-1", tasks_total=5, worktree="/wt",
        )

        all_events = await mgr.get_events(swarm_id, since_event_id=0)
        assert len(all_events) >= 1
        first_id = all_events[0]["event_id"]

        await mgr.update_progress(
            swarm_id=swarm_id, packet_id=1,
            task_id="t1", task_name="Task 1",
            status="completed", tasks_completed=1,
            tasks_total=5,
        )

        new_events = await mgr.get_events(swarm_id, since_event_id=first_id)
        assert len(new_events) >= 1
        assert all(e["event_id"] > first_id for e in new_events)


@pytest.mark.asyncio
class TestCleanupORM:
    async def test_cleanup_old_swarms(self, coordination_session):
        """Cleanup deletes swarms older than cutoff."""
        from spellbook.coordination.state import StateManager

        mgr = StateManager(session=coordination_session)
        recent_id = await mgr.create_swarm(feature="recent", manifest_path="/p")

        # Insert old swarm directly
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
        old = Swarm(
            swarm_id="swarm-old-123",
            feature="old-feature",
            manifest_path="/p",
            status="complete",
            auto_merge=False,
            notify_on_complete=True,
            created_at=old_date,
            updated_at=old_date,
        )
        coordination_session.add(old)
        await coordination_session.flush()

        await mgr.cleanup_old_swarms(days=7)

        # Recent swarm exists
        swarm = await mgr.get_swarm(recent_id)
        assert swarm is not None

        # Old swarm deleted
        with pytest.raises(ValueError, match="Swarm not found"):
            await mgr.get_swarm("swarm-old-123")
