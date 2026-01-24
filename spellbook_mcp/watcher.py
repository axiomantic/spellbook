"""Background watcher for session compaction events."""

import json
import os
import sqlite3
import threading
import time
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from spellbook_mcp.db import get_connection


logger = logging.getLogger(__name__)


class SessionWatcher(threading.Thread):
    """Background thread that monitors session files for compaction events."""

    def __init__(
        self, db_path: str, poll_interval: float = 2.0, project_path: str = None
    ):
        """Initialize watcher.

        Args:
            db_path: Path to SQLite database
            poll_interval: Seconds between polls (default 2.0)
            project_path: Project directory to monitor (defaults to cwd)
        """
        super().__init__(daemon=True)
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.project_path = project_path or os.getcwd()
        self._running = False
        self._shutdown = threading.Event()

        # Session tracking: session_id -> {path, last_mtime, last_size}
        self.sessions: Dict[str, dict] = {}
        # Track processed compaction events by (session_id, leaf_uuid)
        self._processed_compactions: set = set()

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
        """Main watcher loop with error recovery and circuit breaker."""
        consecutive_errors = 0
        max_consecutive_errors = 5  # Give up after 5 consecutive failures

        while not self._shutdown.is_set():
            try:
                self._poll_sessions()
                self._write_heartbeat()
                consecutive_errors = 0  # Reset on success
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(
                        f"Watcher giving up after {max_consecutive_errors} consecutive errors. "
                        f"Last error: {e}"
                    )
                    self._running = False
                    return  # Exit the watcher thread
                logger.warning(
                    f"Watcher error ({consecutive_errors}/{max_consecutive_errors}): {e}"
                )
                time.sleep(5.0)  # Backoff before retry

            # Use event.wait() instead of time.sleep() for responsive shutdown
            self._shutdown.wait(self.poll_interval)

    def _poll_sessions(self):
        """Poll session files for compaction events.

        Checks the current project's session file for compaction markers
        (messages with type='summary'). When compaction is detected:
        1. Extracts the soul from the session transcript
        2. Saves the soul to the database
        3. Signals the injection module to trigger context recovery
        """
        # Lazy imports to avoid circular dependency at module load time
        from spellbook_mcp.compaction_detector import (
            _get_current_session_file,
            check_for_compaction,
        )
        from spellbook_mcp.soul_extractor import extract_soul
        from spellbook_mcp.injection import _set_pending_compaction

        # Check for compaction event
        event = check_for_compaction(self.project_path)

        if event is None:
            return

        # Create unique key for this compaction event
        compaction_key = (event.session_id, event.leaf_uuid)

        # Skip if already processed
        if compaction_key in self._processed_compactions:
            return

        logger.info(
            f"Compaction detected in session {event.session_id}, "
            f"extracting soul..."
        )

        # Get session file path for soul extraction
        session_file = _get_current_session_file(self.project_path)
        if session_file is None:
            logger.warning("Session file not found for soul extraction")
            return

        # Extract soul from transcript
        try:
            soul = extract_soul(str(session_file))
        except Exception as e:
            logger.error(f"Failed to extract soul: {e}", exc_info=True)
            return

        # Save soul to database
        try:
            self._save_soul(event.session_id, soul)
        except Exception as e:
            logger.error(f"Failed to save soul: {e}", exc_info=True)
            return

        # Mark as processed
        self._processed_compactions.add(compaction_key)

        # Signal injection module to trigger recovery on next tool call
        _set_pending_compaction(True)

        logger.info(f"Soul saved and recovery triggered for session {event.session_id}")

    def _save_soul(self, session_id: str, soul: dict) -> None:
        """Save extracted soul to database.

        Args:
            session_id: Session identifier
            soul: Extracted soul dict with keys: todos, active_skill, persona, etc.
        """
        conn = get_connection(self.db_path)

        # Generate unique soul ID
        soul_id = str(uuid.uuid4())

        conn.execute(
            """
            INSERT INTO souls (
                id, project_path, session_id, bound_at,
                persona, active_skill, skill_phase,
                todos, recent_files, exact_position, workflow_pattern
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                soul_id,
                self.project_path,
                session_id,
                datetime.now().isoformat(),
                soul.get("persona"),
                soul.get("active_skill"),
                soul.get("skill_phase"),
                json.dumps(soul.get("todos", [])),
                json.dumps(soul.get("recent_files", [])),
                json.dumps(soul.get("exact_position", [])),
                soul.get("workflow_pattern"),
            ),
        )
        conn.commit()

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
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp FROM heartbeat WHERE id = 1")
        row = cursor.fetchone()

        if not row:
            return False

        heartbeat = datetime.fromisoformat(row[0])
        age = (datetime.now() - heartbeat).total_seconds()

        return age < max_age
    except sqlite3.OperationalError:
        # Table doesn't exist - database not initialized
        return False
