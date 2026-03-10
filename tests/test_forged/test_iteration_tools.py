"""Tests for Forged iteration MCP tools.

Following TDD: tests written BEFORE implementation.
These tests cover forge_iteration_start, forge_iteration_advance, forge_iteration_return.
"""

import json
import pytest
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


class TestForgeIterationStart:
    """Tests for forge_iteration_start tool."""

    def test_start_creates_new_iteration_state(self, tmp_path):
        """Starting iteration for new feature creates initial state."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = get_forged_connection(str(db_path))
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(feature_name="my-feature")

        assert result["status"] == "started"
        assert result["feature_name"] == "my-feature"
        assert result["current_stage"] == "DISCOVER"
        assert result["iteration_number"] == 1
        assert "token" in result
        assert result["token"] is not None

    def test_start_with_custom_starting_stage(self, tmp_path):
        """Starting iteration can specify custom starting stage."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = get_forged_connection(str(db_path))
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(
                    feature_name="my-feature",
                    starting_stage="DESIGN"
                )

        assert result["current_stage"] == "DESIGN"

    def test_start_with_preferences(self, tmp_path):
        """Starting iteration stores preferences."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = get_forged_connection(str(db_path))
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(
                    feature_name="my-feature",
                    preferences={"strict_mode": True, "max_iterations": 5}
                )

        assert result["status"] == "started"
        # Preferences should be stored in database

    def test_start_resumes_existing_feature(self, tmp_path):
        """Starting iteration for existing feature resumes state."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        # Pre-populate with existing state
        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO iteration_state
            (project_path, feature_name, iteration_number, current_stage, preferences, feedback_history)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("/test/project", "existing-feature", 3, "IMPLEMENT", "{}", "[]"))
        conn.commit()

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(feature_name="existing-feature")

        assert result["status"] == "resumed"
        assert result["iteration_number"] == 3
        assert result["current_stage"] == "IMPLEMENT"

    def test_start_rejects_invalid_stage(self, tmp_path):
        """Starting with invalid stage returns error."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = get_forged_connection(str(db_path))
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(
                    feature_name="my-feature",
                    starting_stage="INVALID_STAGE"
                )

        assert result["status"] == "error"
        assert "invalid stage" in result["error"].lower()

    def test_start_creates_token_in_database(self, tmp_path):
        """Token is persisted in forge_tokens table."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(feature_name="my-feature")

        token = result["token"]
        cursor = conn.cursor()
        cursor.execute("SELECT stage, feature_name FROM forge_tokens WHERE id = ?", (token,))
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "DISCOVER"
        assert row[1] == "my-feature"

    def test_start_invalidates_old_token(self, tmp_path):
        """Starting new iteration invalidates previous token for feature."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # First start
                result1 = forge_iteration_start(feature_name="my-feature")
                token1 = result1["token"]

                # Second start (resume)
                result2 = forge_iteration_start(feature_name="my-feature")
                token2 = result2["token"]

        # First token should be invalidated
        cursor = conn.cursor()
        cursor.execute("SELECT invalidated_at FROM forge_tokens WHERE id = ?", (token1,))
        row = cursor.fetchone()
        assert row[0] is not None  # invalidated_at should be set

        # Second token should be valid
        cursor.execute("SELECT invalidated_at FROM forge_tokens WHERE id = ?", (token2,))
        row = cursor.fetchone()
        assert row[0] is None  # Not invalidated yet


class TestForgeIterationAdvance:
    """Tests for forge_iteration_advance tool."""

    def test_advance_moves_to_next_stage(self, tmp_path):
        """Advancing with valid token moves to next stage."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]

                advance_result = forge_iteration_advance(
                    feature_name="my-feature",
                    current_token=token
                )

        assert advance_result["status"] == "advanced"
        assert advance_result["previous_stage"] == "DISCOVER"
        assert advance_result["current_stage"] == "DESIGN"
        assert "token" in advance_result
        assert advance_result["token"] != token  # New token issued

    def test_advance_with_evidence(self, tmp_path):
        """Advancing stores evidence/knowledge."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]

                advance_result = forge_iteration_advance(
                    feature_name="my-feature",
                    current_token=token,
                    evidence={"discovery_notes": "Found existing patterns", "files_reviewed": 5}
                )

        assert advance_result["status"] == "advanced"
        # Evidence should be stored in accumulated_knowledge

    def test_advance_rejects_invalid_token(self, tmp_path):
        """Advancing with invalid token is rejected."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                forge_iteration_start(feature_name="my-feature")

                advance_result = forge_iteration_advance(
                    feature_name="my-feature",
                    current_token="invalid-token-12345"
                )

        assert advance_result["status"] == "error"
        assert "invalid token" in advance_result["error"].lower()

    def test_advance_rejects_expired_token(self, tmp_path):
        """Advancing with already-invalidated token is rejected."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token1 = start_result["token"]

                # Advance once to invalidate token1
                advance_result = forge_iteration_advance(
                    feature_name="my-feature",
                    current_token=token1
                )
                token2 = advance_result["token"]

                # Try to use token1 again
                bad_result = forge_iteration_advance(
                    feature_name="my-feature",
                    current_token=token1
                )

        assert bad_result["status"] == "error"
        assert "expired" in bad_result["error"].lower() or "invalid" in bad_result["error"].lower()

    def test_advance_rejects_wrong_feature(self, tmp_path):
        """Advancing with token from different feature is rejected."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result_a = forge_iteration_start(feature_name="feature-a")
                token_a = result_a["token"]

                forge_iteration_start(feature_name="feature-b")

                # Try to advance feature-b with feature-a's token
                bad_result = forge_iteration_advance(
                    feature_name="feature-b",
                    current_token=token_a
                )

        assert bad_result["status"] == "error"
        assert "feature" in bad_result["error"].lower() or "mismatch" in bad_result["error"].lower()

    def test_advance_from_complete_is_error(self, tmp_path):
        """Advancing from COMPLETE stage is an error."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        # Pre-populate with COMPLETE state
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO iteration_state
            (project_path, feature_name, iteration_number, current_stage, preferences, feedback_history)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("/test/project", "done-feature", 5, "COMPLETE", "{}", "[]"))

        # Create a token for this state
        token_id = "test-complete-token"
        cursor.execute("""
            INSERT INTO forge_tokens (id, feature_name, stage)
            VALUES (?, ?, ?)
        """, (token_id, "done-feature", "COMPLETE"))
        conn.commit()

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_advance(
                    feature_name="done-feature",
                    current_token=token_id
                )

        assert result["status"] == "error"
        assert "complete" in result["error"].lower() or "cannot advance" in result["error"].lower()

    def test_advance_follows_stage_order(self, tmp_path):
        """Stages advance in correct order: DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(feature_name="my-feature")
                token = result["token"]

                stages_seen = ["DISCOVER"]
                expected_order = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]

                for expected_next in expected_order[1:]:
                    result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                    stages_seen.append(result["current_stage"])
                    token = result["token"]

        assert stages_seen == expected_order


class TestForgeIterationReturn:
    """Tests for forge_iteration_return tool."""

    def test_return_to_earlier_stage(self, tmp_path):
        """Returning moves to specified earlier stage with feedback."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # Start and advance to DESIGN
                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]
                advance_result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                token = advance_result["token"]

                # Return to DISCOVER with feedback
                feedback = [
                    {
                        "source": "design-validator",
                        "critique": "Missing edge case consideration",
                        "evidence": "No handling for empty input",
                        "suggestion": "Add discovery task for edge cases",
                        "severity": "blocking"
                    }
                ]
                return_result = forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=feedback
                )

        assert return_result["status"] == "returned"
        assert return_result["previous_stage"] == "DESIGN"
        assert return_result["current_stage"] == "DISCOVER"
        assert return_result["iteration_number"] == 2  # Incremented
        assert "token" in return_result

    def test_return_increments_iteration(self, tmp_path):
        """Returning increments the iteration counter."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                assert start_result["iteration_number"] == 1

                token = start_result["token"]
                advance_result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                token = advance_result["token"]

                return_result = forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=[{"source": "test", "critique": "test", "evidence": "test", "suggestion": "test", "severity": "minor"}]
                )
                assert return_result["iteration_number"] == 2

    def test_return_stores_feedback_history(self, tmp_path):
        """Feedback is stored in iteration state."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]
                advance_result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                token = advance_result["token"]

                feedback = [
                    {"source": "v1", "critique": "Issue 1", "evidence": "E1", "suggestion": "S1", "severity": "blocking"}
                ]
                forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=feedback
                )

        # Check database for stored feedback
        cursor = conn.cursor()
        cursor.execute(
            "SELECT feedback_history FROM iteration_state WHERE feature_name = ?",
            ("my-feature",)
        )
        row = cursor.fetchone()
        stored_feedback = json.loads(row[0])
        assert len(stored_feedback) == 1
        assert stored_feedback[0]["source"] == "v1"

    def test_return_with_reflection(self, tmp_path):
        """Returning with reflection creates reflection record."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]
                advance_result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                token = advance_result["token"]

                feedback = [
                    {"source": "test-validator", "critique": "Found issue", "evidence": "Line 42", "suggestion": "Fix it", "severity": "blocking"}
                ]
                forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=feedback,
                    reflection="Learned that edge cases need more attention during discovery"
                )

        # Check reflections table
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lesson_learned, validator FROM reflections WHERE feature_name = ?",
            ("my-feature",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert "edge cases" in row[0].lower()
        assert row[1] == "test-validator"

    def test_return_rejects_invalid_token(self, tmp_path):
        """Returning with invalid token is rejected."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_return
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                forge_iteration_start(feature_name="my-feature")

                result = forge_iteration_return(
                    feature_name="my-feature",
                    current_token="bad-token",
                    return_to="DISCOVER",
                    feedback=[]
                )

        assert result["status"] == "error"
        assert "invalid token" in result["error"].lower()

    def test_return_rejects_invalid_stage(self, tmp_path):
        """Returning to invalid stage is rejected."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_return
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]

                result = forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="NOT_A_STAGE",
                    feedback=[]
                )

        assert result["status"] == "error"
        assert "invalid stage" in result["error"].lower()

    def test_return_cannot_return_to_complete_or_escalated(self, tmp_path):
        """Cannot return to COMPLETE or ESCALATED stages."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]
                advance_result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                token = advance_result["token"]

                result_complete = forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="COMPLETE",
                    feedback=[]
                )

        assert result_complete["status"] == "error"
        assert "cannot return" in result_complete["error"].lower()

    def test_return_requires_feedback(self, tmp_path):
        """Returning requires at least one feedback item."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                start_result = forge_iteration_start(feature_name="my-feature")
                token = start_result["token"]
                advance_result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                token = advance_result["token"]

                result = forge_iteration_return(
                    feature_name="my-feature",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=[]  # Empty feedback
                )

        assert result["status"] == "error"
        assert "feedback" in result["error"].lower()


class TestTokenSystem:
    """Integration tests for token-based workflow enforcement."""

    def test_token_prevents_skipping_stages(self, tmp_path):
        """Tokens prevent skipping stages in workflow."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # Start at DISCOVER
                result = forge_iteration_start(feature_name="my-feature")
                token = result["token"]
                assert result["current_stage"] == "DISCOVER"

                # Cannot advance twice with same token
                forge_iteration_advance(feature_name="my-feature", current_token=token)

                skip_result = forge_iteration_advance(feature_name="my-feature", current_token=token)

        assert skip_result["status"] == "error"

    def test_token_is_unique_per_transition(self, tmp_path):
        """Each stage transition generates unique token."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        tokens = []
        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(feature_name="my-feature")
                tokens.append(result["token"])
                token = result["token"]

                for _ in range(4):  # Advance through remaining stages
                    result = forge_iteration_advance(feature_name="my-feature", current_token=token)
                    if result["status"] == "advanced":
                        tokens.append(result["token"])
                        token = result["token"]

        # All tokens should be unique
        assert len(tokens) == len(set(tokens))

    def test_concurrent_features_have_independent_tokens(self, tmp_path):
        """Multiple features can be worked on with independent tokens."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # Start two features
                result_a = forge_iteration_start(feature_name="feature-a")
                result_b = forge_iteration_start(feature_name="feature-b")

                token_a = result_a["token"]
                token_b = result_b["token"]

                # Advance feature-a
                advance_a = forge_iteration_advance(feature_name="feature-a", current_token=token_a)

                # Feature-b should still be able to advance with its token
                advance_b = forge_iteration_advance(feature_name="feature-b", current_token=token_b)

        assert advance_a["status"] == "advanced"
        assert advance_b["status"] == "advanced"
        assert advance_a["current_stage"] == "DESIGN"
        assert advance_b["current_stage"] == "DESIGN"
