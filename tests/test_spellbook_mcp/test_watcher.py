"""Tests for session watcher thread."""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.slow


def test_watcher_starts_and_stops(tmp_path):
    """Test watcher thread lifecycle."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path))
    thread = watcher.start()

    assert thread.is_alive()
    assert watcher.is_running()

    watcher.stop()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert not watcher.is_running()


def test_watcher_writes_heartbeat(tmp_path):
    """Test that watcher updates heartbeat periodically."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path), poll_interval=0.5)
    thread = watcher.start()

    # Wait for at least 2 heartbeats
    time.sleep(1.5)

    # Check heartbeat was written
    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp FROM heartbeat WHERE id = 1")
    row = cursor.fetchone()

    assert row is not None
    heartbeat = datetime.fromisoformat(row[0])
    age = (datetime.now() - heartbeat).total_seconds()

    # Use generous tolerance to avoid flaky failures under heavy system load
    assert age < 10.0  # Should be reasonably recent

    watcher.stop()
    thread.join(timeout=2.0)


def test_watcher_heartbeat_freshness_check(tmp_path):
    """Test heartbeat freshness validation."""
    from spellbook_mcp.watcher import is_heartbeat_fresh
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    # No heartbeat yet
    assert not is_heartbeat_fresh(str(db_path))

    # Insert fresh heartbeat
    conn = get_connection(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
        (datetime.now().isoformat(),)
    )
    conn.commit()

    assert is_heartbeat_fresh(str(db_path))

    # Insert stale heartbeat (40 seconds ago)
    stale_time = datetime.now().timestamp() - 40
    conn.execute(
        "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
        (datetime.fromtimestamp(stale_time).isoformat(),)
    )
    conn.commit()

    assert not is_heartbeat_fresh(str(db_path))


def test_poll_sessions_detects_compaction_and_saves_soul(tmp_path, monkeypatch):
    """Test that _poll_sessions detects compaction and saves soul to DB."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection
    from spellbook_mcp.compaction_detector import CompactionEvent
    from spellbook_mcp import injection

    db_path = tmp_path / "test.db"
    project_path = tmp_path / "project"
    project_path.mkdir()
    init_db(str(db_path))

    # Create a mock session file
    session_dir = tmp_path / ".claude" / "projects" / "-tmp-project"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "test-session.jsonl"
    session_file.write_text(
        json.dumps({"type": "user", "message": "hello"}) + "\n"
        + json.dumps({"type": "assistant", "message": "hi"}) + "\n"
    )

    # Create mock compaction event
    mock_event = CompactionEvent(
        session_id="test-session",
        summary="Test summary",
        leaf_uuid="leaf-123",
        detected_at=time.time(),
        project_path=str(project_path),
    )

    # Mock soul extraction result
    mock_soul = {
        "todos": [{"content": "Fix bug", "status": "in_progress"}],
        "active_skill": "debugging",
        "skill_phase": None,
        "persona": "Test Persona",
        "recent_files": ["/path/to/file.py"],
        "exact_position": [{"tool": "Read", "primary_arg": "/path/to/file.py"}],
        "workflow_pattern": "TDD",
    }

    # Track if _set_pending_compaction was called
    pending_calls = []
    original_set_pending = injection._set_pending_compaction

    def mock_set_pending(value):
        pending_calls.append(value)
        original_set_pending(value)

    # Create watcher with project path
    watcher = SessionWatcher(str(db_path), project_path=str(project_path))

    # Mock all the lazy imports within _poll_sessions
    with patch.object(
        watcher.__class__, '_poll_sessions', autospec=True
    ) as original_poll:
        # Restore original method but with patched imports
        original_poll.side_effect = None

    # Use patch.dict to patch the modules that get lazy imported
    with patch(
        "spellbook_mcp.compaction_detector.check_for_compaction", return_value=mock_event
    ) as mock_check:
        with patch(
            "spellbook_mcp.compaction_detector._get_current_session_file",
            return_value=session_file,
        ):
            with patch(
                "spellbook_mcp.soul_extractor.extract_soul", return_value=mock_soul
            ) as mock_extract:
                monkeypatch.setattr(injection, "_set_pending_compaction", mock_set_pending)

                # Call _poll_sessions
                watcher._poll_sessions()

                # Verify check_for_compaction was called with project path
                mock_check.assert_called_once_with(str(project_path))

                # Verify extract_soul was called with session file
                mock_extract.assert_called_once_with(str(session_file))

    # Verify soul was saved to database
    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT project_path, session_id, persona, active_skill, todos FROM souls"
    )
    row = cursor.fetchone()

    assert row is not None
    assert row[0] == str(project_path)  # project_path
    assert row[1] == "test-session"  # session_id
    assert row[2] == "Test Persona"  # persona
    assert row[3] == "debugging"  # active_skill
    todos = json.loads(row[4])
    assert len(todos) == 1
    assert todos[0]["content"] == "Fix bug"

    # Verify _set_pending_compaction was called with True
    assert True in pending_calls

    # Reset injection state for other tests
    injection._reset_state()


def test_poll_sessions_skips_already_processed_compaction(tmp_path):
    """Test that _poll_sessions skips already processed compaction events."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection
    from spellbook_mcp.compaction_detector import CompactionEvent

    db_path = tmp_path / "test.db"
    project_path = tmp_path / "project"
    project_path.mkdir()
    init_db(str(db_path))

    # Create mock compaction event
    mock_event = CompactionEvent(
        session_id="test-session",
        summary="Test summary",
        leaf_uuid="leaf-123",
        detected_at=time.time(),
        project_path=str(project_path),
    )

    watcher = SessionWatcher(str(db_path), project_path=str(project_path))

    # Pre-mark this compaction as processed
    watcher._processed_compactions[("test-session", "leaf-123")] = time.time()

    with patch(
        "spellbook_mcp.compaction_detector.check_for_compaction", return_value=mock_event
    ):
        with patch("spellbook_mcp.soul_extractor.extract_soul") as mock_extract:
            watcher._poll_sessions()

            # extract_soul should NOT be called since event was already processed
            mock_extract.assert_not_called()

    # Verify no soul was saved
    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM souls")
    count = cursor.fetchone()[0]
    assert count == 0


def test_poll_sessions_no_compaction_event(tmp_path):
    """Test that _poll_sessions does nothing when no compaction detected."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    project_path = tmp_path / "project"
    project_path.mkdir()
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path), project_path=str(project_path))

    with patch(
        "spellbook_mcp.compaction_detector.check_for_compaction", return_value=None
    ):
        with patch("spellbook_mcp.soul_extractor.extract_soul") as mock_extract:
            watcher._poll_sessions()

            # extract_soul should NOT be called
            mock_extract.assert_not_called()

    # Verify no soul was saved
    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM souls")
    count = cursor.fetchone()[0]
    assert count == 0


def test_analyze_skills_persists_outcomes(tmp_path, monkeypatch):
    """Test that _analyze_skills extracts and persists skill outcomes."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    project_path = tmp_path / "project"
    project_path.mkdir()
    init_db(str(db_path))

    # Create a session file with skill invocations
    session_dir = tmp_path / ".claude" / "projects" / "-tmp-project"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "test-session.jsonl"

    messages = [
        {"type": "user", "message": {"content": "Help me debug"}},
        {
            "type": "assistant",
            "timestamp": "2026-01-26T10:00:00",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "debugging"},
                    }
                ],
                "usage": {"output_tokens": 100},
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Done"}],
                "usage": {"output_tokens": 200},
            },
        },
    ]
    session_file.write_text("\n".join(json.dumps(m) for m in messages) + "\n")

    watcher = SessionWatcher(str(db_path), project_path=str(project_path))

    # Mock the session file lookup
    with patch(
        "spellbook_mcp.compaction_detector._get_current_session_file",
        return_value=session_file,
    ):
        watcher._analyze_skills()

    # Check outcomes were persisted
    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT skill_name, tokens_used FROM skill_outcomes")
    rows = cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "debugging"
    assert rows[0][1] == 300  # 100 + 200


def test_analyze_skills_handles_session_inactivity(tmp_path, monkeypatch):
    """Test that _analyze_skills finalizes outcomes on session inactivity."""
    from spellbook_mcp.watcher import SessionWatcher, SESSION_INACTIVE_THRESHOLD_SECONDS
    from spellbook_mcp.db import init_db, get_connection
    from spellbook_mcp.skill_analyzer import OUTCOME_SESSION_ENDED

    db_path = tmp_path / "test.db"
    project_path = tmp_path / "project"
    project_path.mkdir()
    init_db(str(db_path))

    # Create session file
    session_dir = tmp_path / ".claude" / "projects" / "-tmp-project"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "test-session.jsonl"
    messages = [
        {
            "type": "assistant",
            "timestamp": "2026-01-26T10:00:00",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                ],
            },
        },
    ]
    session_file.write_text("\n".join(json.dumps(m) for m in messages) + "\n")

    watcher = SessionWatcher(str(db_path), project_path=str(project_path))

    # First call to set up tracking
    with patch(
        "spellbook_mcp.compaction_detector._get_current_session_file",
        return_value=session_file,
    ):
        watcher._analyze_skills()

    # Simulate inactivity by setting last_activity in the past
    session_id = session_file.stem
    if session_id in watcher._skill_states:
        watcher._skill_states[session_id].last_activity = (
            datetime.now() - timedelta(seconds=SESSION_INACTIVE_THRESHOLD_SECONDS + 60)
        )

    # Insert a record with empty outcome to simulate open skill
    conn = get_connection(str(db_path))
    conn.execute("""
        INSERT OR REPLACE INTO skill_outcomes
        (skill_name, session_id, project_encoded, start_time, outcome)
        VALUES (?, ?, ?, ?, ?)
    """, ("debugging", session_id, "test", "2026-01-26T10:00:00", ""))
    conn.commit()

    # Second call should detect inactivity and finalize
    with patch(
        "spellbook_mcp.compaction_detector._get_current_session_file",
        return_value=session_file,
    ):
        watcher._analyze_skills()

    # Check outcome was finalized
    cursor = conn.cursor()
    cursor.execute("SELECT outcome FROM skill_outcomes WHERE skill_name = 'debugging'")
    row = cursor.fetchone()

    # Should be session_ended since skill was still open when session ended
    assert row is not None
    assert row[0] == OUTCOME_SESSION_ENDED


def test_session_skill_state_tracking(tmp_path):
    """Test SessionSkillState tracks invocations correctly."""
    from spellbook_mcp.watcher import SessionSkillState
    from spellbook_mcp.skill_analyzer import SkillInvocation

    state = SessionSkillState(session_id="test-session")

    inv = SkillInvocation(skill="debugging", start_idx=5)
    key = state.invocation_key(inv)

    assert key == "debugging:5"
    assert key not in state.known_invocations

    state.known_invocations.add(key)
    assert key in state.known_invocations


# --- Tests for _prune_expired_compactions ---


def test_prune_expired_compactions_removes_old_entries(tmp_path):
    """Test that entries older than 3600s are pruned."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path))

    now = time.time()
    # Add an entry that is 2 hours old (should be pruned)
    watcher._processed_compactions[("session-old", "leaf-old")] = now - 7200
    # Add an entry that is exactly at the boundary (should be pruned, > 3600)
    watcher._processed_compactions[("session-boundary", "leaf-boundary")] = now - 3601

    watcher._prune_expired_compactions()

    assert ("session-old", "leaf-old") not in watcher._processed_compactions
    assert ("session-boundary", "leaf-boundary") not in watcher._processed_compactions


def test_prune_expired_compactions_preserves_recent_entries(tmp_path):
    """Test that entries newer than 3600s are preserved."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path))

    now = time.time()
    # Add a recent entry (10 minutes ago, should be kept)
    watcher._processed_compactions[("session-recent", "leaf-recent")] = now - 600
    # Add an entry just under the boundary (should be kept)
    watcher._processed_compactions[("session-just-under", "leaf-just-under")] = now - 3599

    watcher._prune_expired_compactions()

    assert ("session-recent", "leaf-recent") in watcher._processed_compactions
    assert ("session-just-under", "leaf-just-under") in watcher._processed_compactions


def test_prune_expired_compactions_mixed_entries(tmp_path):
    """Test pruning with a mix of old and recent entries."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path))

    now = time.time()
    watcher._processed_compactions[("session-old", "leaf-old")] = now - 7200
    watcher._processed_compactions[("session-recent", "leaf-recent")] = now - 60

    watcher._prune_expired_compactions()

    assert ("session-old", "leaf-old") not in watcher._processed_compactions
    assert ("session-recent", "leaf-recent") in watcher._processed_compactions
    assert len(watcher._processed_compactions) == 1


def test_prune_expired_compactions_called_in_run_loop(tmp_path):
    """Test that _prune_expired_compactions is called during the run loop."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path), poll_interval=0.2)

    prune_calls = []
    original_prune = watcher._prune_expired_compactions

    def tracking_prune():
        prune_calls.append(time.time())
        original_prune()

    watcher._prune_expired_compactions = tracking_prune

    # Suppress _poll_sessions and _cleanup_stale_data to avoid side effects
    with patch.object(watcher, '_poll_sessions'):
        with patch.object(watcher, '_cleanup_stale_data'):
            thread = watcher.start()
            time.sleep(0.8)
            watcher.stop()
            thread.join(timeout=2.0)

    assert len(prune_calls) >= 1, "Prune should have been called at least once in the run loop"


# --- Tests for _cleanup_stale_data ---


def test_cleanup_stale_data_no_tables(tmp_path):
    """Test _cleanup_stale_data runs without error when tables don't exist."""
    from spellbook_mcp.watcher import SessionWatcher

    # Create a bare database with no tables
    db_path = tmp_path / "bare.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS heartbeat (id INTEGER PRIMARY KEY, timestamp TEXT)")
    conn.commit()
    conn.close()

    watcher = SessionWatcher(str(db_path))

    # Should not raise any exceptions
    watcher._cleanup_stale_data()


def test_cleanup_stale_data_deletes_old_rows(tmp_path):
    """Test that old rows are deleted and recent rows preserved."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    conn = get_connection(str(db_path))

    now = datetime.now()
    old_30d = (now - timedelta(days=35)).isoformat()
    recent_30d = (now - timedelta(days=5)).isoformat()
    old_90d = (now - timedelta(days=100)).isoformat()
    recent_90d = (now - timedelta(days=10)).isoformat()

    # Insert old and recent souls (30-day retention)
    conn.execute(
        """INSERT INTO souls (id, project_path, session_id, bound_at, persona)
           VALUES (?, ?, ?, ?, ?)""",
        ("old-soul", "/project", "session-old", old_30d, "Old Persona"),
    )
    conn.execute(
        """INSERT INTO souls (id, project_path, session_id, bound_at, persona)
           VALUES (?, ?, ?, ?, ?)""",
        ("recent-soul", "/project", "session-recent", recent_30d, "Recent Persona"),
    )

    # Insert old and recent skill_outcomes (90-day retention)
    conn.execute(
        """INSERT INTO skill_outcomes (skill_name, session_id, project_encoded, start_time, outcome, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("debugging", "session-old", "test", old_90d, "completed", old_90d),
    )
    conn.execute(
        """INSERT INTO skill_outcomes (skill_name, session_id, project_encoded, start_time, outcome, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("debugging", "session-recent", "test", recent_90d, "completed", recent_90d),
    )

    # Insert old and recent corrections (90-day retention)
    conn.execute(
        """INSERT INTO corrections (project_path, constraint_type, constraint_text, recorded_at)
           VALUES (?, ?, ?, ?)""",
        ("/project", "test", "old correction", old_90d),
    )
    conn.execute(
        """INSERT INTO corrections (project_path, constraint_type, constraint_text, recorded_at)
           VALUES (?, ?, ?, ?)""",
        ("/project", "test", "recent correction", recent_90d),
    )

    conn.commit()

    watcher = SessionWatcher(str(db_path))

    # Mock swarm and forged cleanup to isolate the test
    with patch("spellbook_mcp.watcher.SessionWatcher._cleanup_stale_data", wraps=watcher._cleanup_stale_data):
        with patch("spellbook_mcp.coordination.state.StateManager.cleanup_old_swarms", side_effect=Exception("skip")):
            with patch("spellbook_mcp.forged.schema.get_forged_connection", side_effect=Exception("skip")):
                watcher._cleanup_stale_data()

    # Verify old rows deleted, recent rows preserved
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM souls")
    soul_ids = [row[0] for row in cursor.fetchall()]
    assert "old-soul" not in soul_ids
    assert "recent-soul" in soul_ids

    cursor.execute("SELECT session_id FROM skill_outcomes")
    outcome_sessions = [row[0] for row in cursor.fetchall()]
    assert "session-old" not in outcome_sessions
    assert "session-recent" in outcome_sessions

    cursor.execute("SELECT constraint_text FROM corrections")
    correction_texts = [row[0] for row in cursor.fetchall()]
    assert "old correction" not in correction_texts
    assert "recent correction" in correction_texts


def test_cleanup_stale_data_respects_interval(tmp_path):
    """Test that cleanup only runs every CLEANUP_INTERVAL seconds."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path))

    cleanup_calls = []
    original_cleanup = watcher._cleanup_stale_data

    def tracking_cleanup():
        cleanup_calls.append(time.time())
        original_cleanup()

    watcher._cleanup_stale_data = tracking_cleanup

    # Simulate the run loop's interval check
    # First time: _last_cleanup is 0.0, so now - 0.0 > CLEANUP_INTERVAL => should run
    now = time.time()
    if now - watcher._last_cleanup > watcher.CLEANUP_INTERVAL:
        watcher._cleanup_stale_data()
        watcher._last_cleanup = now

    assert len(cleanup_calls) == 1

    # Second time immediately after: should NOT run
    now2 = time.time()
    if now2 - watcher._last_cleanup > watcher.CLEANUP_INTERVAL:
        watcher._cleanup_stale_data()
        watcher._last_cleanup = now2

    assert len(cleanup_calls) == 1, "Cleanup should not run again within CLEANUP_INTERVAL"

    # Third time: simulate time advancing past CLEANUP_INTERVAL
    watcher._last_cleanup = time.time() - watcher.CLEANUP_INTERVAL - 1
    now3 = time.time()
    if now3 - watcher._last_cleanup > watcher.CLEANUP_INTERVAL:
        watcher._cleanup_stale_data()
        watcher._last_cleanup = now3

    assert len(cleanup_calls) == 2, "Cleanup should run again after CLEANUP_INTERVAL elapsed"
