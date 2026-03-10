"""Tests for branch preservation through consolidation pipeline."""

import pytest

from spellbook_mcp.db import get_connection, init_db, close_all_connections
from spellbook_mcp.memory_consolidation import (
    _merge_event_metadata,
    _strategy_content_hash_dedup,
    _strategy_jaccard_similarity,
    _strategy_tag_grouping,
    _strategy_temporal_clustering,
    build_consolidation_prompt,
    consolidate_batch,
)
from spellbook_mcp.memory_store import log_raw_event


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path
    close_all_connections()


class TestMergeEventMetadataBranch:
    def test_collects_branches_from_events(self):
        events = [
            {"id": 1, "subject": "file.py", "tags": "a", "branch": "feature-x"},
            {"id": 2, "subject": "other.py", "tags": "b", "branch": "feature-x"},
            {"id": 3, "subject": "third.py", "tags": "c", "branch": "main"},
        ]
        all_tags, all_event_ids, all_citations, all_branches = _merge_event_metadata(events)
        assert all_tags == {"a", "b", "c"}
        assert all_event_ids == [1, 2, 3]
        assert all_branches == {"feature-x", "main"}

    def test_empty_branches_excluded(self):
        events = [
            {"id": 1, "subject": "file.py", "tags": "", "branch": ""},
            {"id": 2, "subject": "other.py", "tags": "", "branch": "main"},
        ]
        all_tags, all_event_ids, all_citations, all_branches = _merge_event_metadata(events)
        assert all_event_ids == [1, 2]
        assert all_branches == {"main"}

    def test_no_branches_yields_empty_set(self):
        events = [
            {"id": 1, "subject": "file.py", "tags": "", "branch": ""},
        ]
        _, _, _, all_branches = _merge_event_metadata(events)
        assert all_branches == set()


class TestBuildConsolidationPromptBranch:
    def test_includes_branch_annotation(self):
        events = [
            {
                "tool_name": "Read",
                "subject": "file.py",
                "summary": "Read the file",
                "tags": "",
                "branch": "feature-x",
            },
        ]
        prompt = build_consolidation_prompt(events)
        # The observation line should end with [branch: feature-x]
        expected_line = "- [Read] file.py: Read the file [branch: feature-x]"
        assert expected_line in prompt

    def test_branch_annotation_with_tags(self):
        events = [
            {
                "tool_name": "Write",
                "subject": "auth.py",
                "summary": "Updated auth",
                "tags": "auth,python",
                "branch": "feature-y",
            },
        ]
        prompt = build_consolidation_prompt(events)
        expected_line = "- [Write] auth.py: Updated auth (tags: auth,python) [branch: feature-y]"
        assert expected_line in prompt

    def test_no_branch_no_annotation(self):
        events = [
            {
                "tool_name": "Read",
                "subject": "file.py",
                "summary": "Read the file",
                "tags": "",
                "branch": "",
            },
        ]
        prompt = build_consolidation_prompt(events)
        assert "[branch:" not in prompt
        expected_line = "- [Read] file.py: Read the file"
        assert expected_line in prompt


class TestStrategyBranchPreservation:
    """Each strategy should include 'branches' in its output dicts."""

    def test_content_hash_dedup_includes_branches(self):
        events = [
            {"id": 1, "subject": "file.py", "summary": "same text", "tags": "a",
             "tool_name": "Read", "branch": "feature-x"},
            {"id": 2, "subject": "file.py", "summary": "same text", "tags": "b",
             "tool_name": "Read", "branch": "main"},
        ]
        memories, unconsumed = _strategy_content_hash_dedup(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == ["feature-x", "main"]

    def test_content_hash_dedup_single_branch(self):
        events = [
            {"id": 1, "subject": "file.py", "summary": "same text", "tags": "",
             "tool_name": "Read", "branch": "feature-x"},
            {"id": 2, "subject": "file.py", "summary": "same text", "tags": "",
             "tool_name": "Read", "branch": "feature-x"},
        ]
        memories, _ = _strategy_content_hash_dedup(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == ["feature-x"]

    def test_content_hash_dedup_empty_branches(self):
        events = [
            {"id": 1, "subject": "file.py", "summary": "same text", "tags": "",
             "tool_name": "Read", "branch": ""},
            {"id": 2, "subject": "file.py", "summary": "same text", "tags": "",
             "tool_name": "Read", "branch": ""},
        ]
        memories, _ = _strategy_content_hash_dedup(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == []

    def test_jaccard_similarity_includes_branches(self):
        # Two events with very similar text should be grouped
        events = [
            {"id": 1, "subject": "auth module", "summary": "updated authentication login handler code",
             "tags": "auth,login", "tool_name": "Write", "branch": "feature-a"},
            {"id": 2, "subject": "auth module", "summary": "modified authentication login handler logic",
             "tags": "auth,login", "tool_name": "Write", "branch": "feature-b"},
        ]
        memories, unconsumed = _strategy_jaccard_similarity(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == ["feature-a", "feature-b"]

    def test_tag_grouping_includes_branches(self):
        events = [
            {"id": 1, "subject": "file1.py", "summary": "first file",
             "tags": "auth,login,security", "tool_name": "Read", "branch": "feat-1"},
            {"id": 2, "subject": "file2.py", "summary": "second file",
             "tags": "auth,login,validation", "tool_name": "Read", "branch": "feat-2"},
        ]
        memories, unconsumed = _strategy_tag_grouping(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == ["feat-1", "feat-2"]

    def test_temporal_clustering_includes_branches(self):
        events = [
            {"id": 1, "subject": "file.py", "summary": "first edit",
             "tags": "a", "tool_name": "Write", "session_id": "s1",
             "timestamp": "2025-01-01T10:00:00", "branch": "dev"},
            {"id": 2, "subject": "file.py", "summary": "second edit",
             "tags": "b", "tool_name": "Write", "session_id": "s1",
             "timestamp": "2025-01-01T10:05:00", "branch": "dev"},
        ]
        memories, unconsumed = _strategy_temporal_clustering(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == ["dev"]

    def test_temporal_clustering_multiple_branches(self):
        events = [
            {"id": 1, "subject": "file.py", "summary": "first edit",
             "tags": "", "tool_name": "Write", "session_id": "s1",
             "timestamp": "2025-01-01T10:00:00", "branch": "main"},
            {"id": 2, "subject": "file.py", "summary": "second edit",
             "tags": "", "tool_name": "Write", "session_id": "s1",
             "timestamp": "2025-01-01T10:05:00", "branch": "feature"},
        ]
        memories, _ = _strategy_temporal_clustering(events)
        assert len(memories) == 1
        assert memories[0]["branches"] == ["feature", "main"]


class TestConsolidateBatchBranch:
    def test_consolidation_preserves_branch_in_memory(self, db_path):
        """Consolidated memories should have the first branch set as origin."""
        # Create 12 identical events with same branch to trigger content-hash dedup
        for i in range(12):
            log_raw_event(
                db_path=db_path,
                session_id="sess1",
                project="test-project",
                event_type="tool_use",
                tool_name="Read",
                subject="auth.py",
                summary="Read authentication module",
                tags="auth,read",
                branch="feature-x",
            )

        result = consolidate_batch(db_path, namespace="test-project")
        assert result["status"] == "success"
        assert result["memories_created"] >= 1

        # Check that memory has branch set
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM memories WHERE namespace = 'test-project' AND status = 'active'"
        )
        rows = cursor.fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == "feature-x"

    def test_consolidation_creates_branch_associations(self, db_path):
        """Memories created by consolidation should have branch associations in junction table."""
        for i in range(12):
            log_raw_event(
                db_path=db_path,
                session_id="sess1",
                project="test-project",
                event_type="tool_use",
                tool_name="Read",
                subject="auth.py",
                summary="Read authentication module",
                tags="auth,read",
                branch="feature-x",
            )

        result = consolidate_batch(db_path, namespace="test-project")
        assert result["status"] == "success"
        assert result["memories_created"] >= 1

        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT mb.branch_name, mb.association_type FROM memory_branches mb "
            "JOIN memories m ON m.id = mb.memory_id "
            "WHERE m.namespace = 'test-project'"
        )
        associations = [(r[0], r[1]) for r in cursor.fetchall()]
        assert ("feature-x", "origin") in associations

    def test_consolidation_multi_branch_associations(self, db_path):
        """Events from multiple branches should all appear in junction table."""
        # Create events: some from feature-x, some from feature-y
        # Use different summaries so they end up in temporal clustering (not dedup)
        for i in range(6):
            log_raw_event(
                db_path=db_path,
                session_id="sess1",
                project="test-project",
                event_type="tool_use",
                tool_name="Read",
                subject="auth.py",
                summary=f"Read authentication module part {i}",
                tags="auth,read",
                branch="feature-x" if i < 3 else "feature-y",
            )
        # Add enough more to reach consolidation threshold
        for i in range(6):
            log_raw_event(
                db_path=db_path,
                session_id="sess1",
                project="test-project",
                event_type="tool_use",
                tool_name="Write",
                subject="config.py",
                summary=f"Write config file part {i}",
                tags="config,write",
                branch="feature-x",
            )

        result = consolidate_batch(db_path, namespace="test-project")
        assert result["status"] == "success"
        assert result["memories_created"] >= 1

        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT DISTINCT mb.branch_name FROM memory_branches mb "
            "JOIN memories m ON m.id = mb.memory_id "
            "WHERE m.namespace = 'test-project'"
        )
        branches = {r[0] for r in cursor.fetchall()}
        assert "feature-x" in branches
        assert "feature-y" in branches
