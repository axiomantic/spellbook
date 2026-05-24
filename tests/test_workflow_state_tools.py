"""Tests for workflow state MCP tools.

Tests cover:
- workflow_state_save: Persist state to database
- workflow_state_load: Retrieve state with staleness check
- workflow_state_update: Incremental deep-merge updates
- skill_instructions_get: Extract skill sections
- _deep_merge: Helper function for nested merging

Note: The MCP tools are decorated with @mcp.tool() which wraps them in FunctionTool
objects. We access the underlying function via the .fn attribute.
"""

import json
import tripwire
import pytest
from datetime import datetime, timedelta, timezone

from spellbook.core.db import init_db, get_connection, close_all_connections


def _setup_get_connection_mock(db_path, call_count):
    """Set up a tripwire mock for get_connection returning a test DB connection.

    Returns (mock, conn). After the `with tripwire:` block, caller must assert
    call_count times via _assert_get_connection_calls().
    """
    mock = tripwire.mock("spellbook.core.db:get_connection")
    conn = get_connection(db_path)
    for _ in range(call_count):
        mock.returns(conn)
    return mock, conn


def _assert_get_connection_calls(mock, call_count):
    """Assert that get_connection was called call_count times."""
    with tripwire.in_any_order():
        for _ in range(call_count):
            mock.assert_call(args=(), kwargs={})


class TestWorkflowStateSave:
    """Tests for workflow_state_save tool."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.db_path = str(tmp_path / "test.db")
        init_db(self.db_path)
        yield
        close_all_connections()

    def test_save_creates_new_record(self, tmp_path):
        """Test saving state creates new record."""
        from spellbook.server import workflow_state_save

        project_path = "/test/project"
        state = {
            "active_skill": "develop",
            "todos": [{"id": "1", "text": "Task 1", "status": "pending"}],
        }

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 1)

        with tripwire:
            result = workflow_state_save.fn(
                project_path=project_path,
                state=state,
                trigger="manual",
            )

        _assert_get_connection_calls(mock_conn, 1)
        assert result["success"] is True
        assert result["project_path"] == project_path
        assert result["trigger"] == "manual"

        # Verify in database
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state_json, trigger FROM workflow_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        assert row is not None
        loaded_state = json.loads(row[0])
        assert loaded_state["active_skill"] == "develop"
        assert row[1] == "manual"

    def test_save_updates_existing_record(self, tmp_path):
        """Test saving state updates existing record for same project."""
        from spellbook.server import workflow_state_save

        project_path = "/test/project"

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 2)

        with tripwire:
            # First save
            state1 = {"active_skill": "debugging"}
            workflow_state_save.fn(project_path=project_path, state=state1, trigger="manual")

            # Second save (update)
            state2 = {"active_skill": "develop"}
            result = workflow_state_save.fn(project_path=project_path, state=state2, trigger="auto")

        _assert_get_connection_calls(mock_conn, 2)
        assert result["success"] is True

        # Verify only one record and it has the updated state
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), state_json, trigger FROM workflow_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        assert row[0] == 1  # Only one record
        loaded_state = json.loads(row[1])
        assert loaded_state["active_skill"] == "develop"
        assert row[2] == "auto"  # Trigger updated

    def test_save_with_different_triggers(self, tmp_path):
        """Test saving with manual, auto, checkpoint triggers."""
        from spellbook.server import workflow_state_save

        triggers = ["manual", "auto", "checkpoint"]

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            for i, trigger in enumerate(triggers):
                project_path = f"/test/project-{i}"
                state = {"workflow_pattern": trigger}
                result = workflow_state_save.fn(
                    project_path=project_path, state=state, trigger=trigger
                )
                assert result["success"] is True
                assert result["trigger"] == trigger

        _assert_get_connection_calls(mock_conn, 3)

        # Verify all triggers stored correctly
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT project_path, trigger FROM workflow_state ORDER BY project_path")
        rows = cursor.fetchall()
        assert len(rows) == 3
        for i, (path, trigger) in enumerate(rows):
            assert path == f"/test/project-{i}"
            assert trigger == triggers[i]

    def test_save_preserves_created_at_on_update(self, tmp_path):
        """Test that created_at is preserved when updating."""
        from spellbook.server import workflow_state_save
        import time

        project_path = "/test/project"

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 2)

        with tripwire:
            # First save
            workflow_state_save.fn(
                project_path=project_path,
                state={"pending_todos": 1},
                trigger="manual",
            )

            # Get created_at
            conn_check = get_connection(self.db_path)
            cursor = conn_check.cursor()
            cursor.execute(
                "SELECT created_at FROM workflow_state WHERE project_path = ?",
                (project_path,),
            )
            created_at_1 = cursor.fetchone()[0]

            # Small delay to ensure timestamps differ
            time.sleep(0.1)

            # Second save (update)
            workflow_state_save.fn(
                project_path=project_path,
                state={"pending_todos": 2},
                trigger="auto",
            )

            # Get timestamps after update
            cursor.execute(
                "SELECT created_at, updated_at FROM workflow_state WHERE project_path = ?",
                (project_path,),
            )
            row = cursor.fetchone()
            created_at_2 = row[0]
            updated_at_2 = row[1]

        _assert_get_connection_calls(mock_conn, 2)

        # created_at should be preserved, updated_at should be newer
        assert created_at_1 == created_at_2
        assert updated_at_2 >= created_at_2

    def test_save_handles_complex_state(self, tmp_path):
        """Test saving complex nested state structures."""
        from spellbook.server import workflow_state_save

        project_path = "/test/project"
        state = {
            "active_skill": "develop",
            "todos": [
                {"id": "1", "text": "Task 1", "status": "completed"},
                {"id": "2", "text": "Task 2", "status": "pending"},
            ],
            "recent_files": ["src/main.py", "tests/test_main.py"],
            "skill_constraints": {
                "forbidden": ["skip tests"],
                "required": ["run linter"],
            },
        }

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 1)

        with tripwire:
            result = workflow_state_save.fn(
                project_path=project_path, state=state, trigger="checkpoint"
            )

        _assert_get_connection_calls(mock_conn, 1)
        assert result["success"] is True

        # Verify complex state stored correctly
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state_json FROM workflow_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        loaded_state = json.loads(row[0])
        assert loaded_state == state


class TestWorkflowStateLoad:
    """Tests for workflow_state_load tool."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.db_path = str(tmp_path / "test.db")
        init_db(self.db_path)
        yield
        close_all_connections()

    def test_load_returns_not_found_for_missing_project(self, tmp_path):
        """Test loading returns found=False for missing project."""
        from spellbook.server import workflow_state_load

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 1)

        with tripwire:
            result = workflow_state_load.fn(project_path="/nonexistent/project")

        _assert_get_connection_calls(mock_conn, 1)
        assert result["success"] is True
        assert result["found"] is False
        assert result["state"] is None
        assert result["age_hours"] is None
        assert result["trigger"] is None

    def test_load_returns_state_for_existing_project(self, tmp_path):
        """Test loading returns state for existing project."""
        from spellbook.server import workflow_state_save, workflow_state_load

        project_path = "/test/project"
        state = {"active_skill": "debugging", "todos": []}

        mock_conn, conn = _setup_get_connection_mock(self.db_path, 2)

        with tripwire:
            # Save state
            workflow_state_save.fn(project_path=project_path, state=state, trigger="manual")

            # Load state
            result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 2)
        assert result["success"] is True
        assert result["found"] is True
        assert result["state"] == state
        assert result["trigger"] == "manual"
        assert result["age_hours"] is not None
        assert result["age_hours"] < 1.0  # Just saved, should be very recent

    def test_load_respects_max_age_hours(self, tmp_path):
        """Test loading returns found=False for stale state."""
        from spellbook.server import workflow_state_load

        project_path = "/test/project"

        # Insert state with old timestamp directly
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        cursor.execute(
            """
            INSERT INTO workflow_state (project_path, state_json, trigger, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_path, '{"active_skill": "debugging"}', "manual", old_time, old_time),
        )
        conn.commit()

        mock_gc = tripwire.mock("spellbook.core.db:get_connection")
        mock_gc.returns(conn)

        with tripwire:
            # Load with default max_age_hours (24)
            result = workflow_state_load.fn(project_path=project_path, max_age_hours=24.0)

        _assert_get_connection_calls(mock_gc, 1)
        assert result["success"] is True
        assert result["found"] is False  # Too old
        assert result["state"] is None
        assert result["age_hours"] is not None
        assert result["age_hours"] > 24.0
        assert result["trigger"] == "manual"

    def test_load_accepts_fresh_state_within_max_age(self, tmp_path):
        """Test loading accepts state within max_age_hours."""
        from spellbook.server import workflow_state_load

        project_path = "/test/project"

        # Insert state with timestamp 2 hours ago
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        cursor.execute(
            """
            INSERT INTO workflow_state (project_path, state_json, trigger, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_path, '{"skill_phase": "discovery"}', "auto", recent_time, recent_time),
        )
        conn.commit()

        mock_gc = tripwire.mock("spellbook.core.db:get_connection")
        mock_gc.returns(conn)

        with tripwire:
            # Load with 24 hour max age
            result = workflow_state_load.fn(project_path=project_path, max_age_hours=24.0)

        _assert_get_connection_calls(mock_gc, 1)
        assert result["success"] is True
        assert result["found"] is True
        assert result["state"] == {"skill_phase": "discovery"}
        assert 1.5 < result["age_hours"] < 3.0  # Approximately 2 hours

    def test_load_returns_age_hours(self, tmp_path):
        """Test loading returns correct age_hours."""
        from spellbook.server import workflow_state_load

        project_path = "/test/project"

        # Insert state with timestamp 5 hours ago
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        five_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        cursor.execute(
            """
            INSERT INTO workflow_state (project_path, state_json, trigger, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_path,
                '{"active_skill": "debugging"}',
                "checkpoint",
                five_hours_ago,
                five_hours_ago,
            ),
        )
        conn.commit()

        mock_gc = tripwire.mock("spellbook.core.db:get_connection")
        mock_gc.returns(conn)

        with tripwire:
            result = workflow_state_load.fn(project_path=project_path, max_age_hours=24.0)

        _assert_get_connection_calls(mock_gc, 1)
        assert result["success"] is True
        assert result["found"] is True
        # Allow some margin for test execution time
        assert 4.5 < result["age_hours"] < 5.5

    def test_load_with_custom_max_age(self, tmp_path):
        """Test loading with custom max_age_hours parameter."""
        from spellbook.server import workflow_state_load

        project_path = "/test/project"

        # Insert state with timestamp 3 hours ago
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        three_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        cursor.execute(
            """
            INSERT INTO workflow_state (project_path, state_json, trigger, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_path, '{"active_skill": "tdd"}', "manual", three_hours_ago, three_hours_ago),
        )
        conn.commit()

        mock_gc = tripwire.mock("spellbook.core.db:get_connection")
        mock_gc.returns(conn)
        mock_gc.returns(conn)

        with tripwire:
            # With max_age=2 hours, should be stale
            result_stale = workflow_state_load.fn(project_path=project_path, max_age_hours=2.0)
            assert result_stale["found"] is False

            # With max_age=4 hours, should be fresh
            result_fresh = workflow_state_load.fn(project_path=project_path, max_age_hours=4.0)
            assert result_fresh["found"] is True

        _assert_get_connection_calls(mock_gc, 2)


class TestWorkflowStateUpdate:
    """Tests for workflow_state_update tool."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.db_path = str(tmp_path / "test.db")
        init_db(self.db_path)
        yield
        close_all_connections()

    def test_update_creates_state_if_not_exists(self, tmp_path):
        """Test update creates new state if none exists."""
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"
        updates = {"active_skill": "debugging", "skill_phase": "discovery"}

        # update(1) + load(1) = 2
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 2)

        with tripwire:
            result = workflow_state_update.fn(project_path=project_path, updates=updates)
            assert result["success"] is True

            # Verify state was created
            load_result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 2)
        assert load_result["found"] is True
        assert load_result["state"]["active_skill"] == "debugging"
        assert load_result["state"]["skill_phase"] == "discovery"

    def test_update_merges_nested_dicts(self, tmp_path):
        """Test update deep-merges nested dictionaries."""
        from spellbook.server import workflow_state_save, workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # save(1) + update(1) + load(1) = 3
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            # Initial state with nested dict
            initial_state = {
                "skill_constraints": {
                    "forbidden": ["skip tests"],
                    "required": ["run linter"],
                }
            }
            workflow_state_save.fn(project_path=project_path, state=initial_state, trigger="manual")

            # Update with partial nested dict
            updates = {
                "skill_constraints": {
                    "forbidden": ["skip reviews"],  # List - will be appended
                    "optional": "new_value",  # New key - will be added
                }
            }
            workflow_state_update.fn(project_path=project_path, updates=updates)

            # Load and verify merge
            result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert result["found"] is True
        constraints = result["state"]["skill_constraints"]
        # Lists are appended
        assert constraints["forbidden"] == ["skip tests", "skip reviews"]
        # Original keys preserved
        assert constraints["required"] == ["run linter"]
        # New keys added
        assert constraints["optional"] == "new_value"

    def test_update_appends_to_lists(self, tmp_path):
        """Test update appends to lists."""
        from spellbook.server import workflow_state_save, workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # save(1) + update(1) + load(1) = 3
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            # Initial state with lists
            initial_state = {
                "recent_files": ["src/main.py"],
                "todos": [{"id": "1", "text": "research", "status": "pending"}],
            }
            workflow_state_save.fn(project_path=project_path, state=initial_state, trigger="manual")

            # Update with additional list items
            updates = {
                "recent_files": ["tests/test_main.py"],  # Should be appended
                "todos": [{"id": "2", "text": "review", "status": "pending"}],  # Should be appended
            }
            workflow_state_update.fn(project_path=project_path, updates=updates)

            result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert result["found"] is True
        assert result["state"]["recent_files"] == ["src/main.py", "tests/test_main.py"]
        assert len(result["state"]["todos"]) == 2
        assert result["state"]["todos"][0]["id"] == "1"
        assert result["state"]["todos"][1]["id"] == "2"

    def test_update_overwrites_scalars(self, tmp_path):
        """Test update overwrites scalar values."""
        from spellbook.server import workflow_state_save, workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # save(1) + update(1) + load(1) = 3
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            # Initial state with scalars
            initial_state = {
                "active_skill": "debugging",
                "skill_phase": "discovery",
                "pending_todos": 1,
            }
            workflow_state_save.fn(project_path=project_path, state=initial_state, trigger="manual")

            # Update scalars
            updates = {
                "active_skill": "tdd",
                "skill_phase": "implementation",
                "pending_todos": 2,
            }
            workflow_state_update.fn(project_path=project_path, updates=updates)

            result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert result["found"] is True
        assert result["state"]["active_skill"] == "tdd"
        assert result["state"]["skill_phase"] == "implementation"
        assert result["state"]["pending_todos"] == 2

    def test_update_sets_auto_trigger(self, tmp_path):
        """Test that update always sets trigger to 'auto'."""
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # update(1) + load(1) = 2
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 2)

        with tripwire:
            workflow_state_update.fn(
                project_path=project_path, updates={"active_skill": "debugging"}
            )
            result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 2)
        assert result["trigger"] == "auto"

    def test_update_multiple_times(self, tmp_path):
        """Test multiple sequential updates accumulate correctly."""
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # 3 updates(3) + load(1) = 4
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 4)

        with tripwire:
            # First update
            workflow_state_update.fn(
                project_path=project_path,
                updates={"recent_files": ["file1.py"], "pending_todos": 1},
            )

            # Second update
            workflow_state_update.fn(
                project_path=project_path,
                updates={"recent_files": ["file2.py"], "workflow_pattern": "TDD"},
            )

            # Third update
            workflow_state_update.fn(
                project_path=project_path,
                updates={"recent_files": ["file3.py"], "pending_todos": 2},
            )

            result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 4)
        assert result["found"] is True
        assert result["state"]["recent_files"] == ["file1.py", "file2.py", "file3.py"]
        assert result["state"]["pending_todos"] == 2  # Overwritten
        assert result["state"]["workflow_pattern"] == "TDD"  # Preserved


class TestSkillInstructionsGet:
    """Tests for skill_instructions_get tool."""

    @pytest.fixture
    def mock_spellbook_dir(self, tmp_path):
        """Create a mock spellbook directory with test skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create a test skill with various section formats
        test_skill_dir = skills_dir / "test-skill"
        test_skill_dir.mkdir()
        skill_content = """---
name: test-skill
description: A test skill for unit tests
---

<ROLE>
You are a test role for validating skill extraction.
</ROLE>

<FORBIDDEN>
- Never do thing A
- Never do thing B
</FORBIDDEN>

<CRITICAL>
This is critical information that must be followed.
</CRITICAL>

## Required Practices

1. Do thing X
2. Do thing Y

## Edge Cases

Handle these edge cases carefully:
- Edge case 1
- Edge case 2
"""
        (test_skill_dir / "SKILL.md").write_text(skill_content)

        # Create another skill for testing
        another_skill_dir = skills_dir / "another-skill"
        another_skill_dir.mkdir()
        another_content = """---
name: another-skill
description: Another test skill
---

## Overview

This skill handles specific tasks.

## Required

Follow these requirements.
"""
        (another_skill_dir / "SKILL.md").write_text(another_content)

        return tmp_path

    def test_get_full_content_no_sections(self, mock_spellbook_dir):
        """Test getting full skill content without section filter."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(skill_name="test-skill")

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is True
        assert result["skill_name"] == "test-skill"
        assert "ROLE" in result["content"]
        assert "FORBIDDEN" in result["content"]
        assert "Required Practices" in result["content"]
        assert "sections" not in result  # No sections key when not filtering

    def test_get_specific_sections(self, mock_spellbook_dir):
        """Test extracting specific sections (FORBIDDEN, ROLE)."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["FORBIDDEN", "ROLE"],
            )

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is True
        assert "sections" in result
        assert "FORBIDDEN" in result["sections"]
        assert "Never do thing A" in result["sections"]["FORBIDDEN"]
        assert "ROLE" in result["sections"]
        assert "test role" in result["sections"]["ROLE"]

    def test_returns_error_for_missing_skill(self, mock_spellbook_dir):
        """Test returns error for non-existent skill."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(skill_name="nonexistent-skill")

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_extracts_xml_style_sections(self, mock_spellbook_dir):
        """Test extracting <FORBIDDEN>...</FORBIDDEN> style sections."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["CRITICAL"],
            )

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is True
        assert "CRITICAL" in result["sections"]
        assert "critical information" in result["sections"]["CRITICAL"].lower()

    def test_extracts_markdown_style_sections(self, mock_spellbook_dir):
        """Test extracting ## Section Name style sections."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["Required Practices"],
            )

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is True
        assert "Required Practices" in result["sections"]
        assert "thing X" in result["sections"]["Required Practices"]

    def test_handles_missing_sections_gracefully(self, mock_spellbook_dir):
        """Test that missing sections are simply not included."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["ROLE", "NONEXISTENT_SECTION"],
            )

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is True
        assert "ROLE" in result["sections"]
        assert "NONEXISTENT_SECTION" not in result["sections"]

    def test_combined_content_from_sections(self, mock_spellbook_dir):
        """Test that content field contains combined sections."""
        from spellbook.server import skill_instructions_get

        mock_dir = tripwire.mock("spellbook.mcp.tools.forged:get_spellbook_dir")
        mock_dir.returns(mock_spellbook_dir)

        with tripwire:
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["ROLE", "FORBIDDEN"],
            )

        mock_dir.assert_call(args=(), kwargs={})
        assert result["success"] is True
        # Content should contain formatted sections
        assert "## ROLE" in result["content"] or "## FORBIDDEN" in result["content"]


class TestDeepMerge:
    """Tests for the _deep_merge helper function."""

    def test_merge_flat_dicts(self):
        """Test merging flat dictionaries."""
        from spellbook.server import _deep_merge

        base = {"a": 1, "b": 2}
        updates = {"b": 3, "c": 4}
        result = _deep_merge(base, updates)

        assert result == {"a": 1, "b": 3, "c": 4}
        # Original should be unchanged
        assert base == {"a": 1, "b": 2}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        from spellbook.server import _deep_merge

        base = {
            "outer": {
                "inner1": "value1",
                "inner2": "value2",
            }
        }
        updates = {
            "outer": {
                "inner2": "updated",
                "inner3": "value3",
            }
        }
        result = _deep_merge(base, updates)

        assert result["outer"]["inner1"] == "value1"  # Preserved
        assert result["outer"]["inner2"] == "updated"  # Updated
        assert result["outer"]["inner3"] == "value3"  # Added

    def test_merge_appends_lists(self):
        """Test merging appends lists."""
        from spellbook.server import _deep_merge

        base = {"items": [1, 2, 3]}
        updates = {"items": [4, 5]}
        result = _deep_merge(base, updates)

        assert result["items"] == [1, 2, 3, 4, 5]

    def test_merge_overwrites_non_dict_non_list(self):
        """Test merging overwrites scalar values."""
        from spellbook.server import _deep_merge

        base = {"count": 1, "name": "old", "active": False}
        updates = {"count": 2, "name": "new", "active": True}
        result = _deep_merge(base, updates)

        assert result["count"] == 2
        assert result["name"] == "new"
        assert result["active"] is True

    def test_merge_handles_type_mismatch(self):
        """Test merging handles type mismatches (update wins)."""
        from spellbook.server import _deep_merge

        # Dict replaced by scalar
        base = {"config": {"nested": "value"}}
        updates = {"config": "simple"}
        result = _deep_merge(base, updates)
        assert result["config"] == "simple"

        # Scalar replaced by dict
        base = {"config": "simple"}
        updates = {"config": {"nested": "value"}}
        result = _deep_merge(base, updates)
        assert result["config"] == {"nested": "value"}

    def test_merge_deeply_nested(self):
        """Test merging deeply nested structures."""
        from spellbook.server import _deep_merge

        base = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "original",
                        "keep": "preserved",
                    }
                }
            }
        }
        updates = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "updated",
                        "new": "added",
                    }
                }
            }
        }
        result = _deep_merge(base, updates)

        assert result["level1"]["level2"]["level3"]["value"] == "updated"
        assert result["level1"]["level2"]["level3"]["keep"] == "preserved"
        assert result["level1"]["level2"]["level3"]["new"] == "added"

    def test_merge_empty_dicts(self):
        """Test merging with empty dictionaries."""
        from spellbook.server import _deep_merge

        # Empty base
        result1 = _deep_merge({}, {"a": 1})
        assert result1 == {"a": 1}

        # Empty updates
        result2 = _deep_merge({"a": 1}, {})
        assert result2 == {"a": 1}

        # Both empty
        result3 = _deep_merge({}, {})
        assert result3 == {}

    def test_merge_empty_lists(self):
        """Test merging with empty lists."""
        from spellbook.server import _deep_merge

        # Empty base list
        result1 = _deep_merge({"items": []}, {"items": [1, 2]})
        assert result1["items"] == [1, 2]

        # Empty update list
        result2 = _deep_merge({"items": [1, 2]}, {"items": []})
        assert result2["items"] == [1, 2]


class TestExtractSection:
    """Tests for the _extract_section helper function."""

    def test_extract_xml_section(self):
        """Test extracting XML-style sections."""
        from spellbook.server import _extract_section

        content = """
Some text before.

<ROLE>
You are a test role.
Multiple lines here.
</ROLE>

Some text after.
"""
        result = _extract_section(content, "ROLE")
        assert result is not None
        assert "test role" in result
        assert "Multiple lines" in result

    def test_extract_xml_section_case_insensitive(self):
        """Test XML section extraction is case-insensitive."""
        from spellbook.server import _extract_section

        content = "<FORBIDDEN>content</FORBIDDEN>"
        result = _extract_section(content, "forbidden")
        assert result == "content"

    def test_extract_markdown_section(self):
        """Test extracting markdown-style sections."""
        from spellbook.server import _extract_section

        content = """
## Overview

This is the overview section.

## Implementation

This is the implementation section.

## Testing

This is the testing section.
"""
        result = _extract_section(content, "Implementation")
        assert result is not None
        assert "implementation section" in result.lower()
        # Should not contain next section
        assert "testing section" not in result.lower()

    def test_extract_returns_none_for_missing(self):
        """Test that missing sections return None."""
        from spellbook.server import _extract_section

        content = "<ROLE>content</ROLE>"
        result = _extract_section(content, "MISSING")
        assert result is None

    def test_extract_prefers_xml_over_markdown(self):
        """Test that XML-style is tried before markdown."""
        from spellbook.server import _extract_section

        content = """
<ROLE>
XML role content
</ROLE>

## ROLE

Markdown role content
"""
        result = _extract_section(content, "ROLE")
        assert "XML role content" in result


class TestWorkflowStateIntegration:
    """Integration tests for workflow state tools working together."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.db_path = str(tmp_path / "test.db")
        init_db(self.db_path)
        yield
        close_all_connections()

    def test_full_lifecycle_save_update_load(self, tmp_path):
        """Test complete workflow state lifecycle."""
        from spellbook.server import (
            workflow_state_save,
            workflow_state_update,
            workflow_state_load,
        )

        project_path = "/test/project"

        # save(1) + 3 updates(3) + load(1) = 5
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 5)

        with tripwire:
            # 1. Initial save (session start)
            initial_state = {
                "recent_files": [],
                "todos": [],
                "active_skill": None,
            }
            save_result = workflow_state_save.fn(
                project_path=project_path,
                state=initial_state,
                trigger="manual",
            )
            assert save_result["success"] is True

            # 2. Update (skill invocation)
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "recent_files": ["src/main.py"],
                    "active_skill": "develop",
                },
            )

            # 3. Update (todo added)
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "todos": [{"id": "1", "text": "Research", "status": "pending"}],
                },
            )

            # 4. Update (nested skill)
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "recent_files": ["tests/test_main.py"],
                    "active_skill": "tdd",
                },
            )

            # 5. Load and verify accumulated state
            load_result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 5)

        assert load_result["success"] is True
        assert load_result["found"] is True
        state = load_result["state"]

        # Recent files accumulated
        assert state["recent_files"] == ["src/main.py", "tests/test_main.py"]
        # Active skill updated
        assert state["active_skill"] == "tdd"
        # Todos accumulated
        assert len(state["todos"]) == 1

    def test_multiple_projects_isolated(self, tmp_path):
        """Test that different projects have isolated state."""
        from spellbook.server import (
            workflow_state_save,
            workflow_state_load,
        )

        # 2 saves + 2 loads = 4
        mock_conn, conn = _setup_get_connection_mock(self.db_path, 4)

        with tripwire:
            # Save state for project A
            workflow_state_save.fn(
                project_path="/project/a",
                state={"active_skill": "debugging", "pending_todos": 1},
                trigger="manual",
            )

            # Save state for project B
            workflow_state_save.fn(
                project_path="/project/b",
                state={"active_skill": "tdd", "pending_todos": 2},
                trigger="manual",
            )

            # Load each and verify isolation
            result_a = workflow_state_load.fn(project_path="/project/a")
            result_b = workflow_state_load.fn(project_path="/project/b")

        _assert_get_connection_calls(mock_conn, 4)

        assert result_a["state"]["active_skill"] == "debugging"
        assert result_a["state"]["pending_todos"] == 1
        assert result_b["state"]["active_skill"] == "tdd"
        assert result_b["state"]["pending_todos"] == 2


class TestAllowlistCompactAndLedgerKeys:
    """Tests for Task 1: stint_stack, compaction_flag, develop_gate_ledger
    added to _ALLOWED_STATE_KEYS so the compact machinery and develop's gate
    ledger survive validate_workflow_state.
    """

    def test_allowlist_accepts_compact_and_ledger_keys(self):
        """A state carrying all three new keys validates clean (no findings)."""
        from spellbook.sessions.resume import validate_workflow_state

        state = {
            "active_skill": "develop",
            "stint_stack": [{"label": "x", "started_at": "2026-05-24T00:00:00Z"}],
            "compaction_flag": True,
            "develop_gate_ledger": {
                "current_phase": "2",
                "need_flags": {
                    "needs_research": True,
                    "needs_design": True,
                    "needs_infrastructure": False,
                },
                "remaining_gates": "design review\ncode review",
                "plan_pointer": "/tmp/p.md",
            },
        }

        result = validate_workflow_state(state)

        assert result == {"valid": True, "state": state, "findings": []}

    def test_genuinely_unknown_key_still_rejected(self):
        """Behavior preservation: a key outside the allowlist still fails with
        the exact HIGH unexpected-keys finding (Task 1 acceptance criterion 2).
        """
        from spellbook.sessions.resume import validate_workflow_state

        state = {"foo": 1}

        result = validate_workflow_state(state)

        assert result == {
            "valid": False,
            "state": None,
            "findings": [
                {
                    "check": "schema",
                    "message": "Unexpected keys in workflow state: ['foo']",
                    "severity": "HIGH",
                }
            ],
        }


class TestCompactRoundTrip:
    """Tasks 2 & 3: real-DB compact round-trip, gate-ledger merge, replace-not-append
    (CRIT-1), and atomic interleaved read-merge-write (CRIT-2).

    Every test runs against a REAL temp SQLite DB via get_connection(self.db_path).
    NO _mcp_call mocking, NO DB mocking — these tests exist precisely because the
    old compaction tests ran against a dead port and never exercised the real path.
    """

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.db_path = str(tmp_path / "test.db")
        init_db(self.db_path)
        yield
        close_all_connections()

    # ---- PreCompact-shape survival + save/load round-trip -------------------

    def test_precompact_state_shape_survives_validation(self):
        """The exact dict _handle_pre_compact produces validates clean post-Task-1.

        Before Task 1 this returned valid=False naming stint_stack/compaction_flag
        as unexpected keys (the pre-existing-bug witness). After the allowlist fix
        it validates clean with no findings.
        """
        from spellbook.sessions.resume import validate_workflow_state

        state = {
            "active_skill": "develop",
            "skill_phase": "2",
            "develop_gate_ledger": {
                "current_phase": "2",
                "need_flags": {
                    "needs_research": True,
                    "needs_design": True,
                    "needs_infrastructure": False,
                },
                "remaining_gates": "design review\ncode review\ntest suite",
                "plan_pointer": "/tmp/plan.md",
            },
            "stint_stack": [{"label": "implement feature", "started_at": "2026-05-24T00:00:00Z"}],
            "compaction_flag": True,
        }

        result = validate_workflow_state(state)

        assert result == {"valid": True, "state": state, "findings": []}

    def test_workflow_state_save_load_roundtrip_with_compact_keys(self):
        """save the PreCompact-shaped dict, then load returns it byte-for-byte."""
        from spellbook.server import workflow_state_save, workflow_state_load

        project_path = "/test/project"
        state = {
            "active_skill": "develop",
            "skill_phase": "3",
            "develop_gate_ledger": {
                "current_phase": "3",
                "need_flags": {
                    "needs_research": False,
                    "needs_design": True,
                    "needs_infrastructure": False,
                },
                "remaining_gates": "code review\ntest suite",
                "plan_pointer": "/tmp/plan.md",
            },
            "stint_stack": [{"label": "build", "started_at": "2026-05-24T01:00:00Z"}],
            "compaction_flag": True,
        }

        # save(1) + load(1) = 2
        mock_conn, _ = _setup_get_connection_mock(self.db_path, 2)

        with tripwire:
            save_result = workflow_state_save.fn(
                project_path=project_path, state=state, trigger="auto"
            )
            load_result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 2)
        assert save_result == {
            "success": True,
            "project_path": project_path,
            "trigger": "auto",
        }
        assert load_result["success"] is True
        assert load_result["found"] is True
        assert load_result["state"] == state

    def test_workflow_state_update_merges_gate_ledger(self):
        """First update seeds the ledger; second update advances the phase and
        replaces remaining_gates. The merged ledger holds the second update's
        scalars while preserving need_flags written first.
        """
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # update(1) + update(1) + load(1) = 3
        mock_conn, _ = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            first = workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "active_skill": "develop",
                    "skill_phase": "2",
                    "develop_gate_ledger": {
                        "current_phase": "2",
                        "need_flags": {
                            "needs_research": False,
                            "needs_design": True,
                            "needs_infrastructure": False,
                        },
                        "remaining_gates": "design review\ncode review\ntest suite",
                        "plan_pointer": "/tmp/plan.md",
                    },
                },
            )
            second = workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "skill_phase": "3",
                    "develop_gate_ledger": {
                        "current_phase": "3",
                        "remaining_gates": "code review\ntest suite",
                    },
                },
            )
            load_result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert first == {"success": True, "project_path": project_path}
        assert second == {"success": True, "project_path": project_path}
        assert load_result["found"] is True
        assert load_result["state"] == {
            "active_skill": "develop",
            "skill_phase": "3",
            "develop_gate_ledger": {
                "current_phase": "3",
                "need_flags": {
                    "needs_research": False,
                    "needs_design": True,
                    "needs_infrastructure": False,
                },
                "remaining_gates": "code review\ntest suite",
                "plan_pointer": "/tmp/plan.md",
            },
        }

    # ---- CRIT-1: remaining_gates replaces, never appends --------------------

    def test_remaining_gates_replaces_not_appends(self):
        """CRIT-1: writing remaining_gates twice with DIFFERENT scalars leaves the
        persisted value EQUAL to the second exactly — no concatenation, no
        duplicated "code review", no \\n-accumulation. Proves the scalar
        representation defeats _deep_merge's list-append.
        """
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # update(1) + update(1) + load(1) = 3
        mock_conn, _ = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "develop_gate_ledger": {
                        "remaining_gates": "design review\ncode review",
                    },
                },
            )
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "develop_gate_ledger": {
                        "remaining_gates": "code review\ngreen-mirage\ntest suite",
                    },
                },
            )
            load_result = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert load_result["found"] is True
        assert load_result["state"] == {
            "develop_gate_ledger": {
                "remaining_gates": "code review\ngreen-mirage\ntest suite",
            },
        }

    # ---- Interleaving: develop ledger write + simulated PreCompact ----------

    def test_interleaved_develop_and_compact_writes(self):
        """develop writes the ledger; a simulated PreCompact load->add->save then
        runs; a final load shows all three keys present and the ledger intact.
        """
        from spellbook.server import (
            workflow_state_update,
            workflow_state_load,
            workflow_state_save,
        )

        project_path = "/test/project"

        # update(1) + load(1) + save(1) + load(1) = 4
        mock_conn, _ = _setup_get_connection_mock(self.db_path, 4)

        with tripwire:
            # (a) develop records its ledger
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "active_skill": "develop",
                    "skill_phase": "2",
                    "develop_gate_ledger": {
                        "current_phase": "2",
                        "need_flags": {
                            "needs_research": False,
                            "needs_design": True,
                            "needs_infrastructure": False,
                        },
                        "remaining_gates": "design review\ncode review",
                        "plan_pointer": "/tmp/plan.md",
                    },
                },
            )
            # (b) simulate PreCompact: load -> add hook-owned keys -> save
            mid = workflow_state_load.fn(project_path=project_path)
            existing_state = mid["state"]
            existing_state["stint_stack"] = [
                {"label": "build", "started_at": "2026-05-24T02:00:00Z"}
            ]
            existing_state["compaction_flag"] = True
            workflow_state_save.fn(project_path=project_path, state=existing_state, trigger="auto")
            # (c) final load
            final = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 4)
        assert final["found"] is True
        assert final["state"] == {
            "active_skill": "develop",
            "skill_phase": "2",
            "develop_gate_ledger": {
                "current_phase": "2",
                "need_flags": {
                    "needs_research": False,
                    "needs_design": True,
                    "needs_infrastructure": False,
                },
                "remaining_gates": "design review\ncode review",
                "plan_pointer": "/tmp/plan.md",
            },
            "stint_stack": [{"label": "build", "started_at": "2026-05-24T02:00:00Z"}],
            "compaction_flag": True,
        }

    # ---- CRIT-2: atomic read-merge-write, disjoint + same-key --------------

    def test_interleaved_writes_disjoint_keys_lose_nothing(self):
        """CRIT-2: two read-merge-write sequences on DIFFERENT keys (one writes
        develop_gate_ledger, the other compaction_flag + stint_stack) interleaved;
        the final load shows NEITHER write lost. Exercises the atomic
        single-transaction read-merge-write path.
        """
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # update(develop) + update(hook) + load = 3
        mock_conn, _ = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            # writer A: develop owns develop_gate_ledger + active_skill + skill_phase
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "active_skill": "develop",
                    "skill_phase": "2",
                    "develop_gate_ledger": {
                        "current_phase": "2",
                        "remaining_gates": "design review\ncode review",
                        "plan_pointer": "/tmp/plan.md",
                    },
                },
            )
            # writer B: hooks own compaction_flag + stint_stack
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "compaction_flag": True,
                    "stint_stack": [{"label": "build", "started_at": "2026-05-24T03:00:00Z"}],
                },
            )
            final = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert final["found"] is True
        assert final["state"] == {
            "active_skill": "develop",
            "skill_phase": "2",
            "develop_gate_ledger": {
                "current_phase": "2",
                "remaining_gates": "design review\ncode review",
                "plan_pointer": "/tmp/plan.md",
            },
            "compaction_flag": True,
            "stint_stack": [{"label": "build", "started_at": "2026-05-24T03:00:00Z"}],
        }

    def test_interleaved_writes_same_key_deterministic_merge(self):
        """CRIT-2: two writes both setting develop_gate_ledger.current_phase; the
        later writer's value wins deterministically (scalar replace), and no
        unrelated sibling key (remaining_gates, plan_pointer) is dropped.
        """
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        # update + update + load = 3
        mock_conn, _ = _setup_get_connection_mock(self.db_path, 3)

        with tripwire:
            # first write seeds current_phase + sibling scalars
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "develop_gate_ledger": {
                        "current_phase": "2",
                        "remaining_gates": "design review\ncode review",
                        "plan_pointer": "/tmp/plan.md",
                    },
                },
            )
            # second write touches only current_phase
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "develop_gate_ledger": {
                        "current_phase": "3",
                    },
                },
            )
            final = workflow_state_load.fn(project_path=project_path)

        _assert_get_connection_calls(mock_conn, 3)
        assert final["found"] is True
        assert final["state"] == {
            "develop_gate_ledger": {
                "current_phase": "3",
                "remaining_gates": "design review\ncode review",
                "plan_pointer": "/tmp/plan.md",
            },
        }


class TestAtomicReadMergeWriteUnderContention:
    """CRIT-2 (the discriminating test): the atomicity guarantee must hold under a
    REAL concurrent interleaving across two distinct connections — the cross-context
    race between the MCP server process (workflow_state_update) and the PreCompact
    hook subprocess (which read-merge-writes compaction_flag/stint_stack into the SAME
    row).

    The sequential interleaving tests above pass with OR without an explicit
    transaction (single-threaded test ordering hides the race), so they cannot prove
    the BEGIN IMMEDIATE lock is actually taken. THIS test forces the lost-update
    interleaving (writer A reads, writer B reads stale base, A writes, B writes) and
    fails against a non-atomic read-merge-write: B's write, merged onto a base read
    BEFORE A committed, silently drops A's key. With the atomic BEGIN IMMEDIATE
    implementation, B's transaction blocks at its BEGIN until A commits, then merges
    onto A's committed state, so NEITHER write is lost.

    Each writer gets its OWN sqlite3 connection (the production cache returns one
    connection per path, but two processes hold two connections — that is the real
    topology). A one-shot delay injected into _deep_merge widens A's window so the
    interleaving is deterministic, not probabilistic.
    """

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test database."""
        self.db_path = str(tmp_path / "test.db")
        init_db(self.db_path)
        yield
        close_all_connections()

    def _make_distinct_connection(self):
        """A fresh sqlite3 connection to the test DB, configured like production
        (WAL + busy timeout) but NOT shared via the get_connection cache — this
        models a second OS process holding its own connection to the same file.
        """
        import sqlite3

        conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def test_concurrent_disjoint_key_writes_lose_nothing(self):
        """Two threads, two connections, forced read-before-write interleaving:
        writer A writes develop_gate_ledger; writer B writes compaction_flag +
        stint_stack. The final persisted state MUST contain BOTH writers' keys
        exactly. Non-atomic read-merge-write fails here (one writer's keys are
        dropped); the BEGIN IMMEDIATE implementation passes.
        """
        import threading
        import time
        import spellbook.core.db as dbmod
        import spellbook.mcp.tools.misc as misc
        from spellbook.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        thread_conns = {}
        a_in_merge = threading.Event()
        original_deep_merge = misc._deep_merge
        merge_delay_armed = {"value": True}

        def get_connection_threadlocal(db_path=None):
            # Each thread reuses the distinct connection assigned to it. Models the
            # per-process connection: A and B never share a connection.
            ident = threading.get_ident()
            return thread_conns[ident]

        def slow_deep_merge(base, updates):
            # Fire exactly once, for writer A only: signal that A has read the base
            # and is between SELECT and INSERT, then hold the window open so B has a
            # chance to read the same base (non-atomic) or block on A's lock (atomic).
            if updates.get("active_skill") == "develop" and merge_delay_armed["value"]:
                merge_delay_armed["value"] = False
                a_in_merge.set()
                time.sleep(0.4)
            return original_deep_merge(base, updates)

        def writer_a():
            thread_conns[threading.get_ident()] = self._make_distinct_connection()
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "active_skill": "develop",
                    "skill_phase": "2",
                    "develop_gate_ledger": {
                        "current_phase": "2",
                        "remaining_gates": "design review\ncode review",
                        "plan_pointer": "/tmp/plan.md",
                    },
                },
            )

        def writer_b():
            thread_conns[threading.get_ident()] = self._make_distinct_connection()
            # Wait until A is mid-merge (has read the base) before B starts its own
            # read-merge-write, so the interleaving is the lost-update ordering.
            a_in_merge.wait(timeout=5.0)
            workflow_state_update.fn(
                project_path=project_path,
                updates={
                    "compaction_flag": True,
                    "stint_stack": [{"label": "build", "started_at": "2026-05-24T03:00:00Z"}],
                },
            )

        orig_get_connection = dbmod.get_connection
        misc._deep_merge = slow_deep_merge
        dbmod.get_connection = get_connection_threadlocal
        try:
            ta = threading.Thread(target=writer_a)
            tb = threading.Thread(target=writer_b)
            ta.start()
            tb.start()
            ta.join(timeout=10.0)
            tb.join(timeout=10.0)
        finally:
            misc._deep_merge = original_deep_merge
            dbmod.get_connection = orig_get_connection
            for conn in thread_conns.values():
                conn.close()

        # Load through the test DB (get_connection has been restored to the real
        # default-path version, so route the load explicitly to self.db_path).
        load_mock, _ = _setup_get_connection_mock(self.db_path, 1)
        with tripwire:
            load_result = workflow_state_load.fn(project_path=project_path)
        _assert_get_connection_calls(load_mock, 1)
        assert load_result["found"] is True
        assert load_result["state"] == {
            "active_skill": "develop",
            "skill_phase": "2",
            "develop_gate_ledger": {
                "current_phase": "2",
                "remaining_gates": "design review\ncode review",
                "plan_pointer": "/tmp/plan.md",
            },
            "compaction_flag": True,
            "stint_stack": [{"label": "build", "started_at": "2026-05-24T03:00:00Z"}],
        }
