"""Tests for forge_record_gate_completion ORM migration.

Verifies that forge_record_gate_completion uses async SQLAlchemy
sessions and GateCompletion ORM model instead of raw sqlite3.
"""

import pytest
from sqlalchemy import select

from spellbook.db.forged_models import GateCompletion
from spellbook.forged.models import VALID_GATES


@pytest.mark.asyncio
class TestForgeRecordGateCompletionORM:
    """forge_record_gate_completion must use ORM session."""

    async def test_records_gate_completion(self, forged_session):
        """Gate completion is persisted as a GateCompletion ORM object."""
        from spellbook.forged.project_tools import forge_record_gate_completion

        result = await forge_record_gate_completion(
            feature_name="my-feature",
            gate=VALID_GATES[0],
            stage="DESIGN",
            consensus=True,
            iteration=2,
            verdict_summary='{"approved": true}',
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "recorded"
        assert result["feature_name"] == "my-feature"
        assert result["gate"] == VALID_GATES[0]
        assert result["consensus"] is True
        assert isinstance(result["gate_id"], int)
        assert result["gate_id"] > 0

        # Verify ORM object in DB
        stmt = select(GateCompletion).where(
            GateCompletion.id == result["gate_id"]
        )
        row = (await forged_session.execute(stmt)).scalar_one()

        assert row.project_path == "/test/project"
        assert row.feature_name == "my-feature"
        assert row.gate == VALID_GATES[0]
        assert row.stage == "DESIGN"
        assert row.consensus == 1
        assert row.iteration == 2
        assert row.verdict_summary == '{"approved": true}'
        assert row.completed_at is not None

    async def test_rejects_invalid_gate(self, forged_session):
        """Invalid gate names are rejected before DB write."""
        from spellbook.forged.project_tools import forge_record_gate_completion

        result = await forge_record_gate_completion(
            feature_name="my-feature",
            gate="INVALID_GATE",
            stage="DESIGN",
            consensus=True,
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "Invalid gate" in result["error"]

    async def test_consensus_false_stored_as_zero(self, forged_session):
        """consensus=False stored as integer 0 in DB."""
        from spellbook.forged.project_tools import forge_record_gate_completion

        result = await forge_record_gate_completion(
            feature_name="feat",
            gate=VALID_GATES[0],
            stage="PLAN",
            consensus=False,
            project_path="/test",
            session=forged_session,
        )

        stmt = select(GateCompletion).where(
            GateCompletion.id == result["gate_id"]
        )
        row = (await forged_session.execute(stmt)).scalar_one()
        assert row.consensus == 0

    async def test_default_iteration_is_one(self, forged_session):
        """Default iteration is 1 when not specified."""
        from spellbook.forged.project_tools import forge_record_gate_completion

        result = await forge_record_gate_completion(
            feature_name="feat",
            gate=VALID_GATES[0],
            stage="IMPLEMENT",
            consensus=True,
            project_path="/test",
            session=forged_session,
        )

        stmt = select(GateCompletion).where(
            GateCompletion.id == result["gate_id"]
        )
        row = (await forged_session.execute(stmt)).scalar_one()
        assert row.iteration == 1

    async def test_verdict_summary_none(self, forged_session):
        """verdict_summary can be None."""
        from spellbook.forged.project_tools import forge_record_gate_completion

        result = await forge_record_gate_completion(
            feature_name="feat",
            gate=VALID_GATES[0],
            stage="DISCOVER",
            consensus=True,
            project_path="/test",
            session=forged_session,
        )

        stmt = select(GateCompletion).where(
            GateCompletion.id == result["gate_id"]
        )
        row = (await forged_session.execute(stmt)).scalar_one()
        assert row.verdict_summary is None
