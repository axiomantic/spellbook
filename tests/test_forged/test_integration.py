"""Integration tests for Forged autonomous development system.

These tests verify the complete workflow integration:
1. Schema initialization
2. Full feature lifecycle (init -> advance -> complete)
3. ITERATE verdict flow
4. Roundtable convene/response cycle
"""

import json
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch


class TestSchemaIntegration:
    """Tests for schema initialization during server startup."""

    def test_schema_initializes_all_tables(self, tmp_path):
        """Schema initialization creates all required tables."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()

        # Check that all tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "schema_version",
            "forge_tokens",
            "iteration_state",
            "reflections",
            "tool_analytics",
        }
        assert expected_tables.issubset(tables)

    def test_schema_is_idempotent(self, tmp_path):
        """Calling init_forged_schema multiple times is safe."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"

        # Initialize multiple times
        init_forged_schema(str(db_path))
        init_forged_schema(str(db_path))
        init_forged_schema(str(db_path))

        # Should still work correctly
        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        count = cursor.fetchone()[0]

        # Should have exactly one version record
        assert count == 1

    def test_schema_records_version(self, tmp_path):
        """Schema version is recorded in the database."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection
        from spellbook_mcp.forged.models import SCHEMA_VERSION

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        version = cursor.fetchone()[0]

        assert version == SCHEMA_VERSION


class TestCompleteFeatureLifecycle:
    """Tests for full feature flow: init -> advance through stages -> complete."""

    def test_feature_flows_through_all_stages(self, tmp_path):
        """A feature can flow through DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # Start at DISCOVER
                result = forge_iteration_start(feature_name="complete-flow-test")
                assert result["status"] == "started"
                assert result["current_stage"] == "DISCOVER"
                token = result["token"]

                # Track stages
                stages_visited = [result["current_stage"]]

                # Advance through all stages
                for expected_next in ["DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]:
                    result = forge_iteration_advance(
                        feature_name="complete-flow-test",
                        current_token=token,
                        evidence={"stage_completed": True}
                    )
                    assert result["status"] == "advanced", f"Failed advancing to {expected_next}: {result}"
                    assert result["current_stage"] == expected_next
                    stages_visited.append(result["current_stage"])
                    token = result["token"]

        assert stages_visited == ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]

    def test_feature_with_evidence_accumulation(self, tmp_path):
        """Evidence is accumulated as feature progresses through stages."""
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                result = forge_iteration_start(feature_name="evidence-test")
                token = result["token"]

                # Advance with evidence
                result = forge_iteration_advance(
                    feature_name="evidence-test",
                    current_token=token,
                    evidence={"discover_findings": ["Pattern A found", "Constraint B identified"]}
                )
                token = result["token"]

                result = forge_iteration_advance(
                    feature_name="evidence-test",
                    current_token=token,
                    evidence={"design_decisions": ["Use strategy X", "Interface Y"]}
                )

        # Check accumulated knowledge in database
        cursor = conn.cursor()
        cursor.execute(
            "SELECT accumulated_knowledge FROM iteration_state WHERE feature_name = ?",
            ("evidence-test",)
        )
        row = cursor.fetchone()
        knowledge = json.loads(row[0])

        assert "discover_evidence" in knowledge
        assert "design_evidence" in knowledge


class TestIterateVerdictFlow:
    """Tests for ITERATE verdict triggering return flow."""

    def test_iterate_returns_to_earlier_stage(self, tmp_path):
        """ITERATE verdict causes return to specified stage with incremented iteration."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
            forge_iteration_return,
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # Start and advance to PLAN
                result = forge_iteration_start(feature_name="iterate-test")
                token = result["token"]
                assert result["iteration_number"] == 1

                result = forge_iteration_advance(feature_name="iterate-test", current_token=token)
                token = result["token"]  # Now at DESIGN

                result = forge_iteration_advance(feature_name="iterate-test", current_token=token)
                token = result["token"]  # Now at PLAN

                # Return to DESIGN with feedback
                feedback = [
                    {
                        "source": "plan-validator",
                        "critique": "Design doesn't cover edge case X",
                        "evidence": "Missing handler for null input",
                        "suggestion": "Add null check in design",
                        "severity": "blocking"
                    }
                ]
                result = forge_iteration_return(
                    feature_name="iterate-test",
                    current_token=token,
                    return_to="DESIGN",
                    feedback=feedback,
                    reflection="Need to be more thorough with edge cases"
                )

        assert result["status"] == "returned"
        assert result["previous_stage"] == "PLAN"
        assert result["current_stage"] == "DESIGN"
        assert result["iteration_number"] == 2  # Incremented

    def test_multiple_iterations_track_history(self, tmp_path):
        """Multiple iterate cycles accumulate feedback history."""
        from spellbook_mcp.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
            forge_iteration_return,
        )
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = "/test/project"

                # First iteration
                result = forge_iteration_start(feature_name="multi-iterate")
                token = result["token"]

                result = forge_iteration_advance(feature_name="multi-iterate", current_token=token)
                token = result["token"]

                # First return
                result = forge_iteration_return(
                    feature_name="multi-iterate",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=[{"source": "v1", "critique": "Issue 1", "evidence": "e1", "suggestion": "s1", "severity": "blocking"}]
                )
                token = result["token"]
                assert result["iteration_number"] == 2

                # Second iteration - advance again
                result = forge_iteration_advance(feature_name="multi-iterate", current_token=token)
                token = result["token"]

                # Second return
                result = forge_iteration_return(
                    feature_name="multi-iterate",
                    current_token=token,
                    return_to="DISCOVER",
                    feedback=[{"source": "v2", "critique": "Issue 2", "evidence": "e2", "suggestion": "s2", "severity": "minor"}]
                )

        assert result["iteration_number"] == 3

        # Check all feedback is stored
        cursor = conn.cursor()
        cursor.execute(
            "SELECT feedback_history FROM iteration_state WHERE feature_name = ?",
            ("multi-iterate",)
        )
        row = cursor.fetchone()
        feedback_history = json.loads(row[0])

        assert len(feedback_history) == 2
        assert feedback_history[0]["source"] == "v1"
        assert feedback_history[1]["source"] == "v2"


class TestRoundtableEndToEnd:
    """Tests for roundtable convene/response cycle."""

    def test_roundtable_convene_generates_prompt(self, tmp_path):
        """roundtable_convene generates a valid prompt with archetypes."""
        from spellbook_mcp.forged.roundtable import roundtable_convene
        from spellbook_mcp.forged.artifacts import write_artifact

        # Create a test artifact
        artifact_path = tmp_path / "test-artifact.md"
        artifact_path.write_text("# Test Design\n\nThis is a test design document.")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
        )

        assert "dialogue" in result
        assert result["dialogue"]  # Not empty
        assert "test-feature" in result["dialogue"]
        assert "DESIGN" in result["dialogue"]
        assert "Test Design" in result["dialogue"]
        assert "archetypes" in result
        assert len(result["archetypes"]) > 0

    def test_roundtable_convene_uses_stage_defaults(self, tmp_path):
        """Default archetypes vary by stage."""
        from spellbook_mcp.forged.roundtable import roundtable_convene, get_default_archetypes

        artifact_path = tmp_path / "artifact.md"
        artifact_path.write_text("Test content")

        # DISCOVER stage
        result_discover = roundtable_convene(
            feature_name="test",
            stage="DISCOVER",
            artifact_path=str(artifact_path),
        )

        # IMPLEMENT stage
        result_implement = roundtable_convene(
            feature_name="test",
            stage="IMPLEMENT",
            artifact_path=str(artifact_path),
        )

        # Archetypes should differ
        assert result_discover["archetypes"] != result_implement["archetypes"]

    def test_process_roundtable_response_all_approve(self, tmp_path):
        """Processing response with all APPROVE verdicts returns consensus True."""
        from spellbook_mcp.forged.roundtable import process_roundtable_response

        response = """
        **Magician**: The implementation looks solid. Types are correct.

        Concerns:
        - None

        Suggestions:
        - None

        Verdict: APPROVE

        **Hermit**: Deep analysis reveals sound architecture.

        Concerns:
        - None

        Suggestions:
        - Could add more comments

        Verdict: APPROVE

        **Justice**: Both perspectives agree.

        Verdict: APPROVE
        """

        result = process_roundtable_response(
            response=response,
            stage="IMPLEMENT",
            iteration=1
        )

        assert result["consensus"] is True
        assert result["return_to"] is None
        assert len(result["feedback"]) == 0

    def test_process_roundtable_response_with_iterate(self, tmp_path):
        """Processing response with ITERATE verdict returns consensus False with feedback."""
        from spellbook_mcp.forged.roundtable import process_roundtable_response

        response = """
        **Magician**: Code has technical issues.

        Concerns:
        - Missing error handling for edge case X
        - Type mismatch in function Y

        Suggestions:
        - Add try-catch block
        - Fix type annotation

        Verdict: ITERATE
        Severity: blocking

        **Hermit**: Needs more work.

        Concerns:
        - Logic flaw in main loop

        Suggestions:
        - Review algorithm

        Verdict: ITERATE
        Severity: significant
        """

        result = process_roundtable_response(
            response=response,
            stage="IMPLEMENT",
            iteration=2
        )

        assert result["consensus"] is False
        assert result["return_to"] == "IMPLEMENT"
        assert len(result["feedback"]) > 0

        # Check feedback structure
        feedback_sources = [fb["source"] for fb in result["feedback"]]
        assert any("Magician" in src for src in feedback_sources)

    def test_roundtable_debate_generates_prompt(self, tmp_path):
        """roundtable_debate generates a debate prompt for Justice."""
        from spellbook_mcp.forged.roundtable import roundtable_debate

        artifact_path = tmp_path / "artifact.md"
        artifact_path.write_text("Test content for debate")

        conflicting_verdicts = {
            "Magician": "APPROVE",
            "Hermit": "ITERATE",
            "Fool": "APPROVE"
        }

        result = roundtable_debate(
            feature_name="debate-test",
            conflicting_verdicts=conflicting_verdicts,
            artifact_path=str(artifact_path),
        )

        assert "dialogue" in result
        assert result["moderator"] == "Justice"
        assert "Magician" in result["dialogue"]
        assert "APPROVE" in result["dialogue"]
        assert "ITERATE" in result["dialogue"]


class TestProjectGraphIntegration:
    """Tests for project graph initialization and updates."""

    def test_project_init_creates_graph(self, tmp_path):
        """forge_project_init creates a valid project graph."""
        from spellbook_mcp.forged.project_tools import forge_project_init
        from spellbook_mcp.forged.artifacts import get_project_encoded

        project_path = str(tmp_path / "my-project")
        Path(project_path).mkdir(parents=True, exist_ok=True)

        features = [
            {"id": "feat-1", "name": "Feature One", "description": "First feature", "depends_on": []},
            {"id": "feat-2", "name": "Feature Two", "description": "Second feature", "depends_on": ["feat-1"]},
            {"id": "feat-3", "name": "Feature Three", "description": "Third feature", "depends_on": ["feat-1"]},
        ]

        result = forge_project_init(
            project_path=project_path,
            project_name="Test Project",
            features=features,
        )

        assert result["success"] is True
        assert "graph" in result
        assert result["graph"]["project_name"] == "Test Project"
        assert len(result["graph"]["features"]) == 3
        assert len(result["graph"]["dependency_order"]) == 3

    def test_project_status_shows_progress(self, tmp_path):
        """forge_project_status returns progress information."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_project_status

        project_path = str(tmp_path / "progress-project")
        Path(project_path).mkdir(parents=True, exist_ok=True)

        features = [
            {"id": "f1", "name": "Feature 1", "description": "Desc 1"},
            {"id": "f2", "name": "Feature 2", "description": "Desc 2"},
        ]

        forge_project_init(
            project_path=project_path,
            project_name="Progress Test",
            features=features,
        )

        result = forge_project_status(project_path=project_path)

        assert result["success"] is True
        assert result["progress"]["total_features"] == 2
        assert result["progress"]["completed_features"] == 0
        assert result["progress"]["completion_percentage"] == 0.0

    def test_feature_update_changes_status(self, tmp_path):
        """forge_feature_update modifies feature status."""
        from spellbook_mcp.forged.project_tools import (
            forge_project_init,
            forge_feature_update,
            forge_project_status,
        )

        project_path = str(tmp_path / "update-project")
        Path(project_path).mkdir(parents=True, exist_ok=True)

        features = [
            {"id": "f1", "name": "Feature 1", "description": "Desc 1"},
            {"id": "f2", "name": "Feature 2", "description": "Desc 2"},
        ]

        forge_project_init(
            project_path=project_path,
            project_name="Update Test",
            features=features,
        )

        # Update feature to complete
        result = forge_feature_update(
            project_path=project_path,
            feature_id="f1",
            status="complete",
        )

        assert result["success"] is True
        assert result["feature"]["status"] == "complete"

        # Check progress updated
        status = forge_project_status(project_path=project_path)
        assert status["progress"]["completed_features"] == 1
        assert status["progress"]["completion_percentage"] == 50.0


class TestCrossModuleIntegration:
    """Tests verifying modules work together correctly."""

    def test_full_workflow_with_project_and_iterations(self, tmp_path):
        """Project graph, iterations, and artifacts work together."""
        from spellbook_mcp.forged.project_tools import forge_project_init, forge_feature_update
        from spellbook_mcp.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        # Setup
        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        conn = get_forged_connection(str(db_path))

        project_path = str(tmp_path / "full-workflow")
        Path(project_path).mkdir(parents=True, exist_ok=True)

        # Initialize project
        features = [
            {"id": "auth", "name": "Authentication", "description": "User login"},
        ]
        init_result = forge_project_init(
            project_path=project_path,
            project_name="Full Workflow Test",
            features=features,
        )
        assert init_result["success"]

        # Start iteration for feature
        with patch("spellbook_mcp.forged.iteration_tools.get_forged_connection") as mock_conn:
            mock_conn.return_value = conn
            with patch("spellbook_mcp.forged.iteration_tools._get_project_path") as mock_project:
                mock_project.return_value = project_path

                # Mark feature as in progress
                forge_feature_update(
                    project_path=project_path,
                    feature_id="auth",
                    status="in_progress",
                    assigned_skill="implementing-features",
                )

                # Start iteration
                iter_result = forge_iteration_start(feature_name="auth")
                assert iter_result["status"] == "started"
                token = iter_result["token"]

                # Advance through stages
                for _ in range(4):  # DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE
                    iter_result = forge_iteration_advance(
                        feature_name="auth",
                        current_token=token
                    )
                    token = iter_result["token"]

                # Mark feature complete
                forge_feature_update(
                    project_path=project_path,
                    feature_id="auth",
                    status="complete",
                )

        # Verify final state
        from spellbook_mcp.forged.project_tools import forge_project_status
        status = forge_project_status(project_path=project_path)
        assert status["progress"]["completion_percentage"] == 100.0
