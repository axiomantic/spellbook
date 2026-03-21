"""Tests for forged.db ORM model definitions.

Verifies that SQLAlchemy models match the actual CREATE TABLE statements
in spellbook/forged/schema.py (the source of truth for forged.db schema).
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from spellbook.db.base import ForgedBase


class TestForgedModels:
    @pytest.fixture
    def engine(self):
        from spellbook.db.forged_models import (  # noqa: F401
            ForgeToken,
            ForgeReflection,
            GateCompletion,
            IterationState,
            ToolAnalytic,
        )

        engine = create_engine("sqlite:///:memory:")
        ForgedBase.metadata.create_all(engine)
        return engine

    def test_all_tables_created(self, engine):
        """All 5 forged.db tables are created by the ORM models."""
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        expected = {
            "forge_tokens",
            "iteration_state",
            "reflections",
            "tool_analytics",
            "gate_completions",
        }
        assert table_names == expected

    def test_forge_token_columns_and_to_dict(self, engine):
        """ForgeToken has id, feature_name, stage, created_at, invalidated_at.

        Does NOT have project_path, token_type, or value.
        """
        from spellbook.db.forged_models import ForgeToken

        with Session(engine) as session:
            token = ForgeToken(
                id="tok-1",
                feature_name="my-feature",
                stage="design",
                created_at="2026-03-20T10:00:00",
                invalidated_at=None,
            )
            session.add(token)
            session.commit()

            loaded = session.get(ForgeToken, "tok-1")
            d = loaded.to_dict()
            assert d == {
                "id": "tok-1",
                "feature_name": "my-feature",
                "stage": "design",
                "created_at": "2026-03-20T10:00:00",
                "invalidated_at": None,
            }
            # Verify absent columns
            assert "project_path" not in d
            assert "token_type" not in d
            assert "value" not in d

    def test_forge_token_column_inspection(self, engine):
        """ForgeToken table has exactly the expected columns in the DB."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("forge_tokens")}
        assert columns == {
            "id",
            "feature_name",
            "stage",
            "created_at",
            "invalidated_at",
        }

    def test_iteration_state_composite_pk_and_to_dict(self, engine):
        """IterationState has composite PK (project_path, feature_name) and individual state columns.

        Does NOT have state_json.
        """
        from spellbook.db.forged_models import IterationState

        with Session(engine) as session:
            state = IterationState(
                project_path="/test/project",
                feature_name="feat-1",
                iteration_number=3,
                current_stage="implement",
                accumulated_knowledge="learned things",
                feedback_history="round 1 feedback",
                artifacts_produced="design.md",
                preferences='{"tdd": true}',
                created_at="2026-03-20T09:00:00",
                updated_at="2026-03-20T10:00:00",
            )
            session.add(state)
            session.commit()

            loaded = session.get(IterationState, ("/test/project", "feat-1"))
            assert loaded is not None
            d = loaded.to_dict()
            assert d == {
                "project_path": "/test/project",
                "feature_name": "feat-1",
                "iteration_number": 3,
                "current_stage": "implement",
                "accumulated_knowledge": "learned things",
                "feedback_history": "round 1 feedback",
                "artifacts_produced": "design.md",
                "preferences": '{"tdd": true}',
                "created_at": "2026-03-20T09:00:00",
                "updated_at": "2026-03-20T10:00:00",
            }
            # Verify absent columns
            assert "state_json" not in d

    def test_iteration_state_column_inspection(self, engine):
        """iteration_state table has exactly the expected columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("iteration_state")}
        assert columns == {
            "project_path",
            "feature_name",
            "iteration_number",
            "current_stage",
            "accumulated_knowledge",
            "feedback_history",
            "artifacts_produced",
            "preferences",
            "created_at",
            "updated_at",
        }

    def test_reflection_columns_and_to_dict(self, engine):
        """ForgeReflection has validator, iteration, root_cause, lesson_learned, status.

        Does NOT have project_path, content, or reflection_type.
        """
        from spellbook.db.forged_models import ForgeReflection

        with Session(engine) as session:
            reflection = ForgeReflection(
                feature_name="feat-1",
                validator="test_suite",
                iteration=2,
                failure_description="tests failed on import",
                root_cause="missing import statement",
                lesson_learned="always check imports",
                status="RESOLVED",
                created_at="2026-03-20T09:00:00",
                resolved_at="2026-03-20T10:00:00",
            )
            session.add(reflection)
            session.commit()

            loaded = session.get(ForgeReflection, 1)
            d = loaded.to_dict()
            assert d == {
                "id": 1,
                "feature_name": "feat-1",
                "validator": "test_suite",
                "iteration": 2,
                "failure_description": "tests failed on import",
                "root_cause": "missing import statement",
                "lesson_learned": "always check imports",
                "status": "RESOLVED",
                "created_at": "2026-03-20T09:00:00",
                "resolved_at": "2026-03-20T10:00:00",
            }
            # Verify absent columns
            assert "project_path" not in d
            assert "content" not in d
            assert "reflection_type" not in d

    def test_reflection_column_inspection(self, engine):
        """reflections table has exactly the expected columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("reflections")}
        assert columns == {
            "id",
            "feature_name",
            "validator",
            "iteration",
            "failure_description",
            "root_cause",
            "lesson_learned",
            "status",
            "created_at",
            "resolved_at",
        }

    def test_tool_analytic_columns_and_to_dict(self, engine):
        """ToolAnalytic has project_path, input_tokens, output_tokens, called_at.

        Does NOT have session_id or created_at.
        """
        from spellbook.db.forged_models import ToolAnalytic

        with Session(engine) as session:
            analytic = ToolAnalytic(
                tool_name="Read",
                project_path="/test/project",
                feature_name="feat-1",
                stage="implement",
                iteration=1,
                input_tokens=100,
                output_tokens=50,
                duration_ms=200,
                success=1,
                called_at="2026-03-20T10:00:00",
            )
            session.add(analytic)
            session.commit()

            loaded = session.get(ToolAnalytic, 1)
            d = loaded.to_dict()
            assert d == {
                "id": 1,
                "tool_name": "Read",
                "project_path": "/test/project",
                "feature_name": "feat-1",
                "stage": "implement",
                "iteration": 1,
                "input_tokens": 100,
                "output_tokens": 50,
                "duration_ms": 200,
                "success": 1,
                "called_at": "2026-03-20T10:00:00",
            }
            # Verify absent columns
            assert "session_id" not in d
            assert "created_at" not in d

    def test_tool_analytic_column_inspection(self, engine):
        """tool_analytics table has exactly the expected columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("tool_analytics")}
        assert columns == {
            "id",
            "tool_name",
            "project_path",
            "feature_name",
            "stage",
            "iteration",
            "input_tokens",
            "output_tokens",
            "duration_ms",
            "success",
            "called_at",
        }

    def test_gate_completion_columns_and_to_dict(self, engine):
        """GateCompletion has gate (not gate_name), stage, consensus, iteration, verdict_summary.

        Does NOT have gate_name.
        """
        from spellbook.db.forged_models import GateCompletion

        with Session(engine) as session:
            completion = GateCompletion(
                project_path="/test/project",
                feature_name="feat-1",
                gate="design-review",
                stage="design",
                consensus=1,
                iteration=2,
                verdict_summary="Approved with minor changes",
                completed_at="2026-03-20T10:00:00",
            )
            session.add(completion)
            session.commit()

            loaded = session.get(GateCompletion, 1)
            d = loaded.to_dict()
            assert d == {
                "id": 1,
                "project_path": "/test/project",
                "feature_name": "feat-1",
                "gate": "design-review",
                "stage": "design",
                "consensus": 1,
                "iteration": 2,
                "verdict_summary": "Approved with minor changes",
                "completed_at": "2026-03-20T10:00:00",
            }
            # Verify absent columns
            assert "gate_name" not in d

    def test_gate_completion_column_inspection(self, engine):
        """gate_completions table has exactly the expected columns."""
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("gate_completions")}
        assert columns == {
            "id",
            "project_path",
            "feature_name",
            "gate",
            "stage",
            "consensus",
            "iteration",
            "verdict_summary",
            "completed_at",
        }

    def test_forge_token_indexes(self, engine):
        """ForgeToken has indexes on feature_name and stage."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("forge_tokens")
        indexed_cols = {
            tuple(idx["column_names"]) for idx in indexes
        }
        assert ("feature_name",) in indexed_cols
        assert ("stage",) in indexed_cols

    def test_iteration_state_indexes(self, engine):
        """IterationState has index on current_stage."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("iteration_state")
        indexed_cols = {
            tuple(idx["column_names"]) for idx in indexes
        }
        assert ("current_stage",) in indexed_cols

    def test_reflection_indexes(self, engine):
        """ForgeReflection has indexes on feature_name, status, validator."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("reflections")
        indexed_cols = {
            tuple(idx["column_names"]) for idx in indexes
        }
        assert ("feature_name",) in indexed_cols
        assert ("status",) in indexed_cols
        assert ("validator",) in indexed_cols

    def test_tool_analytic_indexes(self, engine):
        """ToolAnalytic has indexes on tool_name, project_path, called_at."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("tool_analytics")
        indexed_cols = {
            tuple(idx["column_names"]) for idx in indexes
        }
        assert ("tool_name",) in indexed_cols
        assert ("project_path",) in indexed_cols
        assert ("called_at",) in indexed_cols

    def test_gate_completion_indexes(self, engine):
        """GateCompletion has composite indexes on (project_path, feature_name) and (project_path, feature_name, gate)."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes("gate_completions")
        indexed_cols = {
            tuple(idx["column_names"]) for idx in indexes
        }
        assert ("project_path", "feature_name") in indexed_cols
        assert ("project_path", "feature_name", "gate") in indexed_cols

    def test_reflection_default_status(self, engine):
        """ForgeReflection defaults status to PENDING when not specified."""
        from spellbook.db.forged_models import ForgeReflection

        with Session(engine) as session:
            reflection = ForgeReflection(
                feature_name="feat-2",
                validator="lint",
                iteration=1,
            )
            session.add(reflection)
            session.commit()
            session.refresh(reflection)
            assert reflection.status == "PENDING"

    def test_tool_analytic_default_success(self, engine):
        """ToolAnalytic defaults success to 1 when not specified."""
        from spellbook.db.forged_models import ToolAnalytic

        with Session(engine) as session:
            analytic = ToolAnalytic(
                tool_name="Bash",
                project_path="/test",
            )
            session.add(analytic)
            session.commit()
            session.refresh(analytic)
            assert analytic.success == 1

    def test_gate_completion_defaults(self, engine):
        """GateCompletion defaults consensus to 0 and iteration to 1."""
        from spellbook.db.forged_models import GateCompletion

        with Session(engine) as session:
            completion = GateCompletion(
                project_path="/test",
                feature_name="feat-1",
                gate="review",
                stage="design",
            )
            session.add(completion)
            session.commit()
            session.refresh(completion)
            assert completion.consensus == 0
            assert completion.iteration == 1
