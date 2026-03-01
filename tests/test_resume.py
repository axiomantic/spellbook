"""Tests for session resume detection and boot prompt generation."""

import json
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


class TestAgentsSpellbookMdSessionResume:
    """Tests for AGENTS.spellbook.md session resume documentation."""

    def test_session_resume_section_exists(self):
        """Test AGENTS.spellbook.md has ## Session Resume section."""
        from pathlib import Path

        spellbook_md = Path(__file__).parent.parent / "AGENTS.spellbook.md"
        content = spellbook_md.read_text()

        assert "## Session Resume" in content

    def test_session_resume_has_field_table(self):
        """Test Session Resume section has field documentation table."""
        from pathlib import Path

        spellbook_md = Path(__file__).parent.parent / "AGENTS.spellbook.md"
        content = spellbook_md.read_text()

        assert "resume_available" in content
        assert "resume_boot_prompt" in content

    def test_session_init_call_includes_continuation_message(self):
        """Test session_init call site includes continuation_message parameter."""
        from pathlib import Path

        spellbook_md = Path(__file__).parent.parent / "AGENTS.spellbook.md"
        content = spellbook_md.read_text()

        # Should document passing user's first message
        assert "continuation_message" in content


class TestIntegrationEndToEnd:
    """End-to-end integration tests for session resume flow."""

    def test_full_flow_new_session_no_resume(self, tmp_path, monkeypatch):
        """Test full flow: new session with no prior session to resume."""
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr("spellbook_mcp.db.get_db_path", lambda: db_path)
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        from spellbook_mcp.config_tools import session_init

        result = session_init(
            session_id="test-session-1",
            continuation_message="Let's implement a new feature"
        )

        # Mode should be set (unset in this case)
        assert "mode" in result
        # No resume available
        assert result["resume_available"] is False

    def test_full_flow_continue_prior_session(self, tmp_path, monkeypatch):
        """Test full flow: continue prior session with active skill."""
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime
        import json

        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr("spellbook_mcp.db.get_db_path", lambda: db_path)
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        # Create a planning doc
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_doc = plans_dir / "feature-impl.md"
        plan_doc.write_text("# Implementation Plan\n\n## Task 1\nDo something")

        # Insert a recent soul
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill, skill_phase, todos, recent_files, workflow_pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "soul-1",
            "prior-session",
            str(tmp_path),
            datetime.now().isoformat(),
            "implementing-features",
            "IMPLEMENT",
            json.dumps([{"content": "Complete task 3", "status": "pending"}]),
            json.dumps([str(plan_doc)]),
            "TDD",
        ))
        conn.commit()

        from spellbook_mcp.config_tools import session_init

        result = session_init(
            session_id="new-session",
            continuation_message="continue"
        )

        # Resume should be available
        assert result["resume_available"] is True
        assert result["resume_active_skill"] == "implementing-features"
        assert result["resume_skill_phase"] == "IMPLEMENT"
        assert result["resume_pending_todos"] == 1
        assert result["resume_workflow_pattern"] == "TDD"

        # Boot prompt should contain restoration instructions
        boot_prompt = result["resume_boot_prompt"]
        assert "SECTION 0" in boot_prompt
        assert 'Skill("implementing-features"' in boot_prompt
        assert "--resume IMPLEMENT" in boot_prompt
        assert "TodoWrite(" in boot_prompt
        assert "workflow pattern: TDD" in boot_prompt

    def test_full_flow_fresh_start_overrides(self, tmp_path, monkeypatch):
        """Test full flow: fresh start overrides even when prior session exists."""
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = tmp_path / "test.db"
        init_db(str(db_path))
        monkeypatch.setattr("spellbook_mcp.db.get_db_path", lambda: db_path)
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        # Insert a recent soul
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill)
            VALUES (?, ?, ?, ?, ?)
        """, ("soul-1", "prior-session", str(tmp_path), datetime.now().isoformat(), "debugging"))
        conn.commit()

        from spellbook_mcp.config_tools import session_init

        result = session_init(
            session_id="new-session",
            continuation_message="start fresh - I want to work on something new"
        )

        # User said "start fresh" so resume should NOT be available
        assert result["resume_available"] is False


class TestAllowedStateKeys:
    """Tests for _ALLOWED_STATE_KEYS expansion (T2)."""

    def test_new_keys_present(self):
        """Test that skill_constraints, decisions_binding, identity_role are in _ALLOWED_STATE_KEYS."""
        from spellbook_mcp.resume import _ALLOWED_STATE_KEYS

        assert "skill_constraints" in _ALLOWED_STATE_KEYS
        assert "decisions_binding" in _ALLOWED_STATE_KEYS
        assert "identity_role" in _ALLOWED_STATE_KEYS

    def test_original_keys_still_present(self):
        """Test that original keys are still present after expansion."""
        from spellbook_mcp.resume import _ALLOWED_STATE_KEYS

        for key in ("active_skill", "skill_phase", "todos", "recent_files",
                     "workflow_pattern", "boot_prompt", "pending_todos"):
            assert key in _ALLOWED_STATE_KEYS


class TestExtractSectionContent:
    """Tests for _extract_section_content helper (T8)."""

    def test_extracts_matching_section(self):
        """Test extraction of content between matching XML tags."""
        from spellbook_mcp.resume import _extract_section_content

        content = "Preamble\n<FORBIDDEN>\n- Do not do X\n- Do not do Y\n</FORBIDDEN>\nPostamble"
        result = _extract_section_content(content, "FORBIDDEN")

        assert result is not None
        assert "Do not do X" in result
        assert "Do not do Y" in result

    def test_returns_none_for_no_match(self):
        """Test returns None when section tag is not present."""
        from spellbook_mcp.resume import _extract_section_content

        content = "Just some text with no tags."
        result = _extract_section_content(content, "FORBIDDEN")

        assert result is None

    def test_case_insensitive(self):
        """Test that tag matching is case-insensitive."""
        from spellbook_mcp.resume import _extract_section_content

        content = "<forbidden>\n- item\n</forbidden>"
        result = _extract_section_content(content, "FORBIDDEN")

        assert result is not None
        assert "item" in result

    def test_multiple_sections_concatenated(self):
        """Test that multiple matching sections are concatenated."""
        from spellbook_mcp.resume import _extract_section_content

        content = "<FORBIDDEN>\nFirst block\n</FORBIDDEN>\nMiddle\n<FORBIDDEN>\nSecond block\n</FORBIDDEN>"
        result = _extract_section_content(content, "FORBIDDEN")

        assert result is not None
        assert "First block" in result
        assert "Second block" in result


class TestParseSectionItems:
    """Tests for _parse_section_items helper (T8)."""

    def test_strips_dash_bullets(self):
        """Test strips leading '- ' from items."""
        from spellbook_mcp.resume import _parse_section_items

        text = "- Item one\n- Item two"
        result = _parse_section_items(text)

        assert result == ["Item one", "Item two"]

    def test_strips_asterisk_bullets(self):
        """Test strips leading '* ' from items."""
        from spellbook_mcp.resume import _parse_section_items

        text = "* Alpha\n* Beta"
        result = _parse_section_items(text)

        assert result == ["Alpha", "Beta"]

    def test_strips_numbered_bullets(self):
        """Test strips leading '1. ' style from items."""
        from spellbook_mcp.resume import _parse_section_items

        text = "1. First\n2. Second\n10. Tenth"
        result = _parse_section_items(text)

        assert result == ["First", "Second", "Tenth"]

    def test_skips_empty_lines(self):
        """Test skips empty lines."""
        from spellbook_mcp.resume import _parse_section_items

        text = "- Item\n\n\n- Other"
        result = _parse_section_items(text)

        assert result == ["Item", "Other"]

    def test_filters_bold_subheaders(self):
        """Test filters out lines that are entirely bold sub-headers."""
        from spellbook_mcp.resume import _parse_section_items

        text = "**Phase 0 violations:**\n- Do not skip\n**More header:**\n- Also important"
        result = _parse_section_items(text)

        assert "Phase 0 violations:" not in result
        assert "Do not skip" in result
        assert "Also important" in result


class TestGetSkillConstraints:
    """Tests for _get_skill_constraints function (T8)."""

    def test_real_skill_with_forbidden(self):
        """Test extracting FORBIDDEN constraints from debugging skill."""
        from spellbook_mcp.resume import _get_skill_constraints

        result = _get_skill_constraints("debugging")

        assert isinstance(result, dict)
        assert "forbidden" in result
        assert "required" in result
        assert len(result["forbidden"]) > 0  # debugging has FORBIDDEN sections

    def test_nonexistent_skill_returns_empty(self):
        """Test non-existent skill returns empty lists."""
        from spellbook_mcp.resume import _get_skill_constraints

        result = _get_skill_constraints("this-skill-does-not-exist-xyz")

        assert result == {"forbidden": [], "required": []}

    def test_returns_dict_structure(self):
        """Test return value always has forbidden and required keys."""
        from spellbook_mcp.resume import _get_skill_constraints

        result = _get_skill_constraints("debugging")

        assert isinstance(result["forbidden"], list)
        assert isinstance(result["required"], list)
        # All items should be strings
        for item in result["forbidden"]:
            assert isinstance(item, str)
        for item in result["required"]:
            assert isinstance(item, str)


class TestBootPromptSignature:
    """Tests for generate_boot_prompt signature changes (T3)."""

    def test_backward_compatible_no_new_params(self):
        """Calling with just soul dict works (backward compatible)."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "active_skill": "test-skill",
            "skill_phase": "IMPLEMENT",
            "todos": None,
            "recent_files": [],
            "workflow_pattern": "TDD",
        }
        result = generate_boot_prompt(soul)
        assert "SECTION 0" in result
        assert "test-skill" in result

    def test_accepts_skill_constraints_param(self):
        """Passing skill_constraints does not raise."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(
            soul,
            skill_constraints={"forbidden": ["x"], "required": ["y"]},
        )
        assert isinstance(result, str)

    def test_accepts_binding_decisions_param(self):
        """Passing binding_decisions does not raise."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(
            soul,
            binding_decisions=["Use approach X"],
        )
        assert isinstance(result, str)

    def test_accepts_identity_role_param(self):
        """Passing identity_role does not raise."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(
            soul,
            identity_role="orchestrator",
        )
        assert isinstance(result, str)


class TestGenerateBootPromptWithIdentityRole:
    """Tests for Section 0.6 identity role restoration (T4)."""

    def test_orchestrator_identity_always_present(self):
        """Section 0.6 Orchestrator Identity is always in the output."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(soul)
        assert "### 0.6 Orchestrator Identity" in result
        assert "ORCHESTRATOR" in result
        assert "dispatch subagents" in result

    def test_identity_role_used_when_provided(self):
        """Section 0.6 uses the provided identity_role string."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(soul, identity_role="Red Team Lead")
        assert "### 0.6 Orchestrator Identity" in result
        assert "Red Team Lead" in result
        # The default role text should NOT appear
        assert "ORCHESTRATOR (Senior Software Architect)" not in result

    def test_default_orchestrator_role_when_no_identity(self):
        """Section 0.6 defaults to ORCHESTRATOR when identity_role is None."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(soul, identity_role=None)
        assert "ORCHESTRATOR (Senior Software Architect)" in result


class TestGenerateBootPromptWithSkillConstraints:
    """Tests for Section 0.7 skill constraints (T4)."""

    def test_skill_constraints_section(self):
        """Section 0.7 appears when skill_constraints is provided."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        constraints = {
            "forbidden": ["Writing code directly", "Skipping tests"],
            "required": ["Dispatch subagents", "Run tests first"],
        }
        result = generate_boot_prompt(soul, skill_constraints=constraints)
        assert "### 0.7 Active Skill Constraints" in result
        assert "FORBIDDEN" in result
        assert "Writing code directly" in result
        assert "Skipping tests" in result
        assert "REQUIRED" in result
        assert "Dispatch subagents" in result
        assert "Run tests first" in result

    def test_skill_constraints_absent_when_none(self):
        """Section 0.7 is absent when skill_constraints is None."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(soul, skill_constraints=None)
        assert "### 0.7" not in result

    def test_skill_constraints_absent_when_empty(self):
        """Section 0.7 is absent when skill_constraints has empty lists."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(
            soul, skill_constraints={"forbidden": [], "required": []}
        )
        assert "### 0.7" not in result

    def test_skill_constraints_caps_at_five_items(self):
        """Section 0.7 caps forbidden and required items at 5 each."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        constraints = {
            "forbidden": [f"Forbidden item {i}" for i in range(10)],
            "required": [f"Required item {i}" for i in range(10)],
        }
        result = generate_boot_prompt(soul, skill_constraints=constraints)
        # Should contain items 0-4 but not 5-9
        assert "Forbidden item 4" in result
        assert "Forbidden item 5" not in result
        assert "Required item 4" in result
        assert "Required item 5" not in result

    def test_skill_constraints_truncates_long_items(self):
        """Items longer than 150 chars are truncated."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        long_item = "x" * 200
        constraints = {
            "forbidden": [long_item],
            "required": [],
        }
        result = generate_boot_prompt(soul, skill_constraints=constraints)
        # The item should be truncated to 150 chars
        assert "x" * 150 in result
        assert "x" * 151 not in result


class TestGenerateBootPromptWithBindingDecisions:
    """Tests for Section 0.8 binding decisions (T4)."""

    def test_binding_decisions_section(self):
        """Section 0.8 appears when binding_decisions is provided."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        decisions = ["Use SQLite WAL mode", "Schema v2 migration"]
        result = generate_boot_prompt(soul, binding_decisions=decisions)
        assert "### 0.8 Binding Decisions" in result
        assert "DO NOT REVISIT" in result
        assert "SQLite WAL mode" in result
        assert "Schema v2 migration" in result

    def test_binding_decisions_absent_when_none(self):
        """Section 0.8 is absent when binding_decisions is None."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(soul, binding_decisions=None)
        assert "### 0.8" not in result

    def test_binding_decisions_absent_when_empty(self):
        """Section 0.8 is absent when binding_decisions is empty list."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        result = generate_boot_prompt(soul, binding_decisions=[])
        assert "### 0.8" not in result

    def test_binding_decisions_caps_at_five(self):
        """Section 0.8 caps decisions at 5."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill"}
        decisions = [f"Decision {i}" for i in range(10)]
        result = generate_boot_prompt(soul, binding_decisions=decisions)
        assert "Decision 4" in result
        assert "Decision 5" not in result


class TestGenerateBootPromptAllNewSections:
    """Tests for all new sections together (T4)."""

    def test_all_new_sections_present(self):
        """Verify all three new sections appear together."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "active_skill": "implementing-features",
            "skill_phase": "IMPLEMENT",
            "workflow_pattern": "TDD",
        }
        constraints = {
            "forbidden": ["Direct implementation"],
            "required": ["Subagent dispatch"],
        }
        decisions = ["Use approach X"]
        result = generate_boot_prompt(
            soul,
            skill_constraints=constraints,
            binding_decisions=decisions,
            identity_role="orchestrator",
        )
        assert "### 0.6 Orchestrator Identity" in result
        assert "### 0.7 Active Skill Constraints" in result
        assert "### 0.8 Binding Decisions" in result

    def test_section_ordering(self):
        """Sections appear in correct order: 0.5, 0.6, 0.7, 0.8."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {"active_skill": "test-skill", "workflow_pattern": "TDD"}
        constraints = {
            "forbidden": ["Bad thing"],
            "required": ["Good thing"],
        }
        decisions = ["Decision A"]
        result = generate_boot_prompt(
            soul,
            skill_constraints=constraints,
            binding_decisions=decisions,
            identity_role="orchestrator",
        )
        idx_05 = result.index("### 0.5")
        idx_06 = result.index("### 0.6")
        idx_07 = result.index("### 0.7")
        idx_08 = result.index("### 0.8")
        assert idx_05 < idx_06 < idx_07 < idx_08


class TestGenerateBootPromptNoNewSections:
    """Tests for backward compatibility when no new params passed (T4)."""

    def test_no_new_sections_except_identity(self):
        """When no new params passed, only 0.6 (always-on) is present."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "active_skill": "test-skill",
            "skill_phase": "IMPLEMENT",
            "todos": None,
            "recent_files": [],
            "workflow_pattern": "TDD",
        }
        result = generate_boot_prompt(soul)
        # 0.6 is always present (orchestrator identity)
        assert "### 0.6 Orchestrator Identity" in result
        # 0.7 and 0.8 should NOT be present
        assert "### 0.7" not in result
        assert "### 0.8" not in result

    def test_existing_sections_unchanged(self):
        """Existing sections 0.1-0.5 still present with no new params."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "active_skill": "test-skill",
            "skill_phase": "IMPLEMENT",
            "workflow_pattern": "TDD",
        }
        result = generate_boot_prompt(soul)
        assert "### 0.1 Workflow Restoration" in result
        assert "### 0.2 Required Document Reads" in result
        assert "### 0.3 Todo State Restoration" in result
        assert "### 0.4 Restoration Checkpoint" in result
        assert "### 0.5 Behavioral Constraints" in result


class TestBootPromptTokenBudget:
    """Tests for token budget trimming (T4)."""

    def test_token_budget_under_limit_normal_input(self):
        """Output stays under 8000 chars with reasonable input."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "active_skill": "implementing-features",
            "skill_phase": "IMPLEMENT",
            "todos": json.dumps([
                {"content": f"Task {i}", "status": "pending"}
                for i in range(10)
            ]),
            "recent_files": ["/path/to/plan.md"],
            "workflow_pattern": "TDD",
        }
        constraints = {
            "forbidden": [f"Forbidden item {i}" for i in range(5)],
            "required": [f"Required item {i}" for i in range(5)],
        }
        decisions = [f"Decision {i}: some rationale" for i in range(5)]
        result = generate_boot_prompt(soul, constraints, decisions)
        assert len(result) <= 8000

    def test_priority_trimming_removes_decisions_first(self):
        """When over budget, 0.8 (decisions) is trimmed before 0.7 (constraints)."""
        from spellbook_mcp.resume import generate_boot_prompt

        soul = {
            "active_skill": "test-skill",
            "todos": json.dumps([
                {"content": "x" * 200, "status": "pending"}
                for _ in range(10)
            ]),
        }
        # Large constraints and decisions to trigger trimming
        constraints = {
            "forbidden": ["x" * 150 for _ in range(5)],
            "required": ["x" * 150 for _ in range(5)],
        }
        decisions = ["x" * 200 for _ in range(5)]
        result = generate_boot_prompt(soul, constraints, decisions)
        assert len(result) <= 8000
        # If trimming happened, decisions should be gone before constraints
        if "### 0.7" not in result:
            assert "### 0.8" not in result  # 0.8 removed before 0.7


class TestBootPromptValidation:
    """Tests that enriched boot prompt passes validation (T4)."""

    def test_enriched_boot_prompt_passes_validation(self):
        """Enriched boot prompt passes _validate_boot_prompt()."""
        from spellbook_mcp.resume import generate_boot_prompt, _validate_boot_prompt

        soul = {"active_skill": "test-skill", "skill_phase": "IMPLEMENT"}
        constraints = {
            "forbidden": ["Direct implementation"],
            "required": ["Subagent dispatch"],
        }
        decisions = ["Use approach X"]
        result = generate_boot_prompt(
            soul,
            skill_constraints=constraints,
            binding_decisions=decisions,
            identity_role="orchestrator",
        )
        findings = _validate_boot_prompt(result)
        assert len(findings) == 0, f"Validation failures: {findings}"


class TestRemoveSection:
    """Tests for _remove_section helper (T4)."""

    def test_removes_target_section(self):
        """Removes the specified section and its content."""
        from spellbook_mcp.resume import _remove_section

        text = (
            "### 0.1 First\nContent 1\n"
            "### 0.2 Second\nContent 2\n"
            "### 0.3 Third\nContent 3"
        )
        result = _remove_section(text, "### 0.2")
        assert "### 0.2" not in result
        assert "Content 2" not in result
        assert "### 0.1" in result
        assert "Content 1" in result
        assert "### 0.3" in result
        assert "Content 3" in result

    def test_removes_last_section(self):
        """Removes the last section correctly (no following header)."""
        from spellbook_mcp.resume import _remove_section

        text = "### 0.1 First\nContent 1\n### 0.2 Last\nContent 2\nMore content"
        result = _remove_section(text, "### 0.2")
        assert "### 0.2" not in result
        assert "Content 2" not in result
        assert "### 0.1" in result

    def test_noop_when_section_not_found(self):
        """Returns text unchanged when section not found."""
        from spellbook_mcp.resume import _remove_section

        text = "### 0.1 First\nContent 1"
        result = _remove_section(text, "### 0.9")
        assert result == text


class TestGetResumeFieldsIncludesWorkflowState:
    """Tests for get_resume_fields() with workflow_state integration (T9)."""

    def _setup_db_with_soul(self, tmp_path, active_skill="implementing-features"):
        """Helper to create a DB with a recent soul record."""
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT INTO souls (id, session_id, project_path, bound_at, active_skill, skill_phase)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "soul-1",
            "session-1",
            "/test/project",
            datetime.now().isoformat(),
            active_skill,
            "IMPLEMENT",
        ))
        conn.commit()
        return str(db_path), conn

    def test_includes_skill_constraints_from_workflow_state(self, tmp_path):
        """Constraints from workflow_state are passed to boot prompt."""
        from spellbook_mcp.resume import get_resume_fields

        db_path, conn = self._setup_db_with_soul(tmp_path)

        # Insert workflow state with skill_constraints
        state = {
            "skill_constraints": {
                "forbidden": ["Writing code in main context"],
                "required": ["Dispatch subagents for all work"],
            },
            "decisions_binding": ["Use SQLite WAL mode"],
            "identity_role": "orchestrator",
        }
        conn.execute("""
            INSERT INTO workflow_state (project_path, state_json, trigger, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("/test/project", json.dumps(state), "auto"))
        conn.commit()

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_available"] is True
        assert "FORBIDDEN" in fields["resume_boot_prompt"]
        assert "Writing code in main context" in fields["resume_boot_prompt"]
        assert "REQUIRED" in fields["resume_boot_prompt"]
        assert "Dispatch subagents" in fields["resume_boot_prompt"]

    def test_includes_binding_decisions_from_workflow_state(self, tmp_path):
        """Binding decisions from workflow_state appear in boot prompt."""
        from spellbook_mcp.resume import get_resume_fields

        db_path, conn = self._setup_db_with_soul(tmp_path)

        state = {
            "decisions_binding": ["Use SQLite WAL mode", "Schema v2 migration"],
        }
        conn.execute("""
            INSERT INTO workflow_state (project_path, state_json, trigger, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("/test/project", json.dumps(state), "auto"))
        conn.commit()

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_available"] is True
        assert "Binding Decisions" in fields["resume_boot_prompt"]
        assert "DO NOT REVISIT" in fields["resume_boot_prompt"]
        assert "SQLite WAL mode" in fields["resume_boot_prompt"]
        assert "Schema v2 migration" in fields["resume_boot_prompt"]

    def test_includes_identity_role_from_workflow_state(self, tmp_path):
        """Identity role from workflow_state appears in boot prompt."""
        from spellbook_mcp.resume import get_resume_fields

        db_path, conn = self._setup_db_with_soul(tmp_path)

        state = {"identity_role": "Red Team Lead"}
        conn.execute("""
            INSERT INTO workflow_state (project_path, state_json, trigger, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("/test/project", json.dumps(state), "auto"))
        conn.commit()

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_available"] is True
        assert "Red Team Lead" in fields["resume_boot_prompt"]

    def test_resume_fields_include_new_keys(self, tmp_path):
        """ResumeFields dict includes the new workflow state keys."""
        from spellbook_mcp.resume import get_resume_fields

        db_path, conn = self._setup_db_with_soul(tmp_path)

        state = {
            "skill_constraints": {
                "forbidden": ["Bad thing"],
                "required": ["Good thing"],
            },
            "decisions_binding": ["Decision A"],
            "identity_role": "orchestrator",
        }
        conn.execute("""
            INSERT INTO workflow_state (project_path, state_json, trigger, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("/test/project", json.dumps(state), "auto"))
        conn.commit()

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_skill_constraints"] == state["skill_constraints"]
        assert fields["resume_decisions_binding"] == state["decisions_binding"]
        assert fields["resume_identity_role"] == "orchestrator"

    def test_backward_compatible_no_workflow_state(self, tmp_path):
        """Existing behavior preserved when no workflow_state exists."""
        from spellbook_mcp.resume import get_resume_fields

        # Use a nonexistent skill so the skill file fallback produces nothing
        db_path, conn = self._setup_db_with_soul(
            tmp_path, active_skill="nonexistent-skill-xyz"
        )
        # No workflow_state row inserted

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_available"] is True
        assert "SECTION 0" in fields["resume_boot_prompt"]
        # Orchestrator identity is always present (new section 0.6)
        assert "ORCHESTRATOR" in fields["resume_boot_prompt"]
        # No skill constraints or binding decisions sections (no workflow state, no skill file)
        assert "### 0.7" not in fields["resume_boot_prompt"]
        assert "### 0.8" not in fields["resume_boot_prompt"]

    def test_orchestrator_identity_always_in_boot_prompt(self, tmp_path):
        """Orchestrator identity (Section 0.6) is always present even without workflow state."""
        from spellbook_mcp.resume import get_resume_fields

        db_path, conn = self._setup_db_with_soul(tmp_path)

        fields = get_resume_fields("/test/project", db_path)
        assert "Orchestrator Identity" in fields["resume_boot_prompt"]
        assert "dispatch subagents" in fields["resume_boot_prompt"]

    def test_falls_back_to_skill_file_when_no_workflow_constraints(self, tmp_path, monkeypatch):
        """When workflow_state has no constraints, falls back to skill file."""
        from spellbook_mcp.resume import get_resume_fields

        # Create a soul with an active skill
        db_path, conn = self._setup_db_with_soul(tmp_path, active_skill="test-skill")

        # Insert workflow state WITHOUT skill_constraints
        state = {"decisions_binding": ["Some decision"]}
        conn.execute("""
            INSERT INTO workflow_state (project_path, state_json, trigger, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, ("/test/project", json.dumps(state), "auto"))
        conn.commit()

        # Create a mock skill file
        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "<FORBIDDEN>\n- No direct implementation\n</FORBIDDEN>\n"
            "<REQUIRED>\n- Dispatch subagents\n</REQUIRED>\n"
        )
        monkeypatch.setattr(
            "spellbook_mcp.resume._get_spellbook_dir",
            lambda: tmp_path,
        )

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_available"] is True
        # Constraints from skill file should appear in boot prompt
        assert "No direct implementation" in fields["resume_boot_prompt"]
        assert "Dispatch subagents" in fields["resume_boot_prompt"]

    def test_new_fields_none_when_no_workflow_state(self, tmp_path):
        """New resume fields are None when no workflow_state exists."""
        from spellbook_mcp.resume import get_resume_fields

        # Use a skill that doesn't have FORBIDDEN/REQUIRED sections
        db_path, conn = self._setup_db_with_soul(
            tmp_path, active_skill="nonexistent-skill-xyz"
        )

        fields = get_resume_fields("/test/project", db_path)
        assert fields["resume_available"] is True
        assert fields.get("resume_skill_constraints") is None
        assert fields.get("resume_decisions_binding") is None
        assert fields.get("resume_identity_role") is None
