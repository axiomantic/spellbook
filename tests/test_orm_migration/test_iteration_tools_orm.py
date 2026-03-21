"""Tests for iteration_tools ORM migration.

Verifies that forge_iteration_start, forge_iteration_advance, and
forge_iteration_return use async SQLAlchemy sessions with ForgeToken,
IterationState (ORM), and ForgeReflection models.
"""

import json

import pytest
from sqlalchemy import select

from spellbook.db.forged_models import (
    ForgeToken,
    GateCompletion,
    IterationState as IterationStateORM,
    ForgeReflection,
)


@pytest.mark.asyncio
class TestForgeIterationStartORM:
    """forge_iteration_start must use ORM session."""

    async def test_start_creates_new_state(self, forged_session):
        """Starting creates IterationState and ForgeToken ORM objects."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "started"
        assert result["feature_name"] == "my-feature"
        assert result["current_stage"] == "DISCOVER"
        assert result["iteration_number"] == 1
        assert result["token"] is not None

        # Verify IterationState ORM object
        stmt = select(IterationStateORM).where(
            IterationStateORM.project_path == "/test/project",
            IterationStateORM.feature_name == "my-feature",
        )
        state = (await forged_session.execute(stmt)).scalar_one()
        assert state.iteration_number == 1
        assert state.current_stage == "DISCOVER"

        # Verify ForgeToken ORM object
        stmt = select(ForgeToken).where(ForgeToken.id == result["token"])
        token = (await forged_session.execute(stmt)).scalar_one()
        assert token.feature_name == "my-feature"
        assert token.stage == "DISCOVER"
        assert token.invalidated_at is None

    async def test_start_with_custom_stage(self, forged_session):
        """Starting with custom stage persists correctly."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result = await forge_iteration_start(
            feature_name="feat",
            starting_stage="DESIGN",
            project_path="/test",
            session=forged_session,
        )

        assert result["current_stage"] == "DESIGN"

    async def test_start_rejects_invalid_stage(self, forged_session):
        """Invalid stage returns error without DB write."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result = await forge_iteration_start(
            feature_name="feat",
            starting_stage="INVALID",
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "invalid stage" in result["error"].lower()

    async def test_start_resumes_existing(self, forged_session):
        """Starting for existing feature resumes from current state."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        # First start
        await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )

        # Second start resumes
        result = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "resumed"
        assert result["current_stage"] == "DISCOVER"
        assert result["iteration_number"] == 1

    async def test_start_invalidates_old_tokens(self, forged_session):
        """Starting invalidates previous tokens for the feature."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result1 = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        token1 = result1["token"]

        result2 = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        token2 = result2["token"]

        # Token 1 should be invalidated
        stmt = select(ForgeToken).where(ForgeToken.id == token1)
        t1 = (await forged_session.execute(stmt)).scalar_one()
        assert t1.invalidated_at is not None

        # Token 2 should be valid
        stmt = select(ForgeToken).where(ForgeToken.id == token2)
        t2 = (await forged_session.execute(stmt)).scalar_one()
        assert t2.invalidated_at is None


@pytest.mark.asyncio
class TestForgeIterationAdvanceORM:
    """forge_iteration_advance must use ORM session."""

    async def test_advance_moves_to_next_stage(self, forged_session):
        """Advancing transitions DISCOVER -> DESIGN."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )

        result = await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "advanced"
        assert result["previous_stage"] == "DISCOVER"
        assert result["current_stage"] == "DESIGN"
        assert result["token"] != start["token"]

    async def test_advance_stores_evidence(self, forged_session):
        """Evidence is stored in accumulated_knowledge."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )

        await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            evidence={"notes": "found patterns"},
            project_path="/test",
            session=forged_session,
        )

        # Verify in DB
        stmt = select(IterationStateORM).where(
            IterationStateORM.feature_name == "feat"
        )
        state = (await forged_session.execute(stmt)).scalar_one()
        knowledge = json.loads(state.accumulated_knowledge)
        assert knowledge["discover_evidence"] == {"notes": "found patterns"}

    async def test_advance_rejects_invalid_token(self, forged_session):
        """Invalid token returns error."""
        from spellbook.forged.iteration_tools import forge_iteration_advance

        result = await forge_iteration_advance(
            feature_name="feat",
            current_token="bad-token",
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "invalid token" in result["error"].lower()

    async def test_advance_rejects_expired_token(self, forged_session):
        """Already-used token returns error."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )

        # Use the token
        await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        # Try to use again
        result = await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "error"

    async def test_advance_full_cycle(self, forged_session):
        """Full stage progression: DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        token = start["token"]
        stages = ["DISCOVER"]

        for expected in ["DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]:
            result = await forge_iteration_advance(
                feature_name="feat",
                current_token=token,
                project_path="/test",
                session=forged_session,
            )
            stages.append(result["current_stage"])
            token = result["token"]

        assert stages == ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]


@pytest.mark.asyncio
class TestForgeIterationReturnORM:
    """forge_iteration_return must use ORM session."""

    async def test_return_to_earlier_stage(self, forged_session):
        """Return moves back and increments iteration."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
            forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        result = await forge_iteration_return(
            feature_name="feat",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[{
                "source": "validator",
                "critique": "Missing edge case",
                "evidence": "No handling for empty input",
                "suggestion": "Add validation",
                "severity": "blocking",
            }],
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "returned"
        assert result["previous_stage"] == "DESIGN"
        assert result["current_stage"] == "DISCOVER"
        assert result["iteration_number"] == 2

    async def test_return_with_reflection_creates_record(self, forged_session):
        """Reflection creates ForgeReflection ORM object."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
            forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        await forge_iteration_return(
            feature_name="feat",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[{
                "source": "test-validator",
                "critique": "Found issue",
                "evidence": "Line 42",
                "suggestion": "Fix it",
                "severity": "blocking",
            }],
            reflection="Edge cases need more attention",
            project_path="/test",
            session=forged_session,
        )

        # Verify ForgeReflection in DB
        stmt = select(ForgeReflection).where(
            ForgeReflection.feature_name == "feat"
        )
        reflection = (await forged_session.execute(stmt)).scalar_one()
        assert reflection.validator == "test-validator"
        assert "edge cases" in reflection.lesson_learned.lower()
        assert reflection.status == "PENDING"

    async def test_return_requires_feedback(self, forged_session):
        """Empty feedback returns error."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
            forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        result = await forge_iteration_return(
            feature_name="feat",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[],
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "feedback" in result["error"].lower()

    async def test_return_cannot_return_to_complete(self, forged_session):
        """Cannot return to COMPLETE stage."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start,
            forge_iteration_advance,
            forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="feat",
            project_path="/test",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="feat",
            current_token=start["token"],
            project_path="/test",
            session=forged_session,
        )

        result = await forge_iteration_return(
            feature_name="feat",
            current_token=advance["token"],
            return_to="COMPLETE",
            feedback=[],
            project_path="/test",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "cannot return" in result["error"].lower()
