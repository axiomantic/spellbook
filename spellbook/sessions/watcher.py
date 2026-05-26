"""Background watcher for session heartbeat and skill-invocation analysis."""

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Set


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
        self, db_path: str, poll_interval: float = 2.0, project_path: str = None,
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
        """Poll session files and analyze skills for incremental persistence.

        Runs the skill-invocation analysis every poll cycle.
        """
        # Analyze skills for incremental persistence (runs every poll cycle)
        try:
            self._analyze_skills()
        except Exception as e:
            logger.warning(f"Skill analysis failed: {e}")

    def _cleanup_stale_data(self):
        """Prune old rows from high-volume database tables."""
        from datetime import timedelta
        from sqlalchemy import delete
        from spellbook.db.engines import get_sync_session
        from spellbook.db.spellbook_models import (
            Correction,
            Decision,
            SkillOutcome as SkillOutcomeModel,
            Subagent,
        )

        now = datetime.now()
        cutoff_90d = (now - timedelta(days=90)).isoformat()

        try:
            with get_sync_session(self.db_path) as session:
                # Each delete is wrapped in try/except to handle missing tables
                cleanup_ops = [
                    (SkillOutcomeModel, SkillOutcomeModel.created_at, cutoff_90d),
                    (Subagent, Subagent.spawned_at, cutoff_90d),
                    (Decision, Decision.decided_at, cutoff_90d),
                    (Correction, Correction.recorded_at, cutoff_90d),
                ]
                for model, column, cutoff in cleanup_ops:
                    try:
                        session.execute(
                            delete(model).where(column < cutoff)
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        # Clean up old forged workflow data (async ORM)
        try:
            from sqlalchemy import delete
            from spellbook.db import get_forged_session
            from spellbook.db.forged_models import ForgeToken, ToolAnalytic, ForgeReflection

            cutoff_90d_forged = (now - timedelta(days=90)).isoformat()

            async def _cleanup_forged():
                async with get_forged_session() as session:
                    try:
                        await session.execute(
                            delete(ForgeToken).where(
                                ForgeToken.invalidated_at.isnot(None),
                                ForgeToken.invalidated_at < cutoff_90d_forged,
                            )
                        )
                    except Exception:
                        pass

                    try:
                        await session.execute(
                            delete(ToolAnalytic).where(
                                ToolAnalytic.called_at < cutoff_90d_forged,
                            )
                        )
                    except Exception:
                        pass

                    try:
                        await session.execute(
                            delete(ForgeReflection).where(
                                ForgeReflection.created_at < cutoff_90d_forged,
                                ForgeReflection.status == "RESOLVED",
                            )
                        )
                    except Exception:
                        pass

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_cleanup_forged())
            except RuntimeError:
                asyncio.run(_cleanup_forged())
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
        from spellbook.sessions.compaction import _get_current_session_file
        from spellbook.sessions.skill_analyzer import (
            extract_skill_invocations,
            persist_outcome,
            finalize_session_outcomes,
            SkillOutcome,
        )
        from spellbook.sessions.parser import load_jsonl

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

    def _write_heartbeat(self):
        """Write heartbeat to database."""
        from spellbook.db.engines import get_sync_session
        from spellbook.db.spellbook_models import Heartbeat
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        with get_sync_session(self.db_path) as session:
            stmt = sqlite_insert(Heartbeat).values(
                id=1,
                timestamp=datetime.now().isoformat(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={"timestamp": stmt.excluded.timestamp},
            )
            session.execute(stmt)


def is_heartbeat_fresh(db_path: str, max_age: float = 30.0) -> bool:
    """Check if watcher heartbeat is fresh.

    Args:
        db_path: Path to database file
        max_age: Maximum age in seconds (default 30.0)

    Returns:
        True if heartbeat exists and is fresh
    """
    try:
        from sqlalchemy import select
        from spellbook.db.engines import get_sync_session
        from spellbook.db.spellbook_models import Heartbeat

        with get_sync_session(db_path) as session:
            stmt = select(Heartbeat).where(Heartbeat.id == 1)
            hb = session.execute(stmt).scalars().first()

        if not hb or not hb.timestamp:
            return False

        heartbeat = datetime.fromisoformat(hb.timestamp)
        age = (datetime.now() - heartbeat).total_seconds()

        return age < max_age
    except Exception:
        # Table doesn't exist or other error - database not initialized
        return False
