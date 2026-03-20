"""Tests for Forged iteration MCP tools.

Updated for ORM migration: tests now use async fixtures with
in-memory SQLAlchemy sessions instead of mocked sqlite3 connections.
"""

import json
import pytest

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


class TestForgeIterationStart:
    """Tests for forge_iteration_start tool."""

    async def test_start_creates_new_iteration_state(self, forged_session):
        """Starting iteration for new feature creates initial state."""
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
        assert "token" in result
        assert result["token"] is not None

    async def test_start_with_custom_starting_stage(self, forged_session):
        """Starting iteration can specify custom starting stage."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result = await forge_iteration_start(
            feature_name="my-feature",
            starting_stage="DESIGN",
            project_path="/test/project",
            session=forged_session,
        )

        assert result["current_stage"] == "DESIGN"

    async def test_start_with_preferences(self, forged_session):
        """Starting iteration stores preferences."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result = await forge_iteration_start(
            feature_name="my-feature",
            preferences={"strict_mode": True, "max_iterations": 5},
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "started"

    async def test_start_resumes_existing_feature(self, forged_session):
        """Starting iteration for existing feature resumes state."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        await forge_iteration_start(
            feature_name="existing-feature",
            project_path="/test/project",
            session=forged_session,
        )

        result = await forge_iteration_start(
            feature_name="existing-feature",
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "resumed"
        assert result["iteration_number"] == 1
        assert result["current_stage"] == "DISCOVER"

    async def test_start_rejects_invalid_stage(self, forged_session):
        """Starting with invalid stage returns error."""
        from spellbook.forged.iteration_tools import forge_iteration_start

        result = await forge_iteration_start(
            feature_name="my-feature",
            starting_stage="INVALID_STAGE",
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "invalid stage" in result["error"].lower()

    async def test_start_creates_token_in_database(self, forged_session):
        """Token is persisted in forge_tokens table."""
        from spellbook.forged.iteration_tools import forge_iteration_start
        from spellbook.db.forged_models import ForgeToken
        from sqlalchemy import select

        result = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )

        token = result["token"]
        stmt = select(ForgeToken).where(ForgeToken.id == token)
        row = (await forged_session.execute(stmt)).scalar_one()
        assert row.stage == "DISCOVER"
        assert row.feature_name == "my-feature"

    async def test_start_invalidates_old_token(self, forged_session):
        """Starting new iteration invalidates previous token for feature."""
        from spellbook.forged.iteration_tools import forge_iteration_start
        from spellbook.db.forged_models import ForgeToken
        from sqlalchemy import select

        result1 = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        token1 = result1["token"]

        result2 = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        token2 = result2["token"]

        # First token should be invalidated
        stmt = select(ForgeToken).where(ForgeToken.id == token1)
        t1 = (await forged_session.execute(stmt)).scalar_one()
        assert t1.invalidated_at is not None

        # Second token should be valid
        stmt = select(ForgeToken).where(ForgeToken.id == token2)
        t2 = (await forged_session.execute(stmt)).scalar_one()
        assert t2.invalidated_at is None


class TestForgeIterationAdvance:
    """Tests for forge_iteration_advance tool."""

    async def test_advance_moves_to_next_stage(self, forged_session):
        """Advancing with valid token moves to next stage."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )

        result = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=start["token"],
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "advanced"
        assert result["previous_stage"] == "DISCOVER"
        assert result["current_stage"] == "DESIGN"
        assert result["token"] != start["token"]

    async def test_advance_with_evidence(self, forged_session):
        """Advancing stores evidence/knowledge."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )

        result = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=start["token"],
            evidence={"discovery_notes": "Found existing patterns", "files_reviewed": 5},
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "advanced"

    async def test_advance_rejects_invalid_token(self, forged_session):
        """Advancing with invalid token is rejected."""
        from spellbook.forged.iteration_tools import forge_iteration_advance

        result = await forge_iteration_advance(
            feature_name="my-feature",
            current_token="invalid-token-12345",
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "invalid token" in result["error"].lower()

    async def test_advance_rejects_expired_token(self, forged_session):
        """Advancing with already-invalidated token is rejected."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        token1 = start["token"]

        await forge_iteration_advance(
            feature_name="my-feature",
            current_token=token1,
            project_path="/test/project",
            session=forged_session,
        )

        bad_result = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=token1,
            project_path="/test/project",
            session=forged_session,
        )

        assert bad_result["status"] == "error"
        assert "expired" in bad_result["error"].lower() or "invalid" in bad_result["error"].lower()

    async def test_advance_rejects_wrong_feature(self, forged_session):
        """Advancing with token from different feature is rejected."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        result_a = await forge_iteration_start(
            feature_name="feature-a",
            project_path="/test/project",
            session=forged_session,
        )
        token_a = result_a["token"]

        await forge_iteration_start(
            feature_name="feature-b",
            project_path="/test/project",
            session=forged_session,
        )

        bad_result = await forge_iteration_advance(
            feature_name="feature-b",
            current_token=token_a,
            project_path="/test/project",
            session=forged_session,
        )

        assert bad_result["status"] == "error"
        assert "feature" in bad_result["error"].lower() or "mismatch" in bad_result["error"].lower()

    async def test_advance_follows_stage_order(self, forged_session):
        """Stages advance in correct order."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        result = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]
        stages = ["DISCOVER"]
        expected_order = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]

        for expected_next in expected_order[1:]:
            result = await forge_iteration_advance(
                feature_name="my-feature",
                current_token=token,
                project_path="/test/project",
                session=forged_session,
            )
            stages.append(result["current_stage"])
            token = result["token"]

        assert stages == expected_order


class TestForgeIterationReturn:
    """Tests for forge_iteration_return tool."""

    async def test_return_to_earlier_stage(self, forged_session):
        """Returning moves to specified earlier stage with feedback."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=start["token"],
            project_path="/test/project",
            session=forged_session,
        )

        result = await forge_iteration_return(
            feature_name="my-feature",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[{
                "source": "design-validator",
                "critique": "Missing edge case consideration",
                "evidence": "No handling for empty input",
                "suggestion": "Add discovery task for edge cases",
                "severity": "blocking",
            }],
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "returned"
        assert result["previous_stage"] == "DESIGN"
        assert result["current_stage"] == "DISCOVER"
        assert result["iteration_number"] == 2
        assert "token" in result

    async def test_return_increments_iteration(self, forged_session):
        """Returning increments the iteration counter."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        assert start["iteration_number"] == 1

        advance = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=start["token"],
            project_path="/test/project",
            session=forged_session,
        )

        ret = await forge_iteration_return(
            feature_name="my-feature",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[{"source": "test", "critique": "test", "evidence": "test", "suggestion": "test", "severity": "minor"}],
            project_path="/test/project",
            session=forged_session,
        )
        assert ret["iteration_number"] == 2

    async def test_return_with_reflection(self, forged_session):
        """Returning with reflection creates reflection record."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return,
        )
        from spellbook.db.forged_models import ForgeReflection
        from sqlalchemy import select

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=start["token"],
            project_path="/test/project",
            session=forged_session,
        )

        await forge_iteration_return(
            feature_name="my-feature",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[{"source": "test-validator", "critique": "Found issue", "evidence": "Line 42", "suggestion": "Fix it", "severity": "blocking"}],
            reflection="Learned that edge cases need more attention during discovery",
            project_path="/test/project",
            session=forged_session,
        )

        stmt = select(ForgeReflection).where(ForgeReflection.feature_name == "my-feature")
        row = (await forged_session.execute(stmt)).scalar_one()
        assert "edge cases" in row.lesson_learned.lower()
        assert row.validator == "test-validator"

    async def test_return_rejects_invalid_token(self, forged_session):
        """Returning with invalid token is rejected."""
        from spellbook.forged.iteration_tools import forge_iteration_return

        result = await forge_iteration_return(
            feature_name="my-feature",
            current_token="bad-token",
            return_to="DISCOVER",
            feedback=[{"source": "test", "critique": "test"}],
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "invalid token" in result["error"].lower()

    async def test_return_rejects_invalid_stage(self, forged_session):
        """Returning to invalid stage is rejected."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_return

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )

        result = await forge_iteration_return(
            feature_name="my-feature",
            current_token=start["token"],
            return_to="NOT_A_STAGE",
            feedback=[],
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "invalid stage" in result["error"].lower()

    async def test_return_requires_feedback(self, forged_session):
        """Returning requires at least one feedback item."""
        from spellbook.forged.iteration_tools import (
            forge_iteration_start, forge_iteration_advance, forge_iteration_return,
        )

        start = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        advance = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=start["token"],
            project_path="/test/project",
            session=forged_session,
        )

        result = await forge_iteration_return(
            feature_name="my-feature",
            current_token=advance["token"],
            return_to="DISCOVER",
            feedback=[],
            project_path="/test/project",
            session=forged_session,
        )

        assert result["status"] == "error"
        assert "feedback" in result["error"].lower()


class TestTokenSystem:
    """Integration tests for token-based workflow enforcement."""

    async def test_token_prevents_skipping_stages(self, forged_session):
        """Tokens prevent skipping stages in workflow."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        result = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        token = result["token"]

        await forge_iteration_advance(
            feature_name="my-feature",
            current_token=token,
            project_path="/test/project",
            session=forged_session,
        )

        skip_result = await forge_iteration_advance(
            feature_name="my-feature",
            current_token=token,
            project_path="/test/project",
            session=forged_session,
        )

        assert skip_result["status"] == "error"

    async def test_token_is_unique_per_transition(self, forged_session):
        """Each stage transition generates unique token."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        result = await forge_iteration_start(
            feature_name="my-feature",
            project_path="/test/project",
            session=forged_session,
        )
        tokens = [result["token"]]
        token = result["token"]

        for _ in range(4):
            result = await forge_iteration_advance(
                feature_name="my-feature",
                current_token=token,
                project_path="/test/project",
                session=forged_session,
            )
            if result["status"] == "advanced":
                tokens.append(result["token"])
                token = result["token"]

        assert len(tokens) == len(set(tokens))

    async def test_concurrent_features_have_independent_tokens(self, forged_session):
        """Multiple features can be worked on with independent tokens."""
        from spellbook.forged.iteration_tools import forge_iteration_start, forge_iteration_advance

        result_a = await forge_iteration_start(
            feature_name="feature-a",
            project_path="/test/project",
            session=forged_session,
        )
        result_b = await forge_iteration_start(
            feature_name="feature-b",
            project_path="/test/project",
            session=forged_session,
        )

        advance_a = await forge_iteration_advance(
            feature_name="feature-a",
            current_token=result_a["token"],
            project_path="/test/project",
            session=forged_session,
        )
        advance_b = await forge_iteration_advance(
            feature_name="feature-b",
            current_token=result_b["token"],
            project_path="/test/project",
            session=forged_session,
        )

        assert advance_a["status"] == "advanced"
        assert advance_b["status"] == "advanced"
        assert advance_a["current_stage"] == "DESIGN"
        assert advance_b["current_stage"] == "DESIGN"
