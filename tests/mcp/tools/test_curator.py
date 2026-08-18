"""Behavioural tests for the context-curator MCP tools.

The tools are exercised through ``_record_prune`` / ``_read_stats`` against a
real in-memory database. The public ``@mcp.tool()`` wrappers add only a session
context manager over these two, so testing them here covers the behaviour the
OpenCode ``context-curator`` extension actually depends on.
"""

import json

from sqlalchemy import select

from spellbook.db.spellbook_models import CuratorEvent
from spellbook.mcp.tools.curator import _read_stats, _record_prune


async def _seed(session, session_id, tokens_saved, strategy, tool_ids=("t1",)):
    return await _record_prune(session, session_id, list(tool_ids), tokens_saved, strategy)


class TestRecordPrune:
    async def test_returns_status_for_the_recorded_event(self, spellbook_session):
        result = await _record_prune(
            spellbook_session, "sess-a", ["call-1", "call-2", "call-3"], 900, "age"
        )

        assert result["success"] is True
        assert result["session_id"] == "sess-a"
        assert result["tools_pruned"] == 3
        assert isinstance(result["event_id"], int)

    async def test_persists_every_field_the_extension_sends(self, spellbook_session):
        result = await _record_prune(spellbook_session, "sess-a", ["call-1"], 512, "age")

        row = (
            await spellbook_session.execute(
                select(CuratorEvent).where(CuratorEvent.id == result["event_id"])
            )
        ).scalar_one()

        assert row.session_id == "sess-a"
        assert json.loads(row.tool_ids) == ["call-1"]
        assert row.tokens_saved == 512
        assert row.strategy == "age"
        assert row.timestamp.startswith("20")

    async def test_each_call_records_a_distinct_event(self, spellbook_session):
        first = await _seed(spellbook_session, "sess-a", 10, "age")
        second = await _seed(spellbook_session, "sess-a", 20, "age")

        assert first["event_id"] != second["event_id"]
        rows = (await spellbook_session.execute(select(CuratorEvent))).scalars().all()
        assert len(rows) == 2

    async def test_an_empty_tool_list_records_zero_tools_pruned(self, spellbook_session):
        result = await _record_prune(spellbook_session, "sess-a", [], 0, "age")

        assert result["tools_pruned"] == 0
        row = (
            await spellbook_session.execute(
                select(CuratorEvent).where(CuratorEvent.id == result["event_id"])
            )
        ).scalar_one()
        assert json.loads(row.tool_ids) == []


class TestReadStats:
    async def test_unknown_session_reports_zeroes_rather_than_failing(self, spellbook_session):
        stats = await _read_stats(spellbook_session, "never-seen")

        assert stats == {
            "sessionId": "never-seen",
            "totalTokensSaved": 0,
            "pruneEvents": 0,
            "extractEvents": 0,
            "byStrategy": {},
        }

    async def test_totals_sum_the_tokens_of_that_session(self, spellbook_session):
        await _seed(spellbook_session, "sess-a", 100, "age")
        await _seed(spellbook_session, "sess-a", 250, "age")

        stats = await _read_stats(spellbook_session, "sess-a")

        assert stats["totalTokensSaved"] == 350

    async def test_other_sessions_do_not_leak_into_the_totals(self, spellbook_session):
        await _seed(spellbook_session, "sess-a", 100, "age")
        await _seed(spellbook_session, "sess-b", 999, "age")

        stats = await _read_stats(spellbook_session, "sess-a")

        assert stats["totalTokensSaved"] == 100
        assert stats["pruneEvents"] == 1
        assert stats["byStrategy"] == {"age": {"count": 1, "tokens_saved": 100}}

    async def test_by_strategy_groups_counts_and_tokens(self, spellbook_session):
        await _seed(spellbook_session, "sess-a", 100, "age")
        await _seed(spellbook_session, "sess-a", 50, "age")
        await _seed(spellbook_session, "sess-a", 300, "size")

        stats = await _read_stats(spellbook_session, "sess-a")

        assert stats["byStrategy"] == {
            "age": {"count": 2, "tokens_saved": 150},
            "size": {"count": 1, "tokens_saved": 300},
        }

    async def test_extracts_are_counted_apart_from_prunes(self, spellbook_session):
        await _seed(spellbook_session, "sess-a", 10, "extract")
        await _seed(spellbook_session, "sess-a", 20, "extract")
        await _seed(spellbook_session, "sess-a", 30, "age")
        await _seed(spellbook_session, "sess-a", 40, "size")

        stats = await _read_stats(spellbook_session, "sess-a")

        assert stats["extractEvents"] == 2
        assert stats["pruneEvents"] == 2
        assert stats["totalTokensSaved"] == 100

    async def test_a_session_with_only_extracts_reports_no_prunes(self, spellbook_session):
        await _seed(spellbook_session, "sess-a", 10, "extract")

        stats = await _read_stats(spellbook_session, "sess-a")

        assert stats["extractEvents"] == 1
        assert stats["pruneEvents"] == 0

    async def test_stats_reflect_events_recorded_through_record_prune(self, spellbook_session):
        await _record_prune(spellbook_session, "sess-a", ["c1", "c2"], 640, "relevance")

        stats = await _read_stats(spellbook_session, "sess-a")

        assert stats["sessionId"] == "sess-a"
        assert stats["totalTokensSaved"] == 640
        assert stats["pruneEvents"] == 1
        assert stats["byStrategy"]["relevance"] == {"count": 1, "tokens_saved": 640}
