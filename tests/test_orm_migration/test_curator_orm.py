"""Tests for curator module ORM migration.

Tests verify that curator_track_prune and curator_get_stats use
async SQLAlchemy sessions and CuratorEvent ORM model instead of
raw sqlite3 connections.

RED phase: these tests will fail until the migration is complete.
"""

import json

import pytest
from sqlalchemy import select, func

from spellbook.db.spellbook_models import CuratorEvent


@pytest.mark.asyncio
class TestCuratorTrackPruneORM:
    """curator_track_prune must use ORM session."""

    async def test_track_prune_creates_curator_event(self, spellbook_session):
        """curator_track_prune inserts a CuratorEvent via ORM session."""
        from spellbook.coordination.curator import curator_track_prune

        result = await curator_track_prune(
            session_id="sess-001",
            tool_ids=["tool-a", "tool-b"],
            tokens_saved=500,
            strategy="aggressive",
            session=spellbook_session,
        )

        assert result == {
            "success": True,
            "event_id": result["event_id"],
            "session_id": "sess-001",
            "tools_pruned": 2,
        }

        # Verify ORM object in DB
        stmt = select(CuratorEvent).where(
            CuratorEvent.id == result["event_id"]
        )
        row = (await spellbook_session.execute(stmt)).scalar_one()

        assert row.session_id == "sess-001"
        assert json.loads(row.tool_ids) == ["tool-a", "tool-b"]
        assert row.tokens_saved == 500
        assert row.strategy == "aggressive"
        assert row.timestamp is not None

    async def test_track_prune_event_id_is_integer(self, spellbook_session):
        """event_id returned by curator_track_prune is a positive integer."""
        from spellbook.coordination.curator import curator_track_prune

        result = await curator_track_prune(
            session_id="sess-002",
            tool_ids=["tool-x"],
            tokens_saved=100,
            strategy="lazy",
            session=spellbook_session,
        )

        assert isinstance(result["event_id"], int)
        assert result["event_id"] > 0


@pytest.mark.asyncio
class TestCuratorGetStatsORM:
    """curator_get_stats must use ORM session."""

    async def test_get_stats_empty_session(self, spellbook_session):
        """Stats for session with no events returns zeroes."""
        from spellbook.coordination.curator import curator_get_stats

        result = await curator_get_stats(
            session_id="empty-sess",
            session=spellbook_session,
        )

        assert result == {
            "session_id": "empty-sess",
            "totalTokensSaved": 0,
            "pruneEvents": 0,
            "extractEvents": 0,
            "byStrategy": {},
        }

    async def test_get_stats_with_events(self, spellbook_session):
        """Stats aggregate events correctly."""
        from spellbook.coordination.curator import curator_track_prune, curator_get_stats

        await curator_track_prune(
            session_id="stats-sess",
            tool_ids=["a"],
            tokens_saved=100,
            strategy="aggressive",
            session=spellbook_session,
        )
        await curator_track_prune(
            session_id="stats-sess",
            tool_ids=["b", "c"],
            tokens_saved=200,
            strategy="aggressive",
            session=spellbook_session,
        )
        await curator_track_prune(
            session_id="stats-sess",
            tool_ids=["d"],
            tokens_saved=50,
            strategy="extract",
            session=spellbook_session,
        )

        result = await curator_get_stats(
            session_id="stats-sess",
            session=spellbook_session,
        )

        assert result == {
            "session_id": "stats-sess",
            "totalTokensSaved": 350,
            "pruneEvents": 2,
            "extractEvents": 1,
            "byStrategy": {
                "aggressive": {"count": 2, "tokens_saved": 300},
                "extract": {"count": 1, "tokens_saved": 50},
            },
        }

    async def test_get_stats_isolates_sessions(self, spellbook_session):
        """Stats for one session do not include events from another."""
        from spellbook.coordination.curator import curator_track_prune, curator_get_stats

        await curator_track_prune(
            session_id="sess-A",
            tool_ids=["x"],
            tokens_saved=999,
            strategy="nuke",
            session=spellbook_session,
        )
        await curator_track_prune(
            session_id="sess-B",
            tool_ids=["y"],
            tokens_saved=1,
            strategy="gentle",
            session=spellbook_session,
        )

        result = await curator_get_stats(
            session_id="sess-A",
            session=spellbook_session,
        )

        assert result["totalTokensSaved"] == 999
        assert result["pruneEvents"] == 1
        assert result["byStrategy"] == {
            "nuke": {"count": 1, "tokens_saved": 999},
        }
