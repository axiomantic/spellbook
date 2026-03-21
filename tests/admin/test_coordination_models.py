"""Tests for coordination.db ORM model definitions.

Verifies that SQLAlchemy models match the actual CREATE TABLE statements
in spellbook/coordination/state.py (lines 32-89).
"""

import json

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from spellbook.db.base import CoordinationBase


class TestCoordinationModels:
    """Tests for coordination.db table definitions."""

    @pytest.fixture
    def engine(self):
        from spellbook.db.coordination_models import (  # noqa: F401
            Swarm,
            SwarmEvent,
            SwarmWorker,
        )

        engine = create_engine("sqlite:///:memory:")
        CoordinationBase.metadata.create_all(engine)
        return engine

    # ── Table existence ──────────────────────────────────────────────

    def test_all_tables_created(self, engine):
        """All 3 coordination tables exist after metadata.create_all."""
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert table_names == {"swarms", "workers", "events"}

    # ── Swarm model columns ──────────────────────────────────────────

    def test_swarm_columns(self, engine):
        """Swarm model has exactly the columns from the CREATE TABLE."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("swarms")}
        expected = {
            "swarm_id",
            "feature",
            "manifest_path",
            "status",
            "auto_merge",
            "notify_on_complete",
            "created_at",
            "updated_at",
            "completed_at",
        }
        assert columns == expected

    def test_swarm_primary_key(self, engine):
        """Swarm primary key is swarm_id."""
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("swarms")
        assert pk["constrained_columns"] == ["swarm_id"]

    def test_swarm_to_dict(self, engine):
        """Swarm.to_dict() returns all columns with correct values."""
        from spellbook.db.coordination_models import Swarm

        s = Swarm(
            swarm_id="s-1",
            feature="test-feature",
            manifest_path="/path/to/manifest.json",
            status="created",
            auto_merge=False,
            notify_on_complete=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            completed_at=None,
        )
        d = s.to_dict()
        assert d == {
            "swarm_id": "s-1",
            "feature": "test-feature",
            "manifest_path": "/path/to/manifest.json",
            "status": "created",
            "auto_merge": False,
            "notify_on_complete": True,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
        }

    def test_swarm_to_dict_with_completed_at(self, engine):
        """Swarm.to_dict() includes completed_at when set."""
        from spellbook.db.coordination_models import Swarm

        s = Swarm(
            swarm_id="s-2",
            feature="done",
            manifest_path="/m",
            status="complete",
            auto_merge=True,
            notify_on_complete=False,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            completed_at="2026-01-02T00:00:00Z",
        )
        d = s.to_dict()
        assert d == {
            "swarm_id": "s-2",
            "feature": "done",
            "manifest_path": "/m",
            "status": "complete",
            "auto_merge": True,
            "notify_on_complete": False,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "completed_at": "2026-01-02T00:00:00Z",
        }

    def test_swarm_roundtrip(self, engine):
        """Swarm can be persisted and loaded with correct values."""
        from spellbook.db.coordination_models import Swarm

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-rt",
                feature="roundtrip",
                manifest_path="/rt/manifest.json",
                status="created",
                auto_merge=False,
                notify_on_complete=True,
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            session.add(swarm)
            session.commit()

            loaded = session.get(Swarm, "s-rt")
            assert loaded.to_dict() == {
                "swarm_id": "s-rt",
                "feature": "roundtrip",
                "manifest_path": "/rt/manifest.json",
                "status": "created",
                "auto_merge": False,
                "notify_on_complete": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "completed_at": None,
            }

    # ── Worker model columns ─────────────────────────────────────────

    def test_worker_columns(self, engine):
        """SwarmWorker model has exactly the columns from the CREATE TABLE."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("workers")}
        expected = {
            "worker_id",
            "swarm_id",
            "packet_id",
            "packet_name",
            "worktree",
            "status",
            "tasks_total",
            "tasks_completed",
            "final_commit",
            "tests_passed",
            "review_passed",
            "registered_at",
            "updated_at",
            "completed_at",
        }
        assert columns == expected

    def test_worker_primary_key(self, engine):
        """SwarmWorker primary key is worker_id (autoincrement)."""
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("workers")
        assert pk["constrained_columns"] == ["worker_id"]

    def test_worker_to_dict(self, engine):
        """SwarmWorker.to_dict() returns all columns with correct values."""
        from spellbook.db.coordination_models import SwarmWorker

        w = SwarmWorker(
            swarm_id="s-1",
            packet_id=1,
            packet_name="packet-one",
            worktree="/path/to/worktree",
            status="registered",
            tasks_total=5,
            tasks_completed=0,
            final_commit=None,
            tests_passed=None,
            review_passed=None,
            registered_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            completed_at=None,
        )
        d = w.to_dict()
        # worker_id is None before persistence (autoincrement)
        assert d == {
            "worker_id": None,
            "swarm_id": "s-1",
            "packet_id": 1,
            "packet_name": "packet-one",
            "worktree": "/path/to/worktree",
            "status": "registered",
            "tasks_total": 5,
            "tasks_completed": 0,
            "final_commit": None,
            "tests_passed": None,
            "review_passed": None,
            "registered_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
        }

    def test_worker_to_dict_with_completion(self, engine):
        """SwarmWorker.to_dict() reflects completed state."""
        from spellbook.db.coordination_models import SwarmWorker

        w = SwarmWorker(
            swarm_id="s-1",
            packet_id=2,
            packet_name="packet-two",
            worktree="/wt",
            status="complete",
            tasks_total=3,
            tasks_completed=3,
            final_commit="abc123def",
            tests_passed=True,
            review_passed=False,
            registered_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            completed_at="2026-01-02T00:00:00Z",
        )
        d = w.to_dict()
        assert d == {
            "worker_id": None,
            "swarm_id": "s-1",
            "packet_id": 2,
            "packet_name": "packet-two",
            "worktree": "/wt",
            "status": "complete",
            "tasks_total": 3,
            "tasks_completed": 3,
            "final_commit": "abc123def",
            "tests_passed": True,
            "review_passed": False,
            "registered_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "completed_at": "2026-01-02T00:00:00Z",
        }

    def test_worker_roundtrip(self, engine):
        """SwarmWorker can be persisted and loaded, worker_id is auto-assigned."""
        from spellbook.db.coordination_models import Swarm, SwarmWorker

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-wrt",
                feature="worker-rt",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            worker = SwarmWorker(
                swarm_id="s-wrt",
                packet_id=1,
                packet_name="p1",
                worktree="/wt",
                status="registered",
                tasks_total=5,
                tasks_completed=0,
                registered_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            session.add_all([swarm, worker])
            session.commit()

            loaded = session.get(SwarmWorker, worker.worker_id)
            d = loaded.to_dict()
            assert d == {
                "worker_id": worker.worker_id,
                "swarm_id": "s-wrt",
                "packet_id": 1,
                "packet_name": "p1",
                "worktree": "/wt",
                "status": "registered",
                "tasks_total": 5,
                "tasks_completed": 0,
                "final_commit": None,
                "tests_passed": None,
                "review_passed": None,
                "registered_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "completed_at": None,
            }

    def test_worker_unique_constraint(self, engine):
        """Workers have UNIQUE(swarm_id, packet_id)."""
        from sqlalchemy.exc import IntegrityError

        from spellbook.db.coordination_models import Swarm, SwarmWorker

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-uc",
                feature="unique",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            w1 = SwarmWorker(
                swarm_id="s-uc",
                packet_id=1,
                packet_name="p1",
                status="registered",
                tasks_total=1,
                registered_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            w2 = SwarmWorker(
                swarm_id="s-uc",
                packet_id=1,
                packet_name="p1-dup",
                status="registered",
                tasks_total=1,
                registered_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            session.add_all([swarm, w1, w2])
            with pytest.raises(IntegrityError):
                session.commit()

    # ── Event model columns ──────────────────────────────────────────

    def test_event_columns(self, engine):
        """SwarmEvent model has exactly the columns from the CREATE TABLE."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("events")}
        expected = {
            "event_id",
            "swarm_id",
            "event_type",
            "packet_id",
            "task_id",
            "task_name",
            "commit",
            "error_type",
            "error_message",
            "recoverable",
            "event_data",
            "created_at",
        }
        assert columns == expected

    def test_event_primary_key(self, engine):
        """SwarmEvent primary key is event_id (autoincrement)."""
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint("events")
        assert pk["constrained_columns"] == ["event_id"]

    def test_event_commit_column(self, engine):
        """SwarmEvent has a 'commit' column (SQL keyword, bracket-escaped)."""
        from spellbook.db.coordination_models import SwarmEvent

        e = SwarmEvent(
            swarm_id="s-1",
            event_type="worker_complete",
            commit="abc123",
            created_at="2026-01-01T00:00:00Z",
        )
        d = e.to_dict()
        assert d["commit"] == "abc123"

    def test_event_to_dict_minimal(self, engine):
        """SwarmEvent.to_dict() with only required fields."""
        from spellbook.db.coordination_models import SwarmEvent

        e = SwarmEvent(
            swarm_id="s-1",
            event_type="heartbeat",
            created_at="2026-01-01T00:00:00Z",
        )
        d = e.to_dict()
        assert d == {
            "event_id": None,
            "swarm_id": "s-1",
            "event_type": "heartbeat",
            "packet_id": None,
            "task_id": None,
            "task_name": None,
            "commit": None,
            "error_type": None,
            "error_message": None,
            "recoverable": None,
            "event_data": None,
            "created_at": "2026-01-01T00:00:00Z",
        }

    def test_event_to_dict_with_json_event_data(self, engine):
        """SwarmEvent.to_dict() parses event_data JSON string."""
        from spellbook.db.coordination_models import SwarmEvent

        data = {"task_id": "t1", "status": "completed"}
        e = SwarmEvent(
            swarm_id="s-1",
            event_type="progress",
            packet_id=1,
            task_id="t1",
            task_name="do-thing",
            event_data=json.dumps(data),
            created_at="2026-01-01T00:00:00Z",
        )
        d = e.to_dict()
        assert d == {
            "event_id": None,
            "swarm_id": "s-1",
            "event_type": "progress",
            "packet_id": 1,
            "task_id": "t1",
            "task_name": "do-thing",
            "commit": None,
            "error_type": None,
            "error_message": None,
            "recoverable": None,
            "event_data": {"task_id": "t1", "status": "completed"},
            "created_at": "2026-01-01T00:00:00Z",
        }

    def test_event_to_dict_with_invalid_json_event_data(self, engine):
        """SwarmEvent.to_dict() returns raw string if event_data is not valid JSON."""
        from spellbook.db.coordination_models import SwarmEvent

        e = SwarmEvent(
            swarm_id="s-1",
            event_type="worker_registered",
            packet_id=1,
            event_data="not-json",
            created_at="2026-01-01T00:00:00Z",
        )
        d = e.to_dict()
        assert d["event_data"] == "not-json"

    def test_event_to_dict_error_fields(self, engine):
        """SwarmEvent.to_dict() includes error fields."""
        from spellbook.db.coordination_models import SwarmEvent

        e = SwarmEvent(
            swarm_id="s-1",
            event_type="worker_error",
            packet_id=1,
            task_id="t1",
            error_type="TestFailure",
            error_message="assert False",
            recoverable=True,
            created_at="2026-01-01T00:00:00Z",
        )
        d = e.to_dict()
        assert d == {
            "event_id": None,
            "swarm_id": "s-1",
            "event_type": "worker_error",
            "packet_id": 1,
            "task_id": "t1",
            "task_name": None,
            "commit": None,
            "error_type": "TestFailure",
            "error_message": "assert False",
            "recoverable": True,
            "event_data": None,
            "created_at": "2026-01-01T00:00:00Z",
        }

    def test_event_roundtrip(self, engine):
        """SwarmEvent persists and loads with correct values."""
        from spellbook.db.coordination_models import Swarm, SwarmEvent

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-ert",
                feature="event-rt",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            event = SwarmEvent(
                swarm_id="s-ert",
                event_type="progress",
                packet_id=1,
                task_id="t1",
                task_name="build",
                commit="deadbeef",
                event_data=json.dumps({"tasks_completed": 2}),
                created_at="2026-01-01T12:00:00Z",
            )
            session.add_all([swarm, event])
            session.commit()

            loaded = session.get(SwarmEvent, event.event_id)
            d = loaded.to_dict()
            assert d == {
                "event_id": event.event_id,
                "swarm_id": "s-ert",
                "event_type": "progress",
                "packet_id": 1,
                "task_id": "t1",
                "task_name": "build",
                "commit": "deadbeef",
                "error_type": None,
                "error_message": None,
                "recoverable": None,
                "event_data": {"tasks_completed": 2},
                "created_at": "2026-01-01T12:00:00Z",
            }

    # ── Relationships ────────────────────────────────────────────────

    def test_swarm_workers_relationship(self, engine):
        """Swarm.workers returns related SwarmWorker objects."""
        from spellbook.db.coordination_models import Swarm, SwarmWorker

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-rel",
                feature="rel-test",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            w1 = SwarmWorker(
                swarm_id="s-rel",
                packet_id=1,
                packet_name="p1",
                status="registered",
                tasks_total=3,
                registered_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            w2 = SwarmWorker(
                swarm_id="s-rel",
                packet_id=2,
                packet_name="p2",
                status="registered",
                tasks_total=5,
                registered_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            session.add_all([swarm, w1, w2])
            session.commit()

            loaded = session.get(Swarm, "s-rel")
            assert len(loaded.workers) == 2
            packet_names = {w.packet_name for w in loaded.workers}
            assert packet_names == {"p1", "p2"}

    def test_swarm_events_relationship(self, engine):
        """Swarm.events returns related SwarmEvent objects."""
        from spellbook.db.coordination_models import Swarm, SwarmEvent

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-erel",
                feature="event-rel",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            e1 = SwarmEvent(
                swarm_id="s-erel",
                event_type="worker_registered",
                packet_id=1,
                created_at="2026-01-01T00:00:00Z",
            )
            e2 = SwarmEvent(
                swarm_id="s-erel",
                event_type="heartbeat",
                created_at="2026-01-01T01:00:00Z",
            )
            session.add_all([swarm, e1, e2])
            session.commit()

            loaded = session.get(Swarm, "s-erel")
            assert len(loaded.events) == 2
            event_types = {e.event_type for e in loaded.events}
            assert event_types == {"worker_registered", "heartbeat"}

    def test_cascade_delete_workers(self, engine):
        """Deleting a Swarm cascades to its workers via ORM relationship."""
        from spellbook.db.coordination_models import Swarm, SwarmWorker

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-cas",
                feature="cascade",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            worker = SwarmWorker(
                packet_id=1,
                packet_name="p1",
                status="registered",
                tasks_total=1,
                registered_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            swarm.workers.append(worker)
            session.add(swarm)
            session.commit()
            worker_id = worker.worker_id

            # Reload to ensure relationship is loaded
            loaded_swarm = session.get(Swarm, "s-cas")
            # Access workers to load them into the session
            _ = loaded_swarm.workers
            session.delete(loaded_swarm)
            session.commit()
            session.expire_all()

            assert session.get(SwarmWorker, worker_id) is None

    def test_cascade_delete_events(self, engine):
        """Deleting a Swarm cascades to its events via ORM relationship."""
        from spellbook.db.coordination_models import Swarm, SwarmEvent

        with Session(engine) as session:
            swarm = Swarm(
                swarm_id="s-cas2",
                feature="cascade2",
                manifest_path="/m",
                status="running",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            event = SwarmEvent(
                event_type="heartbeat",
                created_at="2026-01-01T00:00:00Z",
            )
            swarm.events.append(event)
            session.add(swarm)
            session.commit()
            event_id = event.event_id

            loaded_swarm = session.get(Swarm, "s-cas2")
            _ = loaded_swarm.events
            session.delete(loaded_swarm)
            session.commit()
            session.expire_all()

            assert session.get(SwarmEvent, event_id) is None

    # ── Indexes ──────────────────────────────────────────────────────

    def test_swarm_indexes(self, engine):
        """Swarms table has indexes on status and created_at."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("swarms")
        index_columns = {
            idx["name"]: idx["column_names"] for idx in indexes
        }
        # Find indexes that cover status and created_at
        has_status_idx = any("status" in cols for cols in index_columns.values())
        has_created_at_idx = any("created_at" in cols for cols in index_columns.values())
        assert has_status_idx, f"No index on status. Indexes: {index_columns}"
        assert has_created_at_idx, f"No index on created_at. Indexes: {index_columns}"

    def test_worker_indexes(self, engine):
        """Workers table has composite indexes."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("workers")
        index_columns = {
            idx["name"]: idx["column_names"] for idx in indexes
        }
        # Composite index on (swarm_id, status)
        has_swarm_status = any(
            "swarm_id" in cols and "status" in cols
            for cols in index_columns.values()
        )
        # Composite index on (swarm_id, packet_id)
        has_swarm_packet = any(
            "swarm_id" in cols and "packet_id" in cols
            for cols in index_columns.values()
        )
        assert has_swarm_status, f"No composite index on (swarm_id, status). Indexes: {index_columns}"
        assert has_swarm_packet, f"No composite index on (swarm_id, packet_id). Indexes: {index_columns}"

    def test_event_indexes(self, engine):
        """Events table has indexes on swarm_id and created_at."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("events")
        index_columns = {
            idx["name"]: idx["column_names"] for idx in indexes
        }
        has_swarm_idx = any("swarm_id" in cols for cols in index_columns.values())
        has_created_at_idx = any("created_at" in cols for cols in index_columns.values())
        assert has_swarm_idx, f"No index on swarm_id. Indexes: {index_columns}"
        assert has_created_at_idx, f"No index on created_at. Indexes: {index_columns}"
