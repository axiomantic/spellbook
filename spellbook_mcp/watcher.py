"""Background watcher for session compaction events."""

import threading
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .db import get_connection


logger = logging.getLogger(__name__)


class SessionWatcher(threading.Thread):
    """Background thread that monitors session files for compaction events."""

    def __init__(self, db_path: str, poll_interval: float = 2.0):
        """Initialize watcher.

        Args:
            db_path: Path to SQLite database
            poll_interval: Seconds between polls (default 2.0)
        """
        super().__init__(daemon=True)
        self.db_path = db_path
        self.poll_interval = poll_interval
        self._running = False
        self._shutdown = threading.Event()

        # Session tracking: session_id -> {path, last_mtime, last_size}
        self.sessions: Dict[str, dict] = {}

    def is_running(self) -> bool:
        """Check if watcher is currently running.

        Returns:
            True if watcher thread is active
        """
        return self._running

    def start(self) -> threading.Thread:
        """Start the watcher thread.

        Returns:
            The thread object (self)
        """
        self._running = True
        super().start()
        return self

    def stop(self):
        """Stop the watcher thread gracefully."""
        self._running = False
        self._shutdown.set()

    def run(self):
        """Main watcher loop with error recovery."""
        while not self._shutdown.is_set():
            try:
                self._poll_sessions()
                self._write_heartbeat()
            except Exception as e:
                logger.error(f"Watcher error: {e}", exc_info=True)
                time.sleep(5.0)  # Backoff before retry

            # Use event.wait() instead of time.sleep() for responsive shutdown
            self._shutdown.wait(self.poll_interval)

    def _poll_sessions(self):
        """Poll all registered sessions for changes.

        Currently a no-op - will be implemented with soul extraction.
        """
        # TODO: Implement in Phase 2
        pass

    def _write_heartbeat(self):
        """Write heartbeat to database."""
        conn = get_connection(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (datetime.now().isoformat(),)
        )
        conn.commit()


def is_heartbeat_fresh(db_path: str, max_age: float = 30.0) -> bool:
    """Check if watcher heartbeat is fresh.

    Args:
        db_path: Path to database file
        max_age: Maximum age in seconds (default 30.0)

    Returns:
        True if heartbeat exists and is fresh
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp FROM heartbeat WHERE id = 1")
    row = cursor.fetchone()

    if not row:
        return False

    heartbeat = datetime.fromisoformat(row[0])
    age = (datetime.now() - heartbeat).total_seconds()

    return age < max_age
