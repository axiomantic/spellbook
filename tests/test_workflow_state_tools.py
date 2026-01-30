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
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from spellbook_mcp.db import init_db, get_connection, close_all_connections


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
        from spellbook_mcp.server import workflow_state_save

        project_path = "/test/project"
        state = {
            "skill_stack": ["implementing-features"],
            "todos": [{"id": "1", "text": "Task 1", "status": "pending"}],
        }

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)
            result = workflow_state_save.fn(
                project_path=project_path,
                state=state,
                trigger="manual",
            )

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
        assert loaded_state["skill_stack"] == ["implementing-features"]
        assert row[1] == "manual"

    def test_save_updates_existing_record(self, tmp_path):
        """Test saving state updates existing record for same project."""
        from spellbook_mcp.server import workflow_state_save

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # First save
            state1 = {"skill_stack": ["debugging"]}
            workflow_state_save.fn(project_path=project_path, state=state1, trigger="manual")

            # Second save (update)
            state2 = {"skill_stack": ["implementing-features", "tdd"]}
            result = workflow_state_save.fn(
                project_path=project_path, state=state2, trigger="auto"
            )

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
        assert loaded_state["skill_stack"] == ["implementing-features", "tdd"]
        assert row[2] == "auto"  # Trigger updated

    def test_save_with_different_triggers(self, tmp_path):
        """Test saving with manual, auto, checkpoint triggers."""
        from spellbook_mcp.server import workflow_state_save

        triggers = ["manual", "auto", "checkpoint"]

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            for i, trigger in enumerate(triggers):
                project_path = f"/test/project-{i}"
                state = {"trigger_test": trigger}
                result = workflow_state_save.fn(
                    project_path=project_path, state=state, trigger=trigger
                )
                assert result["success"] is True
                assert result["trigger"] == trigger

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
        from spellbook_mcp.server import workflow_state_save
        import time

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # First save
            workflow_state_save.fn(
                project_path=project_path,
                state={"version": 1},
                trigger="manual",
            )

            # Get created_at
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
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
                state={"version": 2},
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

        # created_at should be preserved, updated_at should be newer
        assert created_at_1 == created_at_2
        assert updated_at_2 >= created_at_2

    def test_save_handles_complex_state(self, tmp_path):
        """Test saving complex nested state structures."""
        from spellbook_mcp.server import workflow_state_save

        project_path = "/test/project"
        state = {
            "skill_stack": ["implementing-features", "tdd"],
            "todos": [
                {"id": "1", "text": "Task 1", "status": "completed"},
                {"id": "2", "text": "Task 2", "status": "pending"},
            ],
            "subagents": [
                {"id": "agent-1", "task": "research", "status": "complete"}
            ],
            "context": {
                "files_modified": ["src/main.py", "tests/test_main.py"],
                "decisions": ["Using pytest for testing"],
            },
        }

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)
            result = workflow_state_save.fn(
                project_path=project_path, state=state, trigger="checkpoint"
            )

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
        from spellbook_mcp.server import workflow_state_load

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)
            result = workflow_state_load.fn(project_path="/nonexistent/project")

        assert result["success"] is True
        assert result["found"] is False
        assert result["state"] is None
        assert result["age_hours"] is None
        assert result["trigger"] is None

    def test_load_returns_state_for_existing_project(self, tmp_path):
        """Test loading returns state for existing project."""
        from spellbook_mcp.server import workflow_state_save, workflow_state_load

        project_path = "/test/project"
        state = {"skill_stack": ["debugging"], "todos": []}

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # Save state
            workflow_state_save.fn(project_path=project_path, state=state, trigger="manual")

            # Load state
            result = workflow_state_load.fn(project_path=project_path)

        assert result["success"] is True
        assert result["found"] is True
        assert result["state"] == state
        assert result["trigger"] == "manual"
        assert result["age_hours"] is not None
        assert result["age_hours"] < 1.0  # Just saved, should be very recent

    def test_load_respects_max_age_hours(self, tmp_path):
        """Test loading returns found=False for stale state."""
        from spellbook_mcp.server import workflow_state_load

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
            (project_path, '{"old": true}', "manual", old_time, old_time),
        )
        conn.commit()

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = conn

            # Load with default max_age_hours (24)
            result = workflow_state_load.fn(project_path=project_path, max_age_hours=24.0)

        assert result["success"] is True
        assert result["found"] is False  # Too old
        assert result["state"] is None
        assert result["age_hours"] is not None
        assert result["age_hours"] > 24.0
        assert result["trigger"] == "manual"

    def test_load_accepts_fresh_state_within_max_age(self, tmp_path):
        """Test loading accepts state within max_age_hours."""
        from spellbook_mcp.server import workflow_state_load

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
            (project_path, '{"recent": true}', "auto", recent_time, recent_time),
        )
        conn.commit()

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = conn

            # Load with 24 hour max age
            result = workflow_state_load.fn(project_path=project_path, max_age_hours=24.0)

        assert result["success"] is True
        assert result["found"] is True
        assert result["state"] == {"recent": True}
        assert 1.5 < result["age_hours"] < 3.0  # Approximately 2 hours

    def test_load_returns_age_hours(self, tmp_path):
        """Test loading returns correct age_hours."""
        from spellbook_mcp.server import workflow_state_load

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
            (project_path, '{"test": true}', "checkpoint", five_hours_ago, five_hours_ago),
        )
        conn.commit()

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = conn
            result = workflow_state_load.fn(project_path=project_path, max_age_hours=24.0)

        assert result["success"] is True
        assert result["found"] is True
        # Allow some margin for test execution time
        assert 4.5 < result["age_hours"] < 5.5

    def test_load_with_custom_max_age(self, tmp_path):
        """Test loading with custom max_age_hours parameter."""
        from spellbook_mcp.server import workflow_state_load

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
            (project_path, '{"test": true}', "manual", three_hours_ago, three_hours_ago),
        )
        conn.commit()

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = conn

            # With max_age=2 hours, should be stale
            result_stale = workflow_state_load.fn(project_path=project_path, max_age_hours=2.0)
            assert result_stale["found"] is False

            # With max_age=4 hours, should be fresh
            result_fresh = workflow_state_load.fn(project_path=project_path, max_age_hours=4.0)
            assert result_fresh["found"] is True


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
        from spellbook_mcp.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"
        updates = {"skill_stack": ["debugging"], "active_skill": "debugging"}

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            result = workflow_state_update.fn(project_path=project_path, updates=updates)
            assert result["success"] is True

            # Verify state was created
            load_result = workflow_state_load.fn(project_path=project_path)

        assert load_result["found"] is True
        assert load_result["state"]["skill_stack"] == ["debugging"]
        assert load_result["state"]["active_skill"] == "debugging"

    def test_update_merges_nested_dicts(self, tmp_path):
        """Test update deep-merges nested dictionaries."""
        from spellbook_mcp.server import workflow_state_save, workflow_state_update, workflow_state_load

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # Initial state with nested dict
            initial_state = {
                "context": {
                    "files_modified": ["file1.py"],
                    "decisions": ["decision1"],
                }
            }
            workflow_state_save.fn(project_path=project_path, state=initial_state, trigger="manual")

            # Update with partial nested dict
            updates = {
                "context": {
                    "files_modified": ["file2.py"],  # List - will be appended
                    "new_key": "new_value",  # New key - will be added
                }
            }
            workflow_state_update.fn(project_path=project_path, updates=updates)

            # Load and verify merge
            result = workflow_state_load.fn(project_path=project_path)

        assert result["found"] is True
        context = result["state"]["context"]
        # Lists are appended
        assert context["files_modified"] == ["file1.py", "file2.py"]
        # Original keys preserved
        assert context["decisions"] == ["decision1"]
        # New keys added
        assert context["new_key"] == "new_value"

    def test_update_appends_to_lists(self, tmp_path):
        """Test update appends to lists (skill_stack, subagents)."""
        from spellbook_mcp.server import workflow_state_save, workflow_state_update, workflow_state_load

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # Initial state with lists
            initial_state = {
                "skill_stack": ["implementing-features"],
                "subagents": [{"id": "agent-1", "task": "research"}],
            }
            workflow_state_save.fn(project_path=project_path, state=initial_state, trigger="manual")

            # Update with additional list items
            updates = {
                "skill_stack": ["tdd"],  # Should be appended
                "subagents": [{"id": "agent-2", "task": "review"}],  # Should be appended
            }
            workflow_state_update.fn(project_path=project_path, updates=updates)

            result = workflow_state_load.fn(project_path=project_path)

        assert result["found"] is True
        assert result["state"]["skill_stack"] == ["implementing-features", "tdd"]
        assert len(result["state"]["subagents"]) == 2
        assert result["state"]["subagents"][0]["id"] == "agent-1"
        assert result["state"]["subagents"][1]["id"] == "agent-2"

    def test_update_overwrites_scalars(self, tmp_path):
        """Test update overwrites scalar values."""
        from spellbook_mcp.server import workflow_state_save, workflow_state_update, workflow_state_load

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # Initial state with scalars
            initial_state = {
                "active_skill": "debugging",
                "phase": "discovery",
                "iteration_count": 1,
            }
            workflow_state_save.fn(project_path=project_path, state=initial_state, trigger="manual")

            # Update scalars
            updates = {
                "active_skill": "tdd",
                "phase": "implementation",
                "iteration_count": 2,
            }
            workflow_state_update.fn(project_path=project_path, updates=updates)

            result = workflow_state_load.fn(project_path=project_path)

        assert result["found"] is True
        assert result["state"]["active_skill"] == "tdd"
        assert result["state"]["phase"] == "implementation"
        assert result["state"]["iteration_count"] == 2

    def test_update_sets_auto_trigger(self, tmp_path):
        """Test that update always sets trigger to 'auto'."""
        from spellbook_mcp.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            workflow_state_update.fn(project_path=project_path, updates={"test": True})
            result = workflow_state_load.fn(project_path=project_path)

        assert result["trigger"] == "auto"

    def test_update_multiple_times(self, tmp_path):
        """Test multiple sequential updates accumulate correctly."""
        from spellbook_mcp.server import workflow_state_update, workflow_state_load

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # First update
            workflow_state_update.fn(
                project_path=project_path,
                updates={"skill_stack": ["skill1"], "count": 1}
            )

            # Second update
            workflow_state_update.fn(
                project_path=project_path,
                updates={"skill_stack": ["skill2"], "active": True}
            )

            # Third update
            workflow_state_update.fn(
                project_path=project_path,
                updates={"skill_stack": ["skill3"], "count": 2}
            )

            result = workflow_state_load.fn(project_path=project_path)

        assert result["found"] is True
        assert result["state"]["skill_stack"] == ["skill1", "skill2", "skill3"]
        assert result["state"]["count"] == 2  # Overwritten
        assert result["state"]["active"] is True  # Preserved


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
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(skill_name="test-skill")

        assert result["success"] is True
        assert result["skill_name"] == "test-skill"
        assert "ROLE" in result["content"]
        assert "FORBIDDEN" in result["content"]
        assert "Required Practices" in result["content"]
        assert "sections" not in result  # No sections key when not filtering

    def test_get_specific_sections(self, mock_spellbook_dir):
        """Test extracting specific sections (FORBIDDEN, ROLE)."""
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["FORBIDDEN", "ROLE"],
            )

        assert result["success"] is True
        assert "sections" in result
        assert "FORBIDDEN" in result["sections"]
        assert "Never do thing A" in result["sections"]["FORBIDDEN"]
        assert "ROLE" in result["sections"]
        assert "test role" in result["sections"]["ROLE"]

    def test_returns_error_for_missing_skill(self, mock_spellbook_dir):
        """Test returns error for non-existent skill."""
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(skill_name="nonexistent-skill")

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_extracts_xml_style_sections(self, mock_spellbook_dir):
        """Test extracting <FORBIDDEN>...</FORBIDDEN> style sections."""
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["CRITICAL"],
            )

        assert result["success"] is True
        assert "CRITICAL" in result["sections"]
        assert "critical information" in result["sections"]["CRITICAL"].lower()

    def test_extracts_markdown_style_sections(self, mock_spellbook_dir):
        """Test extracting ## Section Name style sections."""
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["Required Practices"],
            )

        assert result["success"] is True
        assert "Required Practices" in result["sections"]
        assert "thing X" in result["sections"]["Required Practices"]

    def test_handles_missing_sections_gracefully(self, mock_spellbook_dir):
        """Test that missing sections are simply not included."""
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["ROLE", "NONEXISTENT_SECTION"],
            )

        assert result["success"] is True
        assert "ROLE" in result["sections"]
        assert "NONEXISTENT_SECTION" not in result["sections"]

    def test_combined_content_from_sections(self, mock_spellbook_dir):
        """Test that content field contains combined sections."""
        from spellbook_mcp.server import skill_instructions_get

        with patch("spellbook_mcp.server.get_spellbook_dir") as mock_dir:
            mock_dir.return_value = mock_spellbook_dir
            result = skill_instructions_get.fn(
                skill_name="test-skill",
                sections=["ROLE", "FORBIDDEN"],
            )

        assert result["success"] is True
        # Content should contain formatted sections
        assert "## ROLE" in result["content"] or "## FORBIDDEN" in result["content"]


class TestDeepMerge:
    """Tests for the _deep_merge helper function."""

    def test_merge_flat_dicts(self):
        """Test merging flat dictionaries."""
        from spellbook_mcp.server import _deep_merge

        base = {"a": 1, "b": 2}
        updates = {"b": 3, "c": 4}
        result = _deep_merge(base, updates)

        assert result == {"a": 1, "b": 3, "c": 4}
        # Original should be unchanged
        assert base == {"a": 1, "b": 2}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        from spellbook_mcp.server import _deep_merge

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
        from spellbook_mcp.server import _deep_merge

        base = {"items": [1, 2, 3]}
        updates = {"items": [4, 5]}
        result = _deep_merge(base, updates)

        assert result["items"] == [1, 2, 3, 4, 5]

    def test_merge_overwrites_non_dict_non_list(self):
        """Test merging overwrites scalar values."""
        from spellbook_mcp.server import _deep_merge

        base = {"count": 1, "name": "old", "active": False}
        updates = {"count": 2, "name": "new", "active": True}
        result = _deep_merge(base, updates)

        assert result["count"] == 2
        assert result["name"] == "new"
        assert result["active"] is True

    def test_merge_handles_type_mismatch(self):
        """Test merging handles type mismatches (update wins)."""
        from spellbook_mcp.server import _deep_merge

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
        from spellbook_mcp.server import _deep_merge

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
        from spellbook_mcp.server import _deep_merge

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
        from spellbook_mcp.server import _deep_merge

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
        from spellbook_mcp.server import _extract_section

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
        from spellbook_mcp.server import _extract_section

        content = "<FORBIDDEN>content</FORBIDDEN>"
        result = _extract_section(content, "forbidden")
        assert result == "content"

    def test_extract_markdown_section(self):
        """Test extracting markdown-style sections."""
        from spellbook_mcp.server import _extract_section

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
        from spellbook_mcp.server import _extract_section

        content = "<ROLE>content</ROLE>"
        result = _extract_section(content, "MISSING")
        assert result is None

    def test_extract_prefers_xml_over_markdown(self):
        """Test that XML-style is tried before markdown."""
        from spellbook_mcp.server import _extract_section

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
        from spellbook_mcp.server import (
            workflow_state_save,
            workflow_state_update,
            workflow_state_load,
        )

        project_path = "/test/project"

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # 1. Initial save (session start)
            initial_state = {
                "skill_stack": [],
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
                    "skill_stack": ["implementing-features"],
                    "active_skill": "implementing-features",
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
                    "skill_stack": ["tdd"],
                    "active_skill": "tdd",
                },
            )

            # 5. Load and verify accumulated state
            load_result = workflow_state_load.fn(project_path=project_path)

        assert load_result["success"] is True
        assert load_result["found"] is True
        state = load_result["state"]

        # Skill stack accumulated
        assert state["skill_stack"] == ["implementing-features", "tdd"]
        # Active skill updated
        assert state["active_skill"] == "tdd"
        # Todos accumulated
        assert len(state["todos"]) == 1

    def test_multiple_projects_isolated(self, tmp_path):
        """Test that different projects have isolated state."""
        from spellbook_mcp.server import (
            workflow_state_save,
            workflow_state_load,
        )

        with patch("spellbook_mcp.db.get_connection") as mock_conn:
            mock_conn.return_value = get_connection(self.db_path)

            # Save state for project A
            workflow_state_save.fn(
                project_path="/project/a",
                state={"project": "A", "value": 1},
                trigger="manual",
            )

            # Save state for project B
            workflow_state_save.fn(
                project_path="/project/b",
                state={"project": "B", "value": 2},
                trigger="manual",
            )

            # Load each and verify isolation
            result_a = workflow_state_load.fn(project_path="/project/a")
            result_b = workflow_state_load.fn(project_path="/project/b")

        assert result_a["state"]["project"] == "A"
        assert result_a["state"]["value"] == 1
        assert result_b["state"]["project"] == "B"
        assert result_b["state"]["value"] == 2
