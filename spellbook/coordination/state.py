"""Async SQLAlchemy state management for coordination server.

Uses Swarm, SwarmWorker, SwarmEvent ORM models with async sessions.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.db.coordination_models import Swarm, SwarmWorker, SwarmEvent


class StateManager:
    """Manages swarm coordination state via SQLAlchemy ORM.

    Accepts an async session for dependency injection (testing).
    When no session is provided, acquires one from the coordination
    session factory.
    """

    def __init__(
        self,
        database_path: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ):
        """Initialize state manager.

        Args:
            database_path: Legacy parameter (ignored when session provided)
            session: Optional async session (injected for testing)
        """
        self._session = session
        self._database_path = database_path

    async def _get_session(self) -> AsyncSession:
        """Get the injected session or create one from the factory.

        When an injected session is provided (testing), uses that directly.
        Otherwise, creates a session from the coordination session factory.
        Note: when using the factory session, the caller context manager
        in get_coordination_session handles commit/rollback.
        """
        if self._session is not None:
            return self._session

        # Lazy import to avoid circular deps at module load time
        from spellbook.db import get_coordination_session

        # Create and store session for the duration of this manager
        self._ctx = get_coordination_session()
        session = await self._ctx.__aenter__()
        self._session = session
        return session

    async def create_swarm(
        self,
        feature: str,
        manifest_path: str,
        auto_merge: bool = False,
        notify_on_complete: bool = True,
    ) -> str:
        """Create a new swarm. Returns swarm_id."""
        session = await self._get_session()
        swarm_id = f"swarm-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        swarm = Swarm(
            swarm_id=swarm_id,
            feature=feature,
            manifest_path=manifest_path,
            status="created",
            auto_merge=auto_merge,
            notify_on_complete=notify_on_complete,
            created_at=now,
            updated_at=now,
        )
        session.add(swarm)
        await session.flush()
        return swarm_id

    async def get_swarm(self, swarm_id: str) -> Dict[str, Any]:
        """Get swarm by ID."""
        session = await self._get_session()
        stmt = select(Swarm).where(Swarm.swarm_id == swarm_id)
        result = await session.execute(stmt)
        swarm = result.scalar_one_or_none()
        if not swarm:
            raise ValueError(f"Swarm not found: {swarm_id}")
        return swarm.to_dict()

    async def register_worker(
        self,
        swarm_id: str,
        packet_id: int,
        packet_name: str,
        tasks_total: int,
        worktree: str,
    ) -> int:
        """Register a worker with the swarm. Returns worker_id."""
        session = await self._get_session()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        worker = SwarmWorker(
            swarm_id=swarm_id,
            packet_id=packet_id,
            packet_name=packet_name,
            worktree=worktree,
            status="registered",
            tasks_total=tasks_total,
            tasks_completed=0,
            registered_at=now,
            updated_at=now,
        )
        session.add(worker)
        await session.flush()

        # Update swarm status to running
        stmt = (
            update(Swarm)
            .where(Swarm.swarm_id == swarm_id)
            .values(status="running", updated_at=now)
        )
        await session.execute(stmt)

        # Log event
        event = SwarmEvent(
            swarm_id=swarm_id,
            event_type="worker_registered",
            packet_id=packet_id,
            event_data=packet_name,
            created_at=now,
        )
        session.add(event)
        await session.flush()

        return worker.worker_id

    async def update_progress(
        self,
        swarm_id: str,
        packet_id: int,
        task_id: str,
        task_name: str,
        status: str,
        tasks_completed: int,
        tasks_total: int,
        commit: Optional[str] = None,
    ):
        """Update worker progress."""
        session = await self._get_session()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Update worker
        stmt = (
            update(SwarmWorker)
            .where(
                SwarmWorker.swarm_id == swarm_id,
                SwarmWorker.packet_id == packet_id,
            )
            .values(
                status="running",
                tasks_completed=tasks_completed,
                updated_at=now,
            )
        )
        await session.execute(stmt)

        # Log event
        event_data = json.dumps({
            "task_id": task_id,
            "task_name": task_name,
            "status": status,
            "tasks_completed": tasks_completed,
            "tasks_total": tasks_total,
        })

        event = SwarmEvent(
            swarm_id=swarm_id,
            event_type="progress",
            packet_id=packet_id,
            task_id=task_id,
            task_name=task_name,
            commit=commit,
            event_data=event_data,
            created_at=now,
        )
        session.add(event)
        await session.flush()

    async def mark_complete(
        self,
        swarm_id: str,
        packet_id: int,
        final_commit: str,
        tests_passed: bool,
        review_passed: bool,
    ):
        """Mark worker as complete."""
        session = await self._get_session()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Update worker
        stmt = (
            update(SwarmWorker)
            .where(
                SwarmWorker.swarm_id == swarm_id,
                SwarmWorker.packet_id == packet_id,
            )
            .values(
                status="complete",
                final_commit=final_commit,
                tests_passed=tests_passed,
                review_passed=review_passed,
                completed_at=now,
                updated_at=now,
            )
        )
        await session.execute(stmt)

        # Log event
        event_data = json.dumps({
            "final_commit": final_commit,
            "tests_passed": tests_passed,
            "review_passed": review_passed,
        })

        event = SwarmEvent(
            swarm_id=swarm_id,
            event_type="worker_complete",
            packet_id=packet_id,
            commit=final_commit,
            event_data=event_data,
            created_at=now,
        )
        session.add(event)
        await session.flush()

        # Check if all workers are complete
        total_stmt = select(func.count()).select_from(SwarmWorker).where(
            SwarmWorker.swarm_id == swarm_id
        )
        complete_stmt = select(func.count()).select_from(SwarmWorker).where(
            SwarmWorker.swarm_id == swarm_id,
            SwarmWorker.status == "complete",
        )

        total = (await session.execute(total_stmt)).scalar()
        completed = (await session.execute(complete_stmt)).scalar()

        if total > 0 and total == completed:
            # All workers complete
            stmt = (
                update(Swarm)
                .where(Swarm.swarm_id == swarm_id)
                .values(status="complete", completed_at=now, updated_at=now)
            )
            await session.execute(stmt)

            all_complete_event = SwarmEvent(
                swarm_id=swarm_id,
                event_type="all_complete",
                created_at=now,
            )
            session.add(all_complete_event)
            await session.flush()

    async def record_error(
        self,
        swarm_id: str,
        packet_id: int,
        task_id: str,
        error_type: str,
        message: str,
        recoverable: bool,
    ):
        """Record an error from a worker."""
        session = await self._get_session()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Update worker status if non-recoverable
        if not recoverable:
            stmt = (
                update(SwarmWorker)
                .where(
                    SwarmWorker.swarm_id == swarm_id,
                    SwarmWorker.packet_id == packet_id,
                )
                .values(status="failed", updated_at=now)
            )
            await session.execute(stmt)

        # Log event
        event = SwarmEvent(
            swarm_id=swarm_id,
            event_type="worker_error",
            packet_id=packet_id,
            task_id=task_id,
            error_type=error_type,
            error_message=message,
            recoverable=recoverable,
            created_at=now,
        )
        session.add(event)
        await session.flush()

    async def get_events(
        self,
        swarm_id: str,
        since_event_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get events for a swarm since a specific event ID."""
        session = await self._get_session()
        stmt = (
            select(SwarmEvent)
            .where(
                SwarmEvent.swarm_id == swarm_id,
                SwarmEvent.event_id > since_event_id,
            )
            .order_by(SwarmEvent.event_id.asc())
        )

        result = await session.execute(stmt)
        events = []
        for row in result.scalars().all():
            events.append(row.to_dict())

        return events

    async def cleanup_old_swarms(self, days: int = 7):
        """Delete swarms older than specified days."""
        session = await self._get_session()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

        stmt = delete(Swarm).where(Swarm.created_at < cutoff)
        await session.execute(stmt)
        await session.flush()
