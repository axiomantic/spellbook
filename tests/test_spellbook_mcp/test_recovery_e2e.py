"""End-to-end integration test for recovery system."""

import pytest
import json
import time
from pathlib import Path


def test_recovery_e2e_flow(tmp_path):
    """Test complete recovery flow from compaction to injection."""
    from spellbook_mcp.db import init_db, get_connection
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.soul_extractor import extract_soul
    from spellbook_mcp.injection import build_recovery_context, _reset_state

    # Setup
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    project_path = str(tmp_path / "project")
    Path(project_path).mkdir()

    # Create test transcript
    transcript = tmp_path / "session.jsonl"
    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Skill", "args": {"skill": "writing-plans"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {
                    "tool": "TodoWrite",
                    "args": {
                        "todos": [
                            {"content": "Write tests", "status": "in_progress", "activeForm": "Writing tests"}
                        ]
                    }
                }
            ]
        },
        {
            "type": "summary",
            "summary": "Compaction occurred",
            "leafUuid": "test-uuid"
        }
    ]

    with open(transcript, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # Extract soul
    soul = extract_soul(str(transcript))

    assert soul["active_skill"] == "writing-plans"
    assert len(soul["todos"]) == 1

    # Store in database
    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO souls (id, project_path, active_skill, todos)
        VALUES (?, ?, ?, ?)
    """, (
        "soul-1",
        project_path,
        soul["active_skill"],
        json.dumps(soul["todos"])
    ))
    conn.commit()

    # Start watcher (verify heartbeat)
    watcher = SessionWatcher(db_path, poll_interval=0.5)
    thread = watcher.start()
    time.sleep(1.0)  # Wait for heartbeat

    # Build recovery context
    context = build_recovery_context(db_path, project_path)

    assert context is not None
    assert "writing-plans" in context
    assert "Write tests" in context

    # Cleanup
    watcher.stop()
    thread.join(timeout=2.0)

    _reset_state()


def test_recovery_e2e_injection_decorator(tmp_path):
    """Test that injection decorator properly wraps MCP tool responses."""
    from spellbook_mcp.db import init_db, get_connection
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.injection import (
        inject_recovery_context,
        _reset_state,
        _set_pending_compaction
    )
    import json

    # Setup
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    project_path = str(tmp_path / "project")
    Path(project_path).mkdir()

    # Insert soul into database
    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO souls (id, project_path, active_skill, todos, persona)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "soul-1",
        project_path,
        "debugging",
        json.dumps([{"content": "Fix bug", "status": "in_progress"}]),
        "fun:Detective Mode"
    ))
    conn.commit()

    # Start watcher for heartbeat
    watcher = SessionWatcher(db_path, poll_interval=0.5)
    thread = watcher.start()
    time.sleep(1.0)

    # Reset injection state
    _reset_state()

    # Create decorated function
    @inject_recovery_context
    def mock_tool():
        return {"status": "ok"}

    # Trigger compaction (should inject on next call)
    _set_pending_compaction(True)

    # Patch get_db_path and os.getcwd for the injection module
    import os
    original_cwd = os.getcwd
    os.getcwd = lambda: project_path

    try:
        from spellbook_mcp import injection
        original_get_db_path = injection.get_db_path
        injection.get_db_path = lambda: Path(db_path)

        result = mock_tool()

        # Should have injected recovery context
        assert "__system_reminder" in result
        assert "debugging" in result["__system_reminder"]
        assert "Fix bug" in result["__system_reminder"]

        # Restore
        injection.get_db_path = original_get_db_path
    finally:
        os.getcwd = original_cwd
        watcher.stop()
        thread.join(timeout=2.0)
        _reset_state()


def test_recovery_e2e_no_injection_without_heartbeat(tmp_path):
    """Test that injection doesn't occur without watcher heartbeat."""
    from spellbook_mcp.db import init_db, get_connection
    from spellbook_mcp.injection import (
        inject_recovery_context,
        _reset_state,
        _set_pending_compaction
    )
    import json

    # Setup database but don't start watcher
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    project_path = str(tmp_path / "project")
    Path(project_path).mkdir()

    # Insert soul into database
    conn = get_connection(db_path)
    conn.execute("""
        INSERT INTO souls (id, project_path, active_skill, todos)
        VALUES (?, ?, ?, ?)
    """, (
        "soul-1",
        project_path,
        "debugging",
        json.dumps([{"content": "Fix bug", "status": "in_progress"}])
    ))
    conn.commit()

    # Reset injection state
    _reset_state()

    # Create decorated function
    @inject_recovery_context
    def mock_tool():
        return {"status": "ok"}

    # Trigger compaction
    _set_pending_compaction(True)

    # Patch paths
    import os
    original_cwd = os.getcwd
    os.getcwd = lambda: project_path

    try:
        from spellbook_mcp import injection
        original_get_db_path = injection.get_db_path
        injection.get_db_path = lambda: Path(db_path)

        result = mock_tool()

        # Should NOT have injected (no heartbeat means watcher not running)
        assert result == {"status": "ok"}

        injection.get_db_path = original_get_db_path
    finally:
        os.getcwd = original_cwd
        _reset_state()


def test_recovery_e2e_watcher_lifecycle(tmp_path):
    """Test watcher starts, writes heartbeats, and stops cleanly."""
    from spellbook_mcp.db import init_db
    from spellbook_mcp.watcher import SessionWatcher, is_heartbeat_fresh

    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    # Start watcher
    watcher = SessionWatcher(db_path, poll_interval=0.5)
    assert not watcher.is_running()

    thread = watcher.start()
    assert watcher.is_running()

    # Wait for heartbeat
    time.sleep(1.5)
    assert is_heartbeat_fresh(db_path, max_age=5.0)

    # Stop watcher
    watcher.stop()
    thread.join(timeout=2.0)
    assert not watcher.is_running()
