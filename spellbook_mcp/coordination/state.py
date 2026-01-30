"""SQLite state management for coordination server."""
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid
import json


class StateManager:
    """Manages swarm coordination state in SQLite."""

    def __init__(self, database_path: str):
        """
        Initialize state manager.

        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = Path(database_path).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")

            # Create tables
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS swarms (
                    swarm_id TEXT PRIMARY KEY,
                    feature TEXT NOT NULL,
                    manifest_path TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('created', 'running', 'complete', 'failed')),
                    auto_merge BOOLEAN DEFAULT FALSE,
                    notify_on_complete BOOLEAN DEFAULT TRUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS workers (
                    worker_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    swarm_id TEXT NOT NULL,
                    packet_id INTEGER NOT NULL,
                    packet_name TEXT NOT NULL,
                    worktree TEXT,
                    status TEXT NOT NULL CHECK(status IN ('registered', 'running', 'complete', 'failed')),
                    tasks_total INTEGER NOT NULL,
                    tasks_completed INTEGER DEFAULT 0,
                    final_commit TEXT,
                    tests_passed BOOLEAN,
                    review_passed BOOLEAN,
                    registered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (swarm_id) REFERENCES swarms(swarm_id) ON DELETE CASCADE,
                    UNIQUE(swarm_id, packet_id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    swarm_id TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type IN (
                        'worker_registered', 'progress', 'worker_complete',
                        'worker_error', 'all_complete', 'heartbeat'
                    )),
                    packet_id INTEGER,
                    task_id TEXT,
                    task_name TEXT,
                    [commit] TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    recoverable BOOLEAN,
                    event_data TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (swarm_id) REFERENCES swarms(swarm_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_swarms_status ON swarms(status);
                CREATE INDEX IF NOT EXISTS idx_swarms_created_at ON swarms(created_at);
                CREATE INDEX IF NOT EXISTS idx_workers_swarm_status ON workers(swarm_id, status);
                CREATE INDEX IF NOT EXISTS idx_workers_packet ON workers(swarm_id, packet_id);
                CREATE INDEX IF NOT EXISTS idx_events_swarm ON events(swarm_id);
                CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.database_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def create_swarm(
        self,
        feature: str,
        manifest_path: str,
        auto_merge: bool = False,
        notify_on_complete: bool = True
    ) -> str:
        """
        Create a new swarm.

        Returns:
            swarm_id
        """
        swarm_id = f"swarm-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO swarms (
                    swarm_id, feature, manifest_path, status,
                    auto_merge, notify_on_complete, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (swarm_id, feature, manifest_path, "created",
                  auto_merge, notify_on_complete, now, now))
            conn.commit()
            return swarm_id
        finally:
            conn.close()

    def get_swarm(self, swarm_id: str) -> Dict[str, Any]:
        """Get swarm by ID."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM swarms WHERE swarm_id = ?",
                (swarm_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Swarm not found: {swarm_id}")
            return dict(row)
        finally:
            conn.close()

    def register_worker(
        self,
        swarm_id: str,
        packet_id: int,
        packet_name: str,
        tasks_total: int,
        worktree: str
    ) -> int:
        """
        Register a worker with the swarm.

        Returns:
            worker_id
        """
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO workers (
                    swarm_id, packet_id, packet_name,
                    worktree, status, tasks_total, tasks_completed,
                    registered_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (swarm_id, packet_id, packet_name,
                  worktree, "registered", tasks_total, 0, now, now))

            worker_id = cursor.lastrowid

            # Update swarm status to running
            conn.execute("""
                UPDATE swarms SET status = 'running', updated_at = ?
                WHERE swarm_id = ?
            """, (now, swarm_id))

            # Log event
            conn.execute("""
                INSERT INTO events (swarm_id, event_type, packet_id, event_data, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (swarm_id, "worker_registered", packet_id, packet_name, now))

            conn.commit()
            return worker_id
        finally:
            conn.close()

    def update_progress(
        self,
        swarm_id: str,
        packet_id: int,
        task_id: str,
        task_name: str,
        status: str,
        tasks_completed: int,
        tasks_total: int,
        commit: Optional[str] = None
    ):
        """Update worker progress."""
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        conn = self._get_connection()
        try:
            # Update worker
            conn.execute("""
                UPDATE workers
                SET status = 'running',
                    tasks_completed = ?,
                    updated_at = ?
                WHERE swarm_id = ? AND packet_id = ?
            """, (tasks_completed, now, swarm_id, packet_id))

            # Log event
            event_data = json.dumps({
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "tasks_completed": tasks_completed,
                "tasks_total": tasks_total
            })

            conn.execute("""
                INSERT INTO events (
                    swarm_id, event_type, packet_id, task_id,
                    task_name, [commit], event_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (swarm_id, "progress", packet_id, task_id,
                  task_name, commit, event_data, now))

            conn.commit()
        finally:
            conn.close()

    def mark_complete(
        self,
        swarm_id: str,
        packet_id: int,
        final_commit: str,
        tests_passed: bool,
        review_passed: bool
    ):
        """Mark worker as complete."""
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        conn = self._get_connection()
        try:
            # Update worker
            conn.execute("""
                UPDATE workers
                SET status = 'complete',
                    final_commit = ?,
                    tests_passed = ?,
                    review_passed = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE swarm_id = ? AND packet_id = ?
            """, (final_commit, tests_passed, review_passed, now, now,
                  swarm_id, packet_id))

            # Log event
            event_data = json.dumps({
                "final_commit": final_commit,
                "tests_passed": tests_passed,
                "review_passed": review_passed
            })

            conn.execute("""
                INSERT INTO events (
                    swarm_id, event_type, packet_id, [commit],
                    event_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (swarm_id, "worker_complete", packet_id, final_commit,
                  event_data, now))

            # Check if all workers are complete
            cursor = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed
                FROM workers
                WHERE swarm_id = ?
            """, (swarm_id,))
            row = cursor.fetchone()

            if row["total"] > 0 and row["total"] == row["completed"]:
                # All workers complete - update swarm status
                conn.execute("""
                    UPDATE swarms
                    SET status = 'complete', completed_at = ?, updated_at = ?
                    WHERE swarm_id = ?
                """, (now, now, swarm_id))

                # Log all_complete event
                conn.execute("""
                    INSERT INTO events (swarm_id, event_type, created_at)
                    VALUES (?, ?, ?)
                """, (swarm_id, "all_complete", now))

            conn.commit()
        finally:
            conn.close()

    def record_error(
        self,
        swarm_id: str,
        packet_id: int,
        task_id: str,
        error_type: str,
        message: str,
        recoverable: bool
    ):
        """Record an error from a worker."""
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        conn = self._get_connection()
        try:
            # Update worker status if non-recoverable
            if not recoverable:
                conn.execute("""
                    UPDATE workers
                    SET status = 'failed', updated_at = ?
                    WHERE swarm_id = ? AND packet_id = ?
                """, (now, swarm_id, packet_id))

            # Log event
            conn.execute("""
                INSERT INTO events (
                    swarm_id, event_type, packet_id, task_id,
                    error_type, error_message, recoverable, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (swarm_id, "worker_error", packet_id, task_id,
                  error_type, message, recoverable, now))

            conn.commit()
        finally:
            conn.close()

    def get_events(
        self,
        swarm_id: str,
        since_event_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get events for a swarm since a specific event ID.

        Args:
            swarm_id: Swarm identifier
            since_event_id: Return events with ID > this value

        Returns:
            List of event dictionaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM events
                WHERE swarm_id = ? AND event_id > ?
                ORDER BY event_id ASC
            """, (swarm_id, since_event_id))

            events = []
            for row in cursor:
                event = dict(row)
                # Parse event_data JSON if present
                if event.get("event_data"):
                    try:
                        event["event_data"] = json.loads(event["event_data"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                events.append(event)

            return events
        finally:
            conn.close()

    def cleanup_old_swarms(self, days: int = 7):
        """
        Delete swarms older than specified days.

        Args:
            days: Delete swarms older than this many days
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

        conn = self._get_connection()
        try:
            conn.execute("""
                DELETE FROM swarms
                WHERE created_at < ?
            """, (cutoff,))
            conn.commit()
        finally:
            conn.close()
