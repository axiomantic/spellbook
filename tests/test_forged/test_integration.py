"""Integration tests for Forged autonomous development system.

Updated for ORM migration: tests use async ORM sessions.

These tests verify the complete workflow integration:
1. Schema initialization (legacy raw SQL tests kept for schema.py)
2. Full feature lifecycle (init -> advance -> complete)
3. ITERATE verdict flow
4. Roundtable convene/response cycle
"""

import json
import pytest
from pathlib import Path

from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from spellbook.db.base import ForgedBase


@pytest.fixture
async def forged_session():
    """Create in-memory forged session for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    def _pragmas(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sa_event.listen(engine.sync_engine, "connect", _pragmas)

    async with engine.begin() as conn:
        await conn.run_sync(ForgedBase.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


pytestmark = pytest.mark.asyncio


class TestSchemaIntegration:
    """Tests for schema initialization during server startup (legacy raw SQL)."""

    def test_schema_initializes_all_tables(self, tmp_path):
        """Schema initialization creates all required tables."""
        from spellbook.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()

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
        from spellbook.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))
        init_forged_schema(str(db_path))
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        count = cursor.fetchone()[0]
        assert count == 1

    def test_schema_records_version(self, tmp_path):
        """Schema version is recorded in the database."""
        from spellbook.forged.schema import init_forged_schema, get_forged_connection
        from spellbook.forged.models import SCHEMA_VERSION

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        version = cursor.fetchone()[0]
        assert version == SCHEMA_VERSION


class TestCompleteFeatureLifecycle:
    """Tests for full feature flow using async ORM."""

    async def test_feature_flows_through_all_stages(self, forged_session):
        """A feature can flow through DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        result = await forge_iteration_start(
            feature_name="complete-flow-test",
            project_path="/test/project",
            session=forged_session,
        )
        assert result["status"] == "started"
        assert result["current_stage"] == "DISCOVER"
        token = result["token"]
        stages = [result["current_stage"]]

        for expected_next in ["DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]:
            result = await forge_iteration_advance(
                feature_name="complete-flow-test",
                current_token=token,
                evidence={"stage_completed": True},
                project_path="/test/project",
                session=forged_session,
            )
            assert result["status"] == "advanced", f"Failed advancing to {expected_next}: {result}"
            assert result["current_stage"] == expected_next
            stages.append(result["current_stage"])
            token = result["token"]

        assert stages == ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]

    async def test_feature_with_evidence_accumulation(self, forged_session):
        """Evidence is accumulated as feature progresses through stages."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance
        from spellbook.db.forged_models import IterationState
        from sqlalchemy import select

        result = await forge_iteration_start(
            feature_name="evidence-test",
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        await forge_iteration_advance(
            feature_name="evidence-test",
            current_token=token,
            evidence={"discover_findings": ["Pattern A found"]},
            project_path="/test/project",
            session=forged_session,
        )

        stmt = select(IterationState).where(IterationState.feature_name == "evidence-test")
        state = (await forged_session.execute(stmt)).scalar_one()
        knowledge = json.loads(state.accumulated_knowledge)
        assert "discover_evidence" in knowledge


class TestIterateVerdictFlow:
    """Tests for ITERATE verdict triggering return flow."""

    async def test_iterate_returns_to_earlier_stage(self, forged_session):
        """ITERATE verdict causes return to specified stage with incremented iteration."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return,
        )

        result = await forge_iteration_start(
            feature_name="iterate-test",
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]
        assert result["iteration_number"] == 1

        result = await forge_iteration_advance(
            feature_name="iterate-test",
            current_token=token,
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        result = await forge_iteration_advance(
            feature_name="iterate-test",
            current_token=token,
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        result = await forge_iteration_return(
            feature_name="iterate-test",
            current_token=token,
            return_to="DESIGN",
            feedback=[{
                "source": "plan-validator",
                "critique": "Design doesn't cover edge case X",
                "evidence": "Missing handler for null input",
                "suggestion": "Add null check in design",
                "severity": "blocking",
            }],
            reflection="Need to be more thorough with edge cases",
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "returned"
        assert result["previous_stage"] == "PLAN"
        assert result["current_stage"] == "DESIGN"
        assert result["iteration_number"] == 2

    async def test_multiple_iterations_track_history(self, forged_session):
        """Multiple iterate cycles accumulate feedback history."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return,
        )
        from spellbook.db.forged_models import IterationState
        from sqlalchemy import select

        result = await forge_iteration_start(
            feature_name="multi-iterate",
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        result = await forge_iteration_advance(
            feature_name="multi-iterate",
            current_token=token,
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        result = await forge_iteration_return(
            feature_name="multi-iterate",
            current_token=token,
            return_to="DISCOVER",
            feedback=[{"source": "v1", "critique": "Issue 1", "evidence": "e1", "suggestion": "s1", "severity": "blocking"}],
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]
        assert result["iteration_number"] == 2

        result = await forge_iteration_advance(
            feature_name="multi-iterate",
            current_token=token,
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        result = await forge_iteration_return(
            feature_name="multi-iterate",
            current_token=token,
            return_to="DISCOVER",
            feedback=[{"source": "v2", "critique": "Issue 2", "evidence": "e2", "suggestion": "s2", "severity": "minor"}],
            project_path="/test/project",
            session=forged_session,
        )
        assert result["iteration_number"] == 3

        stmt = select(IterationState).where(IterationState.feature_name == "multi-iterate")
        state = (await forged_session.execute(stmt)).scalar_one()
        feedback_history = json.loads(state.feedback_history)
        assert len(feedback_history) == 2
        assert feedback_history[0]["source"] == "v1"
        assert feedback_history[1]["source"] == "v2"


class TestRoundtableEndToEnd:
    """Tests for roundtable convene/response cycle."""

    def test_roundtable_convene_generates_prompt(self, tmp_path):
        """roundtable_convene generates a valid prompt with archetypes."""
        from spellbook.forged.roundtable import roundtable_convene

        artifact_path = tmp_path / "test-artifact.md"
        artifact_path.write_text("# Test Design\n\nThis is a test design document.")

        result = roundtable_convene(
            feature_name="test-feature",
            stage="DESIGN",
            artifact_path=str(artifact_path),
            gate="code_review",
        )

        assert "dialogue" in result
        assert result["dialogue"]
        assert "test-feature" in result["dialogue"]
        assert "DESIGN" in result["dialogue"]
        assert "Test Design" in result["dialogue"]
        assert "archetypes" in result
        assert len(result["archetypes"]) > 0

    async def test_process_roundtable_response_all_approve(self, tmp_path):
        """Processing response with all APPROVE verdicts returns consensus True."""
        from spellbook.forged.roundtable import process_roundtable_response

        response = """
        **Magician**: The implementation looks solid. Types are correct.

        Concerns:
        - None

        Suggestions:
        - None

        Verdict: APPROVE

        **Hermit**: Deep analysis reveals sound architecture.

        Verdict: APPROVE

        **Justice**: Both perspectives agree.

        Verdict: APPROVE
        """

        result = await process_roundtable_response(
            response=response,
            stage="IMPLEMENT",
            gate="test_suite",
            feature_name="test-feature",
            iteration=1,
        )

        assert result["consensus"] is True
        assert result["return_to"] is None
        assert len(result["feedback"]) == 0

    async def test_process_roundtable_response_with_iterate(self, tmp_path):
        """Processing response with ITERATE verdict returns consensus False with feedback."""
        from spellbook.forged.roundtable import process_roundtable_response

        response = """
        **Magician**: Code has technical issues.

        Concerns:
        - Missing error handling for edge case X

        Suggestions:
        - Add try-catch block

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

        result = await process_roundtable_response(
            response=response,
            stage="IMPLEMENT",
            gate="code_review",
            feature_name="test-feature",
            iteration=2,
        )

        assert result["consensus"] is False
        assert result["return_to"] == "IMPLEMENT"
        assert len(result["feedback"]) > 0

        feedback_sources = [fb["source"] for fb in result["feedback"]]
        assert any("Magician" in src for src in feedback_sources)


class TestProjectGraphIntegration:
    """Tests for project graph initialization and updates."""

    def test_project_init_creates_graph(self, tmp_path):
        """forge_project_init creates a valid project graph."""
        from spellbook.forged.project_tools import forge_project_init

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

    def test_feature_update_changes_status(self, tmp_path):
        """forge_feature_update modifies feature status."""
        from spellbook.forged.project_tools import (
            forge_project_init, forge_feature_update, forge_project_status,
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

        result = forge_feature_update(
            project_path=project_path,
            feature_id="f1",
            status="complete",
        )

        assert result["success"] is True
        assert result["feature"]["status"] == "complete"

        status = forge_project_status(project_path=project_path)
        assert status["progress"]["completed_features"] == 1
        assert status["progress"]["completion_percentage"] == 50.0
