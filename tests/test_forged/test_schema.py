"""Tests for Forged database schema and models.

Following TDD: these tests are written BEFORE implementation.
"""

import pytest
import sqlite3
import json
from pathlib import Path
from datetime import datetime


class TestSchemaVersion:
    """Tests for schema_version table and versioning."""

    def test_init_forged_schema_creates_schema_version_table(self, tmp_path):
        """schema_version table must exist after initialization."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_schema_version_has_correct_columns(self, tmp_path):
        """schema_version table must have version and applied_at columns."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(schema_version)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "version" in columns
        assert "INTEGER" in columns["version"].upper()
        assert "applied_at" in columns
        assert "TEXT" in columns["applied_at"].upper()
        conn.close()

    def test_schema_version_recorded_on_init(self, tmp_path):
        """Schema version must be recorded during initialization."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection
        from spellbook_mcp.forged.models import SCHEMA_VERSION

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == SCHEMA_VERSION
        conn.close()


class TestForgeTokensTable:
    """Tests for forge_tokens table."""

    def test_forge_tokens_table_exists(self, tmp_path):
        """forge_tokens table must exist after initialization."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='forge_tokens'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_forge_tokens_has_required_columns(self, tmp_path):
        """forge_tokens table must have all required columns."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(forge_tokens)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "feature_name" in columns
        assert "stage" in columns
        assert "created_at" in columns
        assert "invalidated_at" in columns
        conn.close()

    def test_forge_tokens_id_is_primary_key(self, tmp_path):
        """forge_tokens.id must be the primary key."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(forge_tokens)")
        columns = {row[1]: row[5] for row in cursor.fetchall()}  # row[5] is pk flag

        assert columns["id"] == 1  # pk flag = 1 means it's the primary key
        conn.close()


class TestIterationStateTable:
    """Tests for iteration_state table."""

    def test_iteration_state_table_exists(self, tmp_path):
        """iteration_state table must exist after initialization."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='iteration_state'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_iteration_state_has_required_columns(self, tmp_path):
        """iteration_state table must have all required columns."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(iteration_state)")
        columns = {row[1] for row in cursor.fetchall()}

        expected = {
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
        assert expected.issubset(columns)
        conn.close()

    def test_iteration_state_composite_primary_key(self, tmp_path):
        """iteration_state must have composite primary key on (project_path, feature_name)."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()

        # Insert a row
        cursor.execute("""
            INSERT INTO iteration_state (project_path, feature_name, iteration_number, current_stage)
            VALUES ('/test/path', 'test-feature', 1, 'DISCOVER')
        """)

        # Attempt duplicate insert should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO iteration_state (project_path, feature_name, iteration_number, current_stage)
                VALUES ('/test/path', 'test-feature', 2, 'DESIGN')
            """)
        conn.close()


class TestReflectionsTable:
    """Tests for reflections table."""

    def test_reflections_table_exists(self, tmp_path):
        """reflections table must exist after initialization."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reflections'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_reflections_has_required_columns(self, tmp_path):
        """reflections table must have all required columns."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reflections)")
        columns = {row[1] for row in cursor.fetchall()}

        expected = {
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
        assert expected.issubset(columns)
        conn.close()

    def test_reflections_id_autoincrement(self, tmp_path):
        """reflections.id must autoincrement."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reflections (feature_name, validator, iteration, status)
            VALUES ('feat1', 'lint', 1, 'PENDING')
        """)
        cursor.execute("""
            INSERT INTO reflections (feature_name, validator, iteration, status)
            VALUES ('feat2', 'test', 2, 'RESOLVED')
        """)

        cursor.execute("SELECT id FROM reflections ORDER BY id")
        ids = [row[0] for row in cursor.fetchall()]

        assert ids[0] < ids[1]  # IDs should be incrementing
        conn.close()


class TestToolAnalyticsTable:
    """Tests for tool_analytics table."""

    def test_tool_analytics_table_exists(self, tmp_path):
        """tool_analytics table must exist after initialization."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tool_analytics'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_tool_analytics_has_required_columns(self, tmp_path):
        """tool_analytics table must have all required columns."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tool_analytics)")
        columns = {row[1] for row in cursor.fetchall()}

        expected = {
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
        assert expected.issubset(columns)
        conn.close()


class TestWALMode:
    """Tests for WAL mode configuration."""

    def test_wal_mode_enabled(self, tmp_path):
        """WAL mode must be enabled for concurrent access."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"
        init_forged_schema(str(db_path))

        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()[0]

        assert result.upper() == "WAL"
        conn.close()


class TestIdempotency:
    """Tests for schema initialization idempotency."""

    def test_init_forged_schema_idempotent(self, tmp_path):
        """Calling init_forged_schema multiple times should not error."""
        from spellbook_mcp.forged.schema import init_forged_schema, get_forged_connection

        db_path = tmp_path / "forged.db"

        # Call init multiple times
        init_forged_schema(str(db_path))
        init_forged_schema(str(db_path))
        init_forged_schema(str(db_path))

        # Should still work
        conn = get_forged_connection(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        count = cursor.fetchone()[0]

        # Should only have one version record
        assert count == 1
        conn.close()


class TestFeedbackModel:
    """Tests for Feedback dataclass."""

    def test_feedback_creation(self):
        """Feedback must be creatable with all required fields."""
        from spellbook_mcp.forged.models import Feedback

        feedback = Feedback(
            source="lint-validator",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Type mismatch in function call",
            evidence="Line 42: expected str, got int",
            suggestion="Cast to string or change parameter type",
            severity="blocking",
            iteration=1,
        )

        assert feedback.source == "lint-validator"
        assert feedback.stage == "IMPLEMENT"
        assert feedback.severity == "blocking"

    def test_feedback_to_dict(self):
        """Feedback.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.models import Feedback

        feedback = Feedback(
            source="test-validator",
            stage="IMPLEMENT",
            return_to="DESIGN",
            critique="Tests failing",
            evidence="3 tests failed",
            suggestion="Review test cases",
            severity="significant",
            iteration=2,
        )

        d = feedback.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        # Must have all fields
        assert d["source"] == "test-validator"
        assert d["severity"] == "significant"
        assert d["iteration"] == 2

    def test_feedback_from_dict(self):
        """Feedback.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.models import Feedback

        data = {
            "source": "review-validator",
            "stage": "DESIGN",
            "return_to": "DISCOVER",
            "critique": "Missing edge case",
            "evidence": "No handling for empty input",
            "suggestion": "Add validation",
            "severity": "minor",
            "iteration": 3,
        }

        feedback = Feedback.from_dict(data)

        assert feedback.source == "review-validator"
        assert feedback.stage == "DESIGN"
        assert feedback.severity == "minor"
        assert feedback.iteration == 3

    def test_feedback_roundtrip(self):
        """Feedback must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.models import Feedback

        original = Feedback(
            source="roundtrip-test",
            stage="PLAN",
            return_to="DESIGN",
            critique="Test critique",
            evidence="Test evidence",
            suggestion="Test suggestion",
            severity="blocking",
            iteration=5,
        )

        reconstructed = Feedback.from_dict(original.to_dict())

        assert reconstructed.source == original.source
        assert reconstructed.stage == original.stage
        assert reconstructed.return_to == original.return_to
        assert reconstructed.critique == original.critique
        assert reconstructed.evidence == original.evidence
        assert reconstructed.suggestion == original.suggestion
        assert reconstructed.severity == original.severity
        assert reconstructed.iteration == original.iteration


class TestValidatorResultModel:
    """Tests for ValidatorResult dataclass."""

    def test_validator_result_approved(self):
        """ValidatorResult with APPROVED verdict must work."""
        from spellbook_mcp.forged.models import ValidatorResult

        result = ValidatorResult(
            verdict="APPROVED",
            feedback=None,
            transformed=False,
            artifact_path="/path/to/file.py",
            artifact_hash="abc123",
            transform_description=None,
            error=None,
        )

        assert result.verdict == "APPROVED"
        assert result.feedback is None

    def test_validator_result_with_feedback(self):
        """ValidatorResult with FEEDBACK verdict must include feedback."""
        from spellbook_mcp.forged.models import ValidatorResult, Feedback

        feedback = Feedback(
            source="test",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="Issue found",
            evidence="Line 10",
            suggestion="Fix it",
            severity="blocking",
            iteration=1,
        )

        result = ValidatorResult(
            verdict="FEEDBACK",
            feedback=feedback,
            transformed=False,
            artifact_path="/path/to/file.py",
            artifact_hash="def456",
            transform_description=None,
            error=None,
        )

        assert result.verdict == "FEEDBACK"
        assert result.feedback is not None
        assert result.feedback.severity == "blocking"

    def test_validator_result_to_dict(self):
        """ValidatorResult.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.models import ValidatorResult, Feedback

        feedback = Feedback(
            source="test",
            stage="IMPLEMENT",
            return_to="DESIGN",
            critique="Type error",
            evidence="Line 42",
            suggestion="Fix type",
            severity="significant",
            iteration=2,
        )

        result = ValidatorResult(
            verdict="FEEDBACK",
            feedback=feedback,
            transformed=True,
            artifact_path="/path/file.py",
            artifact_hash="hash123",
            transform_description="Auto-formatted code",
            error=None,
        )

        d = result.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        assert d["verdict"] == "FEEDBACK"
        assert d["transformed"] is True
        assert d["feedback"]["severity"] == "significant"

    def test_validator_result_from_dict(self):
        """ValidatorResult.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.models import ValidatorResult

        data = {
            "verdict": "APPROVED",
            "feedback": None,
            "transformed": False,
            "artifact_path": "/test/path.py",
            "artifact_hash": "xyz789",
            "transform_description": None,
            "error": None,
        }

        result = ValidatorResult.from_dict(data)

        assert result.verdict == "APPROVED"
        assert result.feedback is None
        assert result.artifact_hash == "xyz789"

    def test_validator_result_from_dict_with_feedback(self):
        """ValidatorResult.from_dict() must reconstruct nested feedback."""
        from spellbook_mcp.forged.models import ValidatorResult

        data = {
            "verdict": "FEEDBACK",
            "feedback": {
                "source": "nested-test",
                "stage": "PLAN",
                "return_to": "DISCOVER",
                "critique": "Nested critique",
                "evidence": "Nested evidence",
                "suggestion": "Nested suggestion",
                "severity": "minor",
                "iteration": 4,
            },
            "transformed": False,
            "artifact_path": "/nested/path.py",
            "artifact_hash": "nested123",
            "transform_description": None,
            "error": None,
        }

        result = ValidatorResult.from_dict(data)

        assert result.verdict == "FEEDBACK"
        assert result.feedback is not None
        assert result.feedback.source == "nested-test"
        assert result.feedback.severity == "minor"

    def test_validator_result_roundtrip(self):
        """ValidatorResult must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.models import ValidatorResult, Feedback

        feedback = Feedback(
            source="roundtrip",
            stage="IMPLEMENT",
            return_to="PLAN",
            critique="Roundtrip critique",
            evidence="Roundtrip evidence",
            suggestion="Roundtrip suggestion",
            severity="blocking",
            iteration=7,
        )

        original = ValidatorResult(
            verdict="FEEDBACK",
            feedback=feedback,
            transformed=True,
            artifact_path="/roundtrip/file.py",
            artifact_hash="roundtrip123",
            transform_description="Transformed during roundtrip",
            error=None,
        )

        reconstructed = ValidatorResult.from_dict(original.to_dict())

        assert reconstructed.verdict == original.verdict
        assert reconstructed.feedback.source == original.feedback.source
        assert reconstructed.transformed == original.transformed
        assert reconstructed.artifact_hash == original.artifact_hash


class TestIterationStateModel:
    """Tests for IterationState dataclass."""

    def test_iteration_state_creation(self):
        """IterationState must be creatable with required fields."""
        from spellbook_mcp.forged.models import IterationState

        state = IterationState(
            iteration_number=1,
            current_stage="DISCOVER",
        )

        assert state.iteration_number == 1
        assert state.current_stage == "DISCOVER"
        assert state.feedback_history == []
        assert state.accumulated_knowledge == {}
        assert state.artifacts_produced == []
        assert state.preferences == {}

    def test_iteration_state_with_feedback_history(self):
        """IterationState must handle feedback_history correctly."""
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback1 = Feedback(
            source="v1",
            stage="IMPLEMENT",
            return_to="IMPLEMENT",
            critique="First issue",
            evidence="Line 1",
            suggestion="Fix 1",
            severity="minor",
            iteration=1,
        )
        feedback2 = Feedback(
            source="v2",
            stage="IMPLEMENT",
            return_to="DESIGN",
            critique="Second issue",
            evidence="Line 2",
            suggestion="Fix 2",
            severity="blocking",
            iteration=1,
        )

        state = IterationState(
            iteration_number=2,
            current_stage="IMPLEMENT",
            feedback_history=[feedback1, feedback2],
        )

        assert len(state.feedback_history) == 2
        assert state.feedback_history[0].source == "v1"
        assert state.feedback_history[1].severity == "blocking"

    def test_iteration_state_to_dict(self):
        """IterationState.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback = Feedback(
            source="test",
            stage="DESIGN",
            return_to="DISCOVER",
            critique="Test",
            evidence="Test",
            suggestion="Test",
            severity="minor",
            iteration=1,
        )

        state = IterationState(
            iteration_number=3,
            current_stage="PLAN",
            feedback_history=[feedback],
            accumulated_knowledge={"key": "value"},
            artifacts_produced=["/path/to/file.py"],
            preferences={"prefer_verbose": True},
            started_at="2025-01-01T00:00:00",
        )

        d = state.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        assert d["iteration_number"] == 3
        assert d["current_stage"] == "PLAN"
        assert len(d["feedback_history"]) == 1
        assert d["accumulated_knowledge"]["key"] == "value"

    def test_iteration_state_from_dict(self):
        """IterationState.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.models import IterationState

        data = {
            "iteration_number": 5,
            "current_stage": "IMPLEMENT",
            "feedback_history": [],
            "accumulated_knowledge": {"learned": "something"},
            "artifacts_produced": ["/a.py", "/b.py"],
            "preferences": {"strict": True},
            "started_at": "2025-06-15T12:00:00",
        }

        state = IterationState.from_dict(data)

        assert state.iteration_number == 5
        assert state.current_stage == "IMPLEMENT"
        assert state.accumulated_knowledge["learned"] == "something"
        assert len(state.artifacts_produced) == 2

    def test_iteration_state_from_dict_with_feedback(self):
        """IterationState.from_dict() must reconstruct nested feedback."""
        from spellbook_mcp.forged.models import IterationState

        data = {
            "iteration_number": 2,
            "current_stage": "DESIGN",
            "feedback_history": [
                {
                    "source": "nested",
                    "stage": "DISCOVER",
                    "return_to": "DISCOVER",
                    "critique": "Nested",
                    "evidence": "Nested",
                    "suggestion": "Nested",
                    "severity": "significant",
                    "iteration": 1,
                }
            ],
            "accumulated_knowledge": {},
            "artifacts_produced": [],
            "preferences": {},
            "started_at": "",
        }

        state = IterationState.from_dict(data)

        assert len(state.feedback_history) == 1
        assert state.feedback_history[0].source == "nested"
        assert state.feedback_history[0].severity == "significant"

    def test_iteration_state_roundtrip(self):
        """IterationState must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.models import IterationState, Feedback

        feedback = Feedback(
            source="roundtrip",
            stage="PLAN",
            return_to="DESIGN",
            critique="Roundtrip",
            evidence="Roundtrip",
            suggestion="Roundtrip",
            severity="blocking",
            iteration=3,
        )

        original = IterationState(
            iteration_number=10,
            current_stage="COMPLETE",
            feedback_history=[feedback],
            accumulated_knowledge={"final": "state"},
            artifacts_produced=["/final/file.py"],
            preferences={"done": True},
            started_at="2025-12-31T23:59:59",
        )

        reconstructed = IterationState.from_dict(original.to_dict())

        assert reconstructed.iteration_number == original.iteration_number
        assert reconstructed.current_stage == original.current_stage
        assert len(reconstructed.feedback_history) == 1
        assert reconstructed.feedback_history[0].source == "roundtrip"
        assert reconstructed.accumulated_knowledge["final"] == "state"


class TestConstants:
    """Tests for module constants."""

    def test_schema_version_defined(self):
        """SCHEMA_VERSION must be defined as integer."""
        from spellbook_mcp.forged.models import SCHEMA_VERSION

        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION >= 1

    def test_valid_stages_defined(self):
        """VALID_STAGES must contain all workflow stages."""
        from spellbook_mcp.forged.models import VALID_STAGES

        expected = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE", "ESCALATED"]
        assert VALID_STAGES == expected

    def test_valid_severities_defined(self):
        """VALID_SEVERITIES must contain all severity levels."""
        from spellbook_mcp.forged.models import VALID_SEVERITIES

        expected = ["blocking", "significant", "minor"]
        assert VALID_SEVERITIES == expected

    def test_valid_verdicts_defined(self):
        """VALID_VERDICTS must contain all verdict types."""
        from spellbook_mcp.forged.models import VALID_VERDICTS

        expected = ["APPROVED", "FEEDBACK", "ABSTAIN", "ERROR"]
        assert VALID_VERDICTS == expected


class TestGetForgedDbPath:
    """Tests for get_forged_db_path function."""

    def test_get_forged_db_path_returns_path(self):
        """get_forged_db_path must return a Path object."""
        from spellbook_mcp.forged.schema import get_forged_db_path

        db_path = get_forged_db_path()

        assert isinstance(db_path, Path)
        assert db_path.name == "forged.db"

    def test_get_forged_db_path_in_spellbook_dir(self):
        """get_forged_db_path must be in ~/.local/spellbook/."""
        from spellbook_mcp.forged.schema import get_forged_db_path

        db_path = get_forged_db_path()

        # Should be ~/.local/spellbook/forged.db
        assert db_path.parent.name == "spellbook"
        assert db_path.parent.parent.name == ".local"
