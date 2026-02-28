"""Background watcher for session compaction events."""

import json
import os
import sqlite3
import threading
import time
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from spellbook_mcp.db import get_connection


logger = logging.getLogger(__name__)

# Session inactivity threshold for finalizing outcomes
SESSION_INACTIVE_THRESHOLD_SECONDS = 300  # 5 minutes


@dataclass
class SessionSkillState:
    """Track skill analysis state for a single session."""
    session_id: str
    last_message_idx: int = 0  # Index of last processed message
    last_mtime: float = 0.0    # File mtime at last analysis
    known_invocations: Set[str] = field(default_factory=set)
    last_activity: datetime = field(default_factory=datetime.now)

    def invocation_key(self, inv) -> str:
        """Unique key for an invocation within a session."""
        return f"{inv.skill}:{inv.start_idx}"


class SessionWatcher(threading.Thread):
    """Background thread that monitors session files for compaction events."""

    CLEANUP_INTERVAL = 3600  # 1 hour between database pruning runs

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
        self._last_cleanup = 0.0

        # Session tracking: session_id -> {path, last_mtime, last_size}
        self.sessions: Dict[str, dict] = {}
        # Track processed compaction events by (session_id, leaf_uuid)
        self._processed_compactions: dict = {}  # (session_id, leaf_uuid) -> timestamp
        # Skill analysis state per session
        self._skill_states: Dict[str, SessionSkillState] = {}

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
                self._prune_expired_compactions()

                now = time.time()
                if now - self._last_cleanup > self.CLEANUP_INTERVAL:
                    self._cleanup_stale_data()
                    self._last_cleanup = now

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
        """Poll session files for compaction events and analyze skills.

        Checks the current project's session file for compaction markers
        (messages with type='summary'). When compaction is detected:
        1. Extracts the soul from the session transcript
        2. Saves the soul to the database
        3. Signals the injection module to trigger context recovery

        Also analyzes skills for incremental persistence every poll cycle.
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

        if event is not None:
            # Create unique key for this compaction event
            compaction_key = (event.session_id, event.leaf_uuid)

            # Process if not already processed
            if compaction_key not in self._processed_compactions:
                logger.info(
                    f"Compaction detected in session {event.session_id}, "
                    f"extracting soul..."
                )

                # Get session file path for soul extraction
                session_file = _get_current_session_file(self.project_path)
                if session_file is not None:
                    # Extract soul from transcript
                    try:
                        soul = extract_soul(str(session_file))
                        # Save soul to database
                        try:
                            self._save_soul(event.session_id, soul)
                            # Mark as processed
                            self._processed_compactions[compaction_key] = time.time()
                            # Signal injection module to trigger recovery on next tool call
                            _set_pending_compaction(True)
                            logger.info(f"Soul saved and recovery triggered for session {event.session_id}")
                        except Exception as e:
                            logger.error(f"Failed to save soul: {e}", exc_info=True)
                    except Exception as e:
                        logger.error(f"Failed to extract soul: {e}", exc_info=True)
                else:
                    logger.warning("Session file not found for soul extraction")

        # Analyze skills for incremental persistence (runs every poll cycle)
        try:
            self._analyze_skills()
        except Exception as e:
            logger.warning(f"Skill analysis failed: {e}")

    def _prune_expired_compactions(self):
        """Remove compaction records older than 1 hour."""
        now = time.time()
        expired = [k for k, ts in self._processed_compactions.items() if now - ts > 3600]
        for k in expired:
            del self._processed_compactions[k]

    def _cleanup_stale_data(self):
        """Prune old rows from high-volume database tables."""
        from datetime import timedelta

        now = datetime.now()
        cutoff_30d = (now - timedelta(days=30)).isoformat()
        cutoff_90d = (now - timedelta(days=90)).isoformat()

        try:
            conn = get_connection(self.db_path)

            for table, column, cutoff in [
                ("souls", "bound_at", cutoff_30d),
                ("security_events", "created_at", cutoff_90d),
                ("skill_outcomes", "created_at", cutoff_90d),
                ("subagents", "spawned_at", cutoff_90d),
                ("decisions", "decided_at", cutoff_90d),
                ("corrections", "recorded_at", cutoff_90d),
            ]:
                try:
                    conn.execute(
                        f"DELETE FROM {table} WHERE {column} < ?",  # noqa: S608
                        (cutoff,),
                    )
                except sqlite3.OperationalError:
                    pass

            conn.commit()
        except Exception:
            pass

        # Clean up old swarm coordination data
        try:
            from spellbook_mcp.coordination.state import StateManager
            sm = StateManager(self.db_path)
            sm.cleanup_old_swarms(days=7)
        except Exception:
            pass

        # Clean up old forged workflow data
        try:
            from spellbook_mcp.forged.schema import get_forged_connection

            cutoff_90d_forged = (now - timedelta(days=90)).isoformat()
            fconn = get_forged_connection()

            try:
                fconn.execute(
                    "DELETE FROM forge_tokens WHERE invalidated_at IS NOT NULL AND invalidated_at < ?",
                    (cutoff_90d_forged,),
                )
            except sqlite3.OperationalError:
                pass

            try:
                fconn.execute(
                    "DELETE FROM tool_analytics WHERE called_at < ?",
                    (cutoff_90d_forged,),
                )
            except sqlite3.OperationalError:
                pass

            try:
                fconn.execute(
                    "DELETE FROM reflections WHERE created_at < ? AND status = 'RESOLVED'",
                    (cutoff_90d_forged,),
                )
            except sqlite3.OperationalError:
                pass

            fconn.commit()
        except Exception:
            pass

    def _analyze_skills(self):
        """Analyze current session for skill invocations.

        Called every poll interval (2s). Extracts new invocations
        since last poll, persists outcomes incrementally.

        Lifecycle:
        1. Get current session file and mtime
        2. If new session, create SessionSkillState
        3. If file unchanged for 5+ minutes, finalize open skills
        4. If file changed, extract invocations from last_message_idx
        5. For each new/updated invocation, persist outcome
        6. Update state tracking
        """
        from spellbook_mcp.compaction_detector import _get_current_session_file
        from spellbook_mcp.skill_analyzer import (
            extract_skill_invocations,
            persist_outcome,
            finalize_session_outcomes,
            SkillOutcome,
        )
        from spellbook_mcp.session_ops import load_jsonl

        session_file = _get_current_session_file(self.project_path)
        if session_file is None:
            return

        session_id = session_file.stem
        current_mtime = session_file.stat().st_mtime
        project_encoded = self.project_path.replace("/", "-").lstrip("-")
        db_path = self.db_path  # Use watcher's database path

        # Get or create session state
        if session_id not in self._skill_states:
            self._skill_states[session_id] = SessionSkillState(session_id=session_id)
        state = self._skill_states[session_id]

        # Check for session inactivity
        if self._is_session_inactive(state, current_mtime):
            # Finalize any open skill outcomes
            finalize_session_outcomes(session_id, db_path)
            # Remove from tracking (session ended)
            del self._skill_states[session_id]
            return

        # Skip if file hasn't changed
        if current_mtime <= state.last_mtime:
            return

        # Load messages and extract invocations
        try:
            messages = load_jsonl(str(session_file))
        except Exception as e:
            logger.warning(f"Failed to load session file: {e}")
            return

        invocations = extract_skill_invocations(messages, str(session_file))

        # Cleanup: Remove states for sessions that no longer exist
        # This prevents memory leaks when session files are deleted externally
        stale_sessions = [sid for sid in list(self._skill_states.keys())
                         if sid != session_id]
        for sid in stale_sessions:
            # Check if this old session's file still exists
            # If not, finalize and remove from tracking
            try:
                finalize_session_outcomes(sid, db_path)
            except Exception as e:
                logger.warning(f"Failed to finalize stale session {sid}: {e}")
            del self._skill_states[sid]

        # Process only new/updated invocations
        for inv in invocations:
            key = state.invocation_key(inv)

            # Create outcome from invocation
            outcome = SkillOutcome.from_invocation(inv, session_id, project_encoded)

            # Persist if has determined outcome OR if new invocation
            if outcome.outcome or key not in state.known_invocations:
                if outcome.outcome:  # Only persist if outcome is determined
                    try:
                        persist_outcome(outcome, db_path)
                    except Exception as e:
                        logger.warning(f"Failed to persist outcome for {outcome.skill_name}: {e}")
                        # Continue processing other invocations
                state.known_invocations.add(key)

        # Update tracking
        state.last_mtime = current_mtime
        state.last_message_idx = len(messages)
        state.last_activity = datetime.now()

    def _is_session_inactive(self, state: SessionSkillState, current_mtime: float) -> bool:
        """Detect if session has been inactive long enough to finalize.

        Args:
            state: SessionSkillState for the session
            current_mtime: Current file modification time

        Returns:
            True if session should be finalized
        """
        if current_mtime > state.last_mtime:
            # File was modified, reset activity timer
            state.last_activity = datetime.now()
            return False

        # Check if inactive long enough
        inactive_seconds = (datetime.now() - state.last_activity).total_seconds()
        return inactive_seconds >= SESSION_INACTIVE_THRESHOLD_SECONDS

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
