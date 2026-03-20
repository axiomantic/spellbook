"""SQLAlchemy ORM models for coordination.db.

Models match the CREATE TABLE statements in spellbook/coordination/state.py
(StateManager._init_database, lines 32-89).

Tables: swarms, workers, events
"""

import json

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from spellbook.db.base import CoordinationBase


class Swarm(CoordinationBase):
    """A swarm coordinating parallel work packets."""

    __tablename__ = "swarms"

    swarm_id = Column(String, primary_key=True)
    feature = Column(String, nullable=False)
    manifest_path = Column(String, nullable=False)
    status = Column(String, nullable=False)
    auto_merge = Column(Boolean, default=False)
    notify_on_complete = Column(Boolean, default=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)

    workers = relationship(
        "SwarmWorker",
        back_populates="swarm",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    events = relationship(
        "SwarmEvent",
        back_populates="swarm",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'complete', 'failed')",
            name="ck_swarms_status",
        ),
        Index("idx_swarms_status", "status"),
        Index("idx_swarms_created_at", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "swarm_id": self.swarm_id,
            "feature": self.feature,
            "manifest_path": self.manifest_path,
            "status": self.status,
            "auto_merge": self.auto_merge,
            "notify_on_complete": self.notify_on_complete,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


class SwarmWorker(CoordinationBase):
    """A worker registered with a swarm."""

    __tablename__ = "workers"

    worker_id = Column(Integer, primary_key=True, autoincrement=True)
    swarm_id = Column(
        String,
        ForeignKey("swarms.swarm_id", ondelete="CASCADE"),
        nullable=False,
    )
    packet_id = Column(Integer, nullable=False)
    packet_name = Column(String, nullable=False)
    worktree = Column(String, nullable=True)
    status = Column(String, nullable=False)
    tasks_total = Column(Integer, nullable=False)
    tasks_completed = Column(Integer, default=0)
    final_commit = Column(String, nullable=True)
    tests_passed = Column(Boolean, nullable=True)
    review_passed = Column(Boolean, nullable=True)
    registered_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)

    swarm = relationship("Swarm", back_populates="workers")

    __table_args__ = (
        CheckConstraint(
            "status IN ('registered', 'running', 'complete', 'failed')",
            name="ck_workers_status",
        ),
        UniqueConstraint("swarm_id", "packet_id", name="uq_workers_swarm_packet"),
        Index("idx_workers_swarm_status", "swarm_id", "status"),
        Index("idx_workers_packet", "swarm_id", "packet_id"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "swarm_id": self.swarm_id,
            "packet_id": self.packet_id,
            "packet_name": self.packet_name,
            "worktree": self.worktree,
            "status": self.status,
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "final_commit": self.final_commit,
            "tests_passed": self.tests_passed,
            "review_passed": self.review_passed,
            "registered_at": self.registered_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


class SwarmEvent(CoordinationBase):
    """An event logged by a swarm."""

    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    swarm_id = Column(
        String,
        ForeignKey("swarms.swarm_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String, nullable=False)
    packet_id = Column(Integer, nullable=True)
    task_id = Column(String, nullable=True)
    task_name = Column(String, nullable=True)
    # "commit" is a SQL keyword; use Column("commit", ...) for the DDL name
    commit = Column("commit", String, nullable=True)
    error_type = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    recoverable = Column(Boolean, nullable=True)
    event_data = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    swarm = relationship("Swarm", back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'worker_registered', 'progress', 'worker_complete', "
            "'worker_error', 'all_complete', 'heartbeat')",
            name="ck_events_event_type",
        ),
        Index("idx_events_swarm", "swarm_id"),
        Index("idx_events_created_at", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary, parsing event_data JSON if possible."""
        event_data = self.event_data
        if event_data is not None:
            try:
                event_data = json.loads(event_data)
            except (json.JSONDecodeError, TypeError):
                pass  # Return raw string if not valid JSON

        return {
            "event_id": self.event_id,
            "swarm_id": self.swarm_id,
            "event_type": self.event_type,
            "packet_id": self.packet_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "commit": self.commit,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "recoverable": self.recoverable,
            "event_data": event_data,
            "created_at": self.created_at,
        }
