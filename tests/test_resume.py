"""Tests for session resume detection and boot prompt generation."""

import pytest
from typing import Optional


class TestContinuationIntent:
    """Tests for continuation intent detection."""

    def test_continuation_intent_has_required_fields(self):
        """Test that ContinuationIntent TypedDict has all required fields."""
        from spellbook_mcp.resume import ContinuationIntent

        # Create instance to verify structure
        intent: ContinuationIntent = {
            "intent": "continue",
            "confidence": "high",
            "pattern": r"^\s*continue\s*$",
        }

        assert intent["intent"] == "continue"
        assert intent["confidence"] == "high"
        assert intent["pattern"] == r"^\s*continue\s*$"

    def test_continuation_intent_pattern_can_be_none(self):
        """Test that pattern field can be None for neutral intent."""
        from spellbook_mcp.resume import ContinuationIntent

        intent: ContinuationIntent = {
            "intent": "neutral",
            "confidence": "low",
            "pattern": None,
        }

        assert intent["pattern"] is None


class TestDetectContinuationIntent:
    """Tests for detect_continuation_intent function."""

    @pytest.mark.parametrize("message,expected_intent,expected_confidence", [
        ("continue", "continue", "high"),
        ("Continue", "continue", "high"),
        ("  continue  ", "continue", "high"),
        ("resume", "continue", "high"),
        ("where were we", "continue", "high"),
        ("pick up where we left off", "continue", "high"),
        ("let's continue", "continue", "high"),
        ("lets continue", "continue", "high"),
        ("carry on", "continue", "high"),
        ("what were we doing", "continue", "high"),
        ("what were we working on", "continue", "high"),
        ("back to it", "continue", "high"),
        ("back to work", "continue", "high"),
    ])
    def test_explicit_continue_patterns(self, message, expected_intent, expected_confidence):
        """Test explicit continue patterns are detected with high confidence."""
        from spellbook_mcp.resume import detect_continuation_intent

        result = detect_continuation_intent(message, has_recent_session=False)

        assert result["intent"] == expected_intent
        assert result["confidence"] == expected_confidence
        assert result["pattern"] is not None

    @pytest.mark.parametrize("message", [
        "start fresh",
        "begin fresh",
        "start new",
        "begin new",
        "start over",
        "new session",
        "new task",
        "new project",
        "forget previous",
        "forget last",
        "forget prior",
        "clean slate",
        "from scratch",
        "from beginning",
    ])
    def test_fresh_start_patterns(self, message):
        """Test fresh start patterns override resume even if session exists."""
        from spellbook_mcp.resume import detect_continuation_intent

        result = detect_continuation_intent(message, has_recent_session=True)

        assert result["intent"] == "fresh_start"
        assert result["confidence"] == "high"
        assert result["pattern"] is not None

    @pytest.mark.parametrize("message", [
        "ok",
        "okay",
        "alright",
        "sure",
        "ready",
        "go",
        "next",
        "next step",
        "next task",
        "next item",
        "and then",
        "also, let's",
    ])
    def test_implicit_continue_with_session(self, message):
        """Test implicit patterns trigger continue only with recent session."""
        from spellbook_mcp.resume import detect_continuation_intent

        # With recent session: medium confidence continue
        result = detect_continuation_intent(message, has_recent_session=True)
        assert result["intent"] == "continue"
        assert result["confidence"] == "medium"

    @pytest.mark.parametrize("message", [
        "ok",
        "okay",
        "next",
        "sure",
    ])
    def test_implicit_patterns_without_session(self, message):
        """Test implicit patterns return neutral without recent session."""
        from spellbook_mcp.resume import detect_continuation_intent

        result = detect_continuation_intent(message, has_recent_session=False)
        assert result["intent"] == "neutral"
        assert result["confidence"] == "low"


class TestCountPendingTodos:
    """Tests for count_pending_todos function."""

    def test_count_pending_todos_none_input(self):
        """Test None input returns (0, False)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos(None)

        assert count == 0
        assert corrupted is False

    def test_count_pending_todos_empty_array(self):
        """Test empty array returns (0, False)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos("[]")

        assert count == 0
        assert corrupted is False

    def test_count_pending_todos_with_pending(self):
        """Test counts non-completed todos."""
        from spellbook_mcp.resume import count_pending_todos
        import json

        todos = json.dumps([
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "status": "completed"},
        ])

        count, corrupted = count_pending_todos(todos)

        assert count == 2
        assert corrupted is False

    def test_count_pending_todos_all_completed(self):
        """Test all completed returns 0."""
        from spellbook_mcp.resume import count_pending_todos
        import json

        todos = json.dumps([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "completed"},
        ])

        count, corrupted = count_pending_todos(todos)

        assert count == 0
        assert corrupted is False

    def test_count_pending_todos_malformed_json(self):
        """Test malformed JSON returns (0, True)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos("not valid json")

        assert count == 0
        assert corrupted is True

    def test_count_pending_todos_not_array(self):
        """Test non-array JSON returns (0, True)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos('{"key": "value"}')

        assert count == 0
        assert corrupted is True

    def test_count_pending_todos_mixed_items(self):
        """Test handles mixed item types gracefully."""
        from spellbook_mcp.resume import count_pending_todos
        import json

        todos = json.dumps([
            {"content": "Valid", "status": "pending"},
            "not a dict",
            None,
            {"content": "Also valid", "status": "in_progress"},
        ])

        count, corrupted = count_pending_todos(todos)

        # Should count valid pending items and not crash
        assert count == 2
        assert corrupted is False


class TestFindPlanningDocs:
    """Tests for _find_planning_docs function."""

    def test_find_impl_docs(self, tmp_path):
        """Test finds *-impl.md files."""
        from spellbook_mcp.resume import _find_planning_docs

        # Create test files
        impl_doc = tmp_path / "feature-impl.md"
        impl_doc.write_text("# Implementation Plan")

        recent_files = [str(impl_doc), "/other/file.py"]

        result = _find_planning_docs(recent_files)

        assert str(impl_doc) in result

    def test_find_design_docs(self, tmp_path):
        """Test finds *-design.md files."""
        from spellbook_mcp.resume import _find_planning_docs

        design_doc = tmp_path / "feature-design.md"
        design_doc.write_text("# Design Doc")

        result = _find_planning_docs([str(design_doc)])

        assert str(design_doc) in result

    def test_find_plan_docs(self, tmp_path):
        """Test finds *-plan.md files."""
        from spellbook_mcp.resume import _find_planning_docs

        plan_doc = tmp_path / "feature-plan.md"
        plan_doc.write_text("# Plan")

        result = _find_planning_docs([str(plan_doc)])

        assert str(plan_doc) in result

    def test_find_plans_directory(self, tmp_path):
        """Test finds files in plans/ directories."""
        from spellbook_mcp.resume import _find_planning_docs

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        doc = plans_dir / "something.md"
        doc.write_text("# In plans dir")

        result = _find_planning_docs([str(doc)])

        assert str(doc) in result

    def test_skips_missing_files(self, tmp_path):
        """Test skips files that no longer exist."""
        from spellbook_mcp.resume import _find_planning_docs

        # Reference non-existent file
        missing = str(tmp_path / "missing-impl.md")

        result = _find_planning_docs([missing])

        assert missing not in result
        assert result == []

    def test_limits_to_three_docs(self, tmp_path):
        """Test limits result to 3 documents."""
        from spellbook_mcp.resume import _find_planning_docs

        docs = []
        for i in range(5):
            doc = tmp_path / f"doc{i}-impl.md"
            doc.write_text(f"# Doc {i}")
            docs.append(str(doc))

        result = _find_planning_docs(docs)

        assert len(result) == 3


class TestGenerateBootPrompt:
    """Tests for generate_boot_prompt function."""

    def test_boot_prompt_has_section_0_header(self):
        """Test boot prompt starts with Section 0 header."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
        }

        result = generate_boot_prompt(soul)

        assert "## SECTION 0: MANDATORY FIRST ACTIONS" in result
        assert "Execute IMMEDIATELY" in result

    def test_boot_prompt_no_active_skill(self):
        """Test boot prompt handles no active skill."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "active_skill": None,
        }

        result = generate_boot_prompt(soul)

        assert "### 0.1 Workflow Restoration" in result
        assert "NO ACTIVE SKILL - proceed to 0.2" in result

    def test_boot_prompt_with_active_skill(self):
        """Test boot prompt includes Skill() call when active."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "active_skill": "implementing-features",
            "skill_phase": "DESIGN",
        }

        result = generate_boot_prompt(soul)

        assert 'Skill("implementing-features"' in result
        assert '--resume DESIGN' in result

    def test_boot_prompt_with_skill_no_phase(self):
        """Test boot prompt handles skill without phase."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "active_skill": "debugging",
            "skill_phase": None,
        }

        result = generate_boot_prompt(soul)

        assert 'Skill("debugging")' in result
        assert "--resume" not in result

    def test_boot_prompt_has_checkpoint_section(self):
        """Test boot prompt includes restoration checkpoint."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
        }

        result = generate_boot_prompt(soul)

        assert "### 0.4 Restoration Checkpoint" in result
        assert "Skill invoked?" in result
        assert "Documents read?" in result
        assert "Todos restored?" in result

    def test_boot_prompt_has_constraints_section(self):
        """Test boot prompt includes behavioral constraints."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "workflow_pattern": "TDD",
        }

        result = generate_boot_prompt(soul)

        assert "### 0.5 Behavioral Constraints" in result
        assert "workflow pattern: TDD" in result
        assert "Honor decisions from prior session" in result

    def test_boot_prompt_with_todos(self):
        """Test boot prompt includes TodoWrite for pending todos."""
        from spellbook_mcp.resume import generate_boot_prompt
        import json

        todos = json.dumps([
            {"content": "Implement login", "status": "pending"},
            {"content": "Write tests", "status": "in_progress"},
        ])

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "todos": todos,
        }

        result = generate_boot_prompt(soul)

        assert "### 0.3 Todo State Restoration" in result
        assert "TodoWrite(" in result
        assert "Implement login" in result
        assert "Write tests" in result

    def test_boot_prompt_no_todos(self):
        """Test boot prompt handles no todos."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "todos": None,
        }

        result = generate_boot_prompt(soul)

        assert "NO TODOS TO RESTORE" in result

    def test_boot_prompt_empty_todos(self):
        """Test boot prompt handles empty todos array."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "todos": "[]",
        }

        result = generate_boot_prompt(soul)

        assert "NO TODOS TO RESTORE" in result

    def test_boot_prompt_with_planning_docs(self, tmp_path):
        """Test boot prompt includes Read() for planning docs."""
        from spellbook_mcp.resume import generate_boot_prompt

        # Create actual planning doc
        impl_doc = tmp_path / "feature-impl.md"
        impl_doc.write_text("# Implementation Plan")

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "recent_files": [str(impl_doc)],
        }

        result = generate_boot_prompt(soul)

        assert "### 0.2 Required Document Reads" in result
        assert f'Read("{impl_doc}")' in result

    def test_boot_prompt_no_planning_docs(self):
        """Test boot prompt handles no planning docs."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "id": "test-soul-1",
            "session_id": "session-1",
            "project_path": "/test/project",
            "bound_at": "2026-01-27T10:00:00",
            "recent_files": None,
        }

        result = generate_boot_prompt(soul)

        assert "NO DOCUMENTS TO READ" in result


class TestGetResumeFields:
    """Tests for get_resume_fields function."""

    def test_no_recent_session_returns_unavailable(self, tmp_path):
        """Test returns resume_available=False when no recent session."""
        from spellbook_mcp.resume import get_resume_fields
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = get_resume_fields("/test/project", str(db_path))

        assert result["resume_available"] is False
        assert result.get("resume_session_id") is None

    def test_recent_session_returns_resume_fields(self, tmp_path):
        """Test returns resume fields when recent session exists."""
        from spellbook_mcp.resume import get_resume_fields
        from spellbook_mcp.db import init_db, get_connection
        import json
        from datetime import datetime

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Insert a recent soul
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill, skill_phase, todos)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "soul-1",
            "session-1",
            "/test/project",
            datetime.now().isoformat(),
            "implementing-features",
            "DESIGN",
            json.dumps([{"content": "Task 1", "status": "pending"}]),
        ))
        conn.commit()

        result = get_resume_fields("/test/project", str(db_path))

        assert result["resume_available"] is True
        assert result["resume_session_id"] == "soul-1"
        assert result["resume_active_skill"] == "implementing-features"
        assert result["resume_skill_phase"] == "DESIGN"
        assert result["resume_pending_todos"] == 1
        assert result["resume_boot_prompt"] is not None

    def test_old_session_not_returned(self, tmp_path):
        """Test sessions older than 24h are not returned."""
        from spellbook_mcp.resume import get_resume_fields
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime, timedelta

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Insert an old soul (25 hours ago)
        old_time = (datetime.now() - timedelta(hours=25)).isoformat()
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill)
            VALUES (?, ?, ?, ?, ?)
        """, ("soul-old", "session-old", "/test/project", old_time, "debugging"))
        conn.commit()

        result = get_resume_fields("/test/project", str(db_path))

        assert result["resume_available"] is False

    def test_corrupted_todos_sets_flag(self, tmp_path):
        """Test corrupted todos JSON sets resume_todos_corrupted flag."""
        from spellbook_mcp.resume import get_resume_fields
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, todos)
            VALUES (?, ?, ?, ?, ?)
        """, ("soul-1", "session-1", "/test/project", datetime.now().isoformat(), "not valid json"))
        conn.commit()

        result = get_resume_fields("/test/project", str(db_path))

        assert result["resume_available"] is True
        assert result["resume_todos_corrupted"] is True
        assert result["resume_pending_todos"] == 0


class TestSessionInitResume:
    """Tests for session_init resume integration."""

    def test_session_init_accepts_continuation_message(self, tmp_path, monkeypatch):
        """Test session_init accepts continuation_message parameter."""
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr("spellbook_mcp.db.get_db_path", lambda: db_path)

        from spellbook_mcp.config_tools import session_init

        # Should not raise
        result = session_init(session_id=None, continuation_message="continue")

        assert "mode" in result
        assert "resume_available" in result

    def test_session_init_resume_fields_present(self, tmp_path, monkeypatch):
        """Test session_init includes resume fields in response."""
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime
        import json

        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr("spellbook_mcp.db.get_db_path", lambda: db_path)

        # Insert a recent soul
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill, skill_phase)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("soul-1", "session-1", "/tmp", datetime.now().isoformat(), "debugging", "ANALYZE"))
        conn.commit()

        # Mock getcwd to return matching project path
        monkeypatch.setattr("os.getcwd", lambda: "/tmp")

        from spellbook_mcp.config_tools import session_init

        result = session_init(session_id=None, continuation_message="continue")

        assert result["resume_available"] is True
        assert result["resume_active_skill"] == "debugging"

    def test_session_init_fresh_start_overrides(self, tmp_path, monkeypatch):
        """Test fresh start message overrides available resume."""
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr("spellbook_mcp.db.get_db_path", lambda: db_path)

        # Insert a recent soul
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill)
            VALUES (?, ?, ?, ?, ?)
        """, ("soul-1", "session-1", "/tmp", datetime.now().isoformat(), "debugging"))
        conn.commit()

        monkeypatch.setattr("os.getcwd", lambda: "/tmp")

        from spellbook_mcp.config_tools import session_init

        result = session_init(session_id=None, continuation_message="start fresh")

        assert result["resume_available"] is False
