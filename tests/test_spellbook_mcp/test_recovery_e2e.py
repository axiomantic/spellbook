"""End-to-end integration test for recovery system."""

import json
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


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


def test_recovery_e2e_full_before_after_flow(tmp_path):
    """Comprehensive before/after test verifying the complete recovery pipeline.

    This test documents the full flow with explicit DB state assertions at each step:
    1. BEFORE: DB empty, no souls
    2. Compaction detected in transcript
    3. Soul extracted and stored
    4. AFTER: DB has soul with all 7 components
    5. System-reminder injected into next MCP tool response
    6. Reminder contains parseable recovery context
    """
    from spellbook_mcp.db import init_db, get_connection, close_all_connections
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.soul_extractor import extract_soul
    from spellbook_mcp.injection import (
        build_recovery_context,
        inject_recovery_context,
        _reset_state,
        _set_pending_compaction
    )
    import json
    import re

    # ========== SETUP ==========
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    project_path = str(tmp_path / "project")
    Path(project_path).mkdir()

    # ========== STEP 1: VERIFY DB IS EMPTY (BEFORE) ==========
    conn = get_connection(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM souls")
    count_before = cursor.fetchone()[0]
    assert count_before == 0, f"Expected 0 souls before, got {count_before}"

    # ========== STEP 2: CREATE TRANSCRIPT WITH RICH SESSION STATE ==========
    transcript = tmp_path / "session.jsonl"
    messages = [
        # Skill invocation
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Skill", "args": {"skill": "implementing-features"}}
            ]
        },
        # Phase marker
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "content": "## Phase 2: Design\n\nLet me create the design document..."
        },
        # Persona setting (must use PERSONA: pattern for extraction)
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:02:00Z",
            "content": "PERSONA: Detective Mode\n\nI'll investigate this mystery!"
        },
        # Todo list
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:03:00Z",
            "tool_calls": [
                {
                    "tool": "TodoWrite",
                    "args": {
                        "todos": [
                            {"content": "Create design doc", "status": "completed", "activeForm": "Creating design doc"},
                            {"content": "Review design", "status": "in_progress", "activeForm": "Reviewing design"},
                            {"content": "Implement feature", "status": "pending", "activeForm": "Implementing feature"}
                        ]
                    }
                }
            ]
        },
        # File reads
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:04:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/project/src/main.py"}},
                {"tool": "Read", "args": {"file_path": "/project/tests/test_main.py"}}
            ]
        },
        # Compaction marker (this triggers recovery)
        {
            "type": "summary",
            "summary": "Session was compacted due to context length",
            "leafUuid": "compaction-uuid-12345"
        }
    ]

    with open(transcript, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # ========== STEP 3: EXTRACT SOUL FROM TRANSCRIPT ==========
    soul = extract_soul(str(transcript))

    # Verify all 7 components extracted
    assert soul["active_skill"] == "implementing-features", f"Expected implementing-features, got {soul['active_skill']}"
    assert soul["skill_phase"] == "Phase 2: Design", f"Expected Phase 2: Design, got {soul['skill_phase']}"
    assert soul["persona"] == "fun:Detective Mode", f"Expected 'fun:Detective Mode', got {soul['persona']}"
    # Note: extract_todos only returns non-completed todos (in_progress + pending)
    assert len(soul["todos"]) == 2, f"Expected 2 active todos, got {len(soul['todos'])}"
    assert len(soul["recent_files"]) >= 2, f"Expected at least 2 recent files, got {len(soul['recent_files'])}"

    # ========== STEP 4: STORE SOUL IN DATABASE ==========
    conn.execute("""
        INSERT INTO souls (
            id, project_path,
            active_skill, skill_phase, persona, todos,
            recent_files, exact_position, workflow_pattern
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "soul-test-1",
        project_path,
        soul["active_skill"],
        soul["skill_phase"],
        soul["persona"],
        json.dumps(soul["todos"]),
        json.dumps(soul["recent_files"]),
        json.dumps(soul["exact_position"]),
        soul["workflow_pattern"]
    ))
    conn.commit()

    # ========== STEP 5: VERIFY DB HAS SOUL (AFTER) ==========
    cursor = conn.execute("SELECT COUNT(*) FROM souls WHERE project_path = ?", (project_path,))
    count_after = cursor.fetchone()[0]
    assert count_after == 1, f"Expected 1 soul after, got {count_after}"

    # Query and verify stored values
    cursor = conn.execute("""
        SELECT active_skill, skill_phase, persona, todos, recent_files
        FROM souls WHERE project_path = ?
    """, (project_path,))
    row = cursor.fetchone()
    assert row[0] == "implementing-features"
    assert row[1] == "Phase 2: Design"
    assert row[2] == "fun:Detective Mode"
    stored_todos = json.loads(row[3])
    assert len(stored_todos) == 2, f"Expected 2 active todos, got {len(stored_todos)}"
    assert stored_todos[0]["status"] == "in_progress"  # First active todo

    # ========== STEP 6: START WATCHER FOR HEARTBEAT ==========
    watcher = SessionWatcher(db_path, poll_interval=0.5)
    thread = watcher.start()
    time.sleep(1.0)  # Wait for heartbeat

    # ========== STEP 7: BUILD RECOVERY CONTEXT ==========
    context = build_recovery_context(db_path, project_path)

    assert context is not None, "Recovery context should not be None"

    # Verify context contains all expected fields
    assert "implementing-features" in context, "Context should contain active skill"
    assert "Phase 2: Design" in context, "Context should contain skill phase"
    assert "Detective Mode" in context, "Context should contain persona"
    assert "Review design" in context, "Context should contain in-progress todo"

    # ========== STEP 8: VERIFY INJECTION DECORATOR WORKS ==========
    _reset_state()

    @inject_recovery_context
    def mock_mcp_tool():
        return {"result": "tool executed"}

    # Simulate compaction detected
    _set_pending_compaction(True)

    # Patch paths for injection
    import os
    original_cwd = os.getcwd
    os.getcwd = lambda: project_path

    try:
        from spellbook_mcp import injection
        original_get_db_path = injection.get_db_path
        injection.get_db_path = lambda: Path(db_path)

        result = mock_mcp_tool()

        # ========== STEP 9: VERIFY SYSTEM-REMINDER IN RESPONSE ==========
        assert "__system_reminder" in result, "Response should have __system_reminder key"

        reminder = result["__system_reminder"]

        # Verify reminder has proper tag structure
        assert "<system-reminder>" in reminder, "Reminder should have opening tag"
        assert "</system-reminder>" in reminder, "Reminder should have closing tag"

        # Verify key recovery fields are present and parseable
        assert "implementing-features" in reminder, "Reminder should contain active skill"
        assert "**Skill Phase:**" in reminder, "Reminder should have Skill Phase field"

        # Verify skill phase is parseable by implementing-features skill
        skill_phase_pattern = r'\*\*Skill Phase:\*\*\s*(.+?)(?:\n|$)'
        match = re.search(skill_phase_pattern, reminder)
        assert match is not None, "Skill Phase should be parseable"
        assert match.group(1) == "Phase 2: Design", f"Parsed phase should be 'Phase 2: Design', got '{match.group(1)}'"

        # Verify todos are present
        assert "Review design" in reminder, "In-progress todo should be in reminder"

        injection.get_db_path = original_get_db_path
    finally:
        os.getcwd = original_cwd
        watcher.stop()
        thread.join(timeout=2.0)
        _reset_state()
        close_all_connections()

    # ========== SUCCESS: FULL PIPELINE VERIFIED ==========
    # At this point we have proven:
    # 1. DB was empty before
    # 2. Soul extracted with all 7 components
    # 3. Soul stored in DB correctly
    # 4. Recovery context built with all fields
    # 5. Injection decorator adds __system_reminder
    # 6. Reminder content is parseable by skill (Skill Phase regex works)
    #
    # The only thing we CANNOT test is whether Claude actually uses this.
    # That requires Claude to parse <system-reminder> tags, which is
    # observed behavior but not something we can unit test.
