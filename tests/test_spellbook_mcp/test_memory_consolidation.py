"""Tests for memory consolidation pipeline."""

import json
import pytest
from unittest.mock import patch

from spellbook_mcp.db import init_db, get_connection, close_all_connections
from spellbook_mcp.memory_store import (
    log_raw_event,
    get_unconsolidated_events,
    get_memory,
    insert_memory,
    insert_link,
    soft_delete_memory,
    purge_deleted,
)
from spellbook_mcp.memory_consolidation import (
    consolidate_batch,
    build_consolidation_prompt,
    parse_llm_response,
    compute_bibliographic_coupling,
    should_consolidate,
    EVENT_THRESHOLD,
    SIMILARITY_THRESHOLD,
    TAG_OVERLAP_BOOST,
    MIN_SHARED_TAGS,
    TEMPORAL_GAP_MINUTES,
    MIN_MEANINGFUL_WORDS,
    _strategy_content_hash_dedup,
    _strategy_jaccard_similarity,
    _strategy_tag_grouping,
    _strategy_temporal_clustering,
    _event_text,
    _extract_citations,
    _extract_keywords,
)


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


def _seed_events(db_path, count=15):
    """Seed raw events for testing."""
    for i in range(count):
        log_raw_event(
            db_path=db_path,
            session_id="sess-1",
            project="Users-alice-myproject",
            event_type="tool_use",
            tool_name="Read",
            subject=f"src/module_{i % 3}.py",
            summary=f"Read src/module_{i % 3}.py lines {i*10}-{(i+1)*10}",
            tags="python,read",
        )


# --- should_consolidate ---


class TestShouldConsolidate:
    def test_below_threshold(self, db):
        """One event is below the threshold of EVENT_THRESHOLD."""
        log_raw_event(
            db_path=db, session_id="s", project="p", event_type="t",
            tool_name="Read", subject="f.py", summary="s", tags="",
        )
        assert should_consolidate(db) is False

    def test_at_threshold(self, db):
        """Exactly EVENT_THRESHOLD events should trigger consolidation."""
        _seed_events(db, EVENT_THRESHOLD)
        assert should_consolidate(db) is True

    def test_above_threshold(self, db):
        """More than EVENT_THRESHOLD events should trigger consolidation."""
        _seed_events(db, EVENT_THRESHOLD + 5)
        assert should_consolidate(db) is True

    def test_zero_events(self, db):
        """No events at all means no consolidation."""
        assert should_consolidate(db) is False


# --- build_consolidation_prompt ---


class TestBuildConsolidationPrompt:
    def test_builds_prompt_from_events(self, db):
        """Prompt contains structured observations and instruction text."""
        _seed_events(db, 3)
        events = get_unconsolidated_events(db, limit=50)

        prompt = build_consolidation_prompt(events)

        # Build the expected prompt exactly to verify full content
        expected_lines = []
        for e in events:
            line = f"- [{e['tool_name']}] {e['subject']}: {e['summary']}"
            if e.get("tags"):
                line += f" (tags: {e['tags']})"
            expected_lines.append(line)

        expected_prompt = (
            "Given these tool observations from a coding session, extract structured memories.\n"
            "For each distinct fact, rule, pattern, or decision observed:\n"
            "- content: the memory as a clear, standalone statement\n"
            "- memory_type: one of fact/rule/antipattern/preference/decision\n"
            "- tags: 3-5 keywords for retrieval\n"
            "- citations: file paths referenced, with line ranges and 1-3 line snippets\n\n"
            'Return JSON: {"memories": [{"content": "...", "memory_type": "...", '
            '"tags": [...], "citations": [{"file_path": "...", "line_range": "...", '
            '"snippet": "..."}]}]}\n\n'
            "Observations:\n" + "\n".join(expected_lines)
        )

        assert prompt == expected_prompt


# --- parse_llm_response ---


class TestParseLlmResponse:
    def test_valid_response(self):
        """Parses a well-formed JSON response into memory dicts."""
        response = json.dumps({
            "memories": [
                {
                    "content": "Module 0 handles authentication",
                    "memory_type": "fact",
                    "tags": ["auth", "module0"],
                    "citations": [
                        {
                            "file_path": "src/module_0.py",
                            "line_range": "1-10",
                            "snippet": "def authenticate():",
                        }
                    ],
                }
            ]
        })
        memories = parse_llm_response(response)
        assert memories == [
            {
                "content": "Module 0 handles authentication",
                "memory_type": "fact",
                "tags": ["auth", "module0"],
                "citations": [
                    {
                        "file_path": "src/module_0.py",
                        "line_range": "1-10",
                        "snippet": "def authenticate():",
                    }
                ],
            }
        ]

    def test_invalid_json(self):
        """Returns empty list for non-JSON input."""
        memories = parse_llm_response("not json at all")
        assert memories == []

    def test_missing_fields_defaults(self):
        """Missing tags and citations default to empty lists."""
        response = json.dumps({"memories": [{"content": "ok"}]})
        memories = parse_llm_response(response)
        assert memories == [
            {
                "content": "ok",
                "memory_type": "fact",
                "tags": [],
                "citations": [],
            }
        ]

    def test_skips_entries_without_content(self):
        """Entries missing 'content' key are filtered out."""
        response = json.dumps({
            "memories": [
                {"memory_type": "fact", "tags": ["x"]},
                {"content": "valid one", "memory_type": "rule"},
            ]
        })
        memories = parse_llm_response(response)
        assert memories == [
            {
                "content": "valid one",
                "memory_type": "rule",
                "tags": [],
                "citations": [],
            }
        ]

    def test_empty_memories_list(self):
        """Empty memories array returns empty list."""
        response = json.dumps({"memories": []})
        memories = parse_llm_response(response)
        assert memories == []

    def test_missing_memories_key(self):
        """JSON without 'memories' key returns empty list."""
        response = json.dumps({"data": "something"})
        memories = parse_llm_response(response)
        assert memories == []

    def test_multiple_memories(self):
        """Parses multiple memories correctly."""
        response = json.dumps({
            "memories": [
                {
                    "content": "First memory",
                    "memory_type": "fact",
                    "tags": ["a"],
                    "citations": [],
                },
                {
                    "content": "Second memory",
                    "memory_type": "rule",
                    "tags": ["b", "c"],
                    "citations": [{"file_path": "x.py"}],
                },
            ]
        })
        memories = parse_llm_response(response)
        assert memories == [
            {
                "content": "First memory",
                "memory_type": "fact",
                "tags": ["a"],
                "citations": [],
            },
            {
                "content": "Second memory",
                "memory_type": "rule",
                "tags": ["b", "c"],
                "citations": [{"file_path": "x.py"}],
            },
        ]


# --- compute_bibliographic_coupling ---


class TestComputeBibliographicCoupling:
    def test_shared_file_jaccard(self, db):
        """Two memories sharing one file out of three total get Jaccard 1/3."""
        id1 = insert_memory(
            db_path=db, content="memory about auth",
            memory_type="fact", namespace="ns",
            tags=["auth"],
            citations=[
                {"file_path": "src/auth.py", "line_range": "1-10", "snippet": "..."},
                {"file_path": "src/utils.py", "line_range": "1-5", "snippet": "..."},
            ],
        )
        id2 = insert_memory(
            db_path=db, content="memory about users",
            memory_type="fact", namespace="ns",
            tags=["users"],
            citations=[
                {"file_path": "src/auth.py", "line_range": "20-30", "snippet": "..."},
                {"file_path": "src/models.py", "line_range": "1-5", "snippet": "..."},
            ],
        )
        links = compute_bibliographic_coupling(db, id1)
        # Jaccard: |{auth.py}| / |{auth.py, utils.py, models.py}| = 1/3
        assert links == [{"other_id": id2, "weight": pytest.approx(1.0 / 3.0, abs=0.01)}]

    def test_no_shared_files(self, db):
        """Memories citing different files produce no links."""
        insert_memory(
            db_path=db, content="memory A",
            memory_type="fact", namespace="ns",
            tags=["a"],
            citations=[{"file_path": "src/a.py"}],
        )
        id2 = insert_memory(
            db_path=db, content="memory B",
            memory_type="fact", namespace="ns",
            tags=["b"],
            citations=[{"file_path": "src/b.py"}],
        )
        links = compute_bibliographic_coupling(db, id2)
        assert links == []

    def test_no_citations(self, db):
        """Memory with no citations produces no links."""
        mem_id = insert_memory(
            db_path=db, content="memory without citations",
            memory_type="fact", namespace="ns",
            tags=["x"],
            citations=[],
        )
        links = compute_bibliographic_coupling(db, mem_id)
        assert links == []

    def test_identical_citations_full_overlap(self, db):
        """Two memories citing exactly the same files get Jaccard 1.0."""
        id1 = insert_memory(
            db_path=db, content="memory one",
            memory_type="fact", namespace="ns",
            tags=["x"],
            citations=[
                {"file_path": "src/shared.py", "line_range": "1-10", "snippet": "a"},
            ],
        )
        id2 = insert_memory(
            db_path=db, content="memory two",
            memory_type="fact", namespace="ns",
            tags=["y"],
            citations=[
                {"file_path": "src/shared.py", "line_range": "20-30", "snippet": "b"},
            ],
        )
        links = compute_bibliographic_coupling(db, id1)
        assert links == [{"other_id": id2, "weight": pytest.approx(1.0, abs=0.01)}]


# --- consolidate_batch (heuristic pipeline) ---


def _seed_duplicate_events(db_path):
    """Seed events with exact duplicates for content-hash dedup testing."""
    # Two identical events (same subject + summary)
    for i in range(2):
        log_raw_event(
            db_path=db_path,
            session_id="sess-1",
            project="Users-alice-myproject",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read authentication module config",
            tags="python,auth",
        )
    # One unique event
    log_raw_event(
        db_path=db_path,
        session_id="sess-1",
        project="Users-alice-myproject",
        event_type="tool_use",
        tool_name="Edit",
        subject="src/database.py",
        summary="Edited database migration schema",
        tags="python,db",
    )


class TestConsolidateBatch:
    def test_no_events(self, db):
        """No unconsolidated events returns early with no_events status."""
        result = consolidate_batch(
            db_path=db,
            namespace="Users-alice-myproject",
        )
        assert result == {
            "status": "no_events",
            "events_consolidated": 0,
            "memories_created": 0,
        }

    def test_heuristic_pipeline_creates_memories_with_extra_meta(self, db):
        """Heuristic pipeline creates memories with source=heuristic extra_meta."""
        _seed_duplicate_events(db)

        result = consolidate_batch(
            db_path=db,
            namespace="Users-alice-myproject",
        )

        assert result["status"] == "success"
        assert result["events_consolidated"] == 3
        # 2 duplicate events -> 1 content_hash memory
        # 1 remaining unique event -> goes through jaccard (no match), tag_grouping (no match),
        # temporal_clustering (produces 1 memory)
        # Total: 2 memories
        assert result["memories_created"] == 2
        # batch_id must be a valid UUID
        import uuid
        uuid.UUID(result["batch_id"], version=4)

        # All events should be marked consolidated
        remaining = get_unconsolidated_events(db, limit=50)
        assert remaining == []

        # Verify memories were inserted with correct extra_meta
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT content, memory_type, namespace, meta FROM memories "
            "WHERE namespace = ? ORDER BY content",
            ("Users-alice-myproject",),
        )
        rows = cursor.fetchall()
        assert len(rows) == 2

        # Check each memory has correct extra_meta
        for row in rows:
            meta = json.loads(row[3])
            assert meta["source"] == "heuristic"
            assert meta["strategy"] in (
                "content_hash", "jaccard_similarity", "tag_grouping", "temporal_clustering",
            )
            assert isinstance(meta["event_count"], int)
            assert meta["event_count"] in (1, 2)
            assert meta["batch_id"] == result["batch_id"]

        # Verify the content_hash dedup memory
        content_hash_rows = [
            r for r in rows if json.loads(r[3])["strategy"] == "content_hash"
        ]
        assert len(content_hash_rows) == 1
        assert content_hash_rows[0][0] == "[Read] src/auth.py: Read authentication module config"
        assert content_hash_rows[0][1] == "fact"
        assert content_hash_rows[0][2] == "Users-alice-myproject"
        ch_meta = json.loads(content_hash_rows[0][3])
        assert ch_meta["event_count"] == 2

        # Verify the temporal_clustering memory (the unique event)
        temporal_rows = [
            r for r in rows if json.loads(r[3])["strategy"] == "temporal_clustering"
        ]
        assert len(temporal_rows) == 1
        assert temporal_rows[0][1] == "fact"
        tc_meta = json.loads(temporal_rows[0][3])
        assert tc_meta["event_count"] == 1

    def test_error_handling_marks_events_and_returns_error(self, db):
        """Strategy failure logs error, marks events consolidated, returns error dict."""
        _seed_events(db, 15)

        # Force an error in the heuristic pipeline by making a strategy raise
        with patch(
            "spellbook_mcp.memory_consolidation._strategy_content_hash_dedup",
            side_effect=RuntimeError("hash computation failed"),
        ):
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result["status"] == "error"
        assert result["error"] == "hash computation failed"
        assert result["events_consolidated"] == 15
        assert result["memories_created"] == 0
        # batch_id must be present and valid
        import uuid
        uuid.UUID(result["batch_id"], version=4)

        # Events should be marked consolidated (prevent infinite retry)
        remaining = get_unconsolidated_events(db, limit=50)
        assert remaining == []

        # Verify audit log entry was created
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT action, details FROM memory_audit_log WHERE action = 'consolidation_error'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "consolidation_error"
        details = json.loads(row[1])
        assert details["error"] == "hash computation failed"
        assert details["events_count"] == 15
        assert details["batch_id"] == result["batch_id"]

    def test_mid_pipeline_strategy_failure_graceful_recovery(self, db):
        """When a mid-pipeline strategy fails, error is caught and all events marked consolidated."""
        # Seed events: 2 duplicates (consumed by content_hash) + 3 unique (hit jaccard)
        for _ in range(2):
            log_raw_event(
                db_path=db, session_id="sess-1", project="ns",
                event_type="tool_use", tool_name="Read",
                subject="src/dup.py",
                summary="Read exact duplicate content here",
                tags="python",
            )
        for i in range(3):
            log_raw_event(
                db_path=db, session_id="sess-1", project="ns",
                event_type="tool_use", tool_name="Edit",
                subject=f"src/unique_{i}.py",
                summary=f"Completely different unique content number {i} for testing",
                tags=f"tag_{i}",
            )

        # Fail jaccard_similarity (second strategy, after content_hash succeeds)
        with patch(
            "spellbook_mcp.memory_consolidation._strategy_jaccard_similarity",
            side_effect=ValueError("jaccard computation exploded"),
        ):
            result = consolidate_batch(db_path=db, namespace="ns")

        assert result["status"] == "error"
        assert result["error"] == "jaccard computation exploded"
        assert result["events_consolidated"] == 5
        assert result["memories_created"] == 0
        import uuid as uuid_mod
        uuid_mod.UUID(result["batch_id"], version=4)

        # All events marked consolidated (prevents infinite retry)
        remaining = get_unconsolidated_events(db, limit=50)
        assert remaining == []

        # No memories were persisted (error rolls back the batch)
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE namespace = ?", ("ns",),
        )
        assert cursor.fetchone()[0] == 0

        # Audit log records the error
        cursor = conn.execute(
            "SELECT action, details FROM memory_audit_log WHERE action = 'consolidation_error'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "consolidation_error"
        details = json.loads(row[1])
        assert details["error"] == "jaccard computation exploded"
        assert details["events_count"] == 5
        assert details["batch_id"] == result["batch_id"]

    def test_namespace_isolation(self, db):
        """consolidate_batch only consumes events from the specified namespace."""
        # Seed events in namespace "alpha"
        for _ in range(2):
            log_raw_event(
                db_path=db, session_id="sess-1", project="alpha",
                event_type="tool_use", tool_name="Read",
                subject="src/alpha.py",
                summary="Read alpha module code",
                tags="python",
            )
        # Seed events in namespace "beta"
        for _ in range(2):
            log_raw_event(
                db_path=db, session_id="sess-1", project="beta",
                event_type="tool_use", tool_name="Read",
                subject="src/beta.py",
                summary="Read beta module code",
                tags="python",
            )

        # Consolidate only "alpha"
        result = consolidate_batch(db_path=db, namespace="alpha")

        assert result["status"] == "success"
        assert result["events_consolidated"] == 2

        # Alpha events should be consolidated
        alpha_remaining = get_unconsolidated_events(db, limit=50, namespace="alpha")
        assert alpha_remaining == []

        # Beta events should remain unconsolidated
        beta_remaining = get_unconsolidated_events(db, limit=50, namespace="beta")
        assert len(beta_remaining) == 2
        assert all(e["project"] == "beta" for e in beta_remaining)

        # Memories should be stored under "alpha" namespace only
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT namespace FROM memories"
        )
        namespaces = [row[0] for row in cursor.fetchall()]
        assert all(ns == "alpha" for ns in namespaces)

                event_type="tool_use", tool_name="Read",
                subject="src/config.py",
                summary="Read config loader initialization",
                tags="python,config",
            )

        # Group B: 2 similar events (Jaccard >= 0.6) -> jaccard_similarity
        # These share "authentication", "module", "configuration", "handler"
        # but differ enough to not be exact duplicates
        log_raw_event(
            db_path=db, session_id="sess-1", project="ns",
            event_type="tool_use", tool_name="Read",
            subject="src/auth.py",
            summary="authentication module configuration handler validates tokens",
            tags="python,auth,security",
        )
        log_raw_event(
            db_path=db, session_id="sess-1", project="ns",
            event_type="tool_use", tool_name="Read",
            subject="src/auth.py",
            summary="authentication module configuration handler validates sessions",
            tags="python,auth,security",
        )

        # Group C: 2 events with shared tags (python,db) -> tag_grouping
        # These must NOT be Jaccard-similar (different words) and NOT exact dupes
        log_raw_event(
            db_path=db, session_id="sess-1", project="ns",
            event_type="tool_use", tool_name="Edit",
            subject="src/models.py",
            summary="alpha schema creation",
            tags="python,db",
        )
        log_raw_event(
            db_path=db, session_id="sess-1", project="ns",
            event_type="tool_use", tool_name="Edit",
            subject="src/migrations.py",
            summary="beta migration runner",
            tags="python,db",
        )

        # Group D: 1 unique event with no tag overlap -> temporal_clustering fallback
        log_raw_event(
            db_path=db, session_id="sess-1", project="ns",
            event_type="tool_use", tool_name="Edit",
            subject="README.md",
            summary="Updated project documentation overview",
            tags="docs",
        )

        result = consolidate_batch(db_path=db, namespace="ns")

        assert result["status"] == "success"
        assert result["events_consolidated"] == 7
        import uuid as uuid_mod
        uuid_mod.UUID(result["batch_id"], version=4)

        # All events should be consumed
        remaining = get_unconsolidated_events(db, limit=50)
        assert remaining == []

        # Verify memories by strategy
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT content, memory_type, namespace, meta FROM memories "
            "WHERE namespace = ? ORDER BY content",
            ("ns",),
        )
        rows = cursor.fetchall()

        # Classify memories by strategy
        by_strategy = {}
        for row in rows:
            meta = json.loads(row[3])
            strategy = meta["strategy"]
            by_strategy.setdefault(strategy, []).append({
                "content": row[0],
                "memory_type": row[1],
                "namespace": row[2],
                "meta": meta,
            })

        # Strategy 1: content_hash should have 1 memory from the 2 duplicate events
        assert len(by_strategy.get("content_hash", [])) == 1
        ch_mem = by_strategy["content_hash"][0]
        assert ch_mem["content"] == "[Read] src/config.py: Read config loader initialization"
        assert ch_mem["memory_type"] == "fact"
        assert ch_mem["namespace"] == "ns"
        assert ch_mem["meta"]["source"] == "heuristic"
        assert ch_mem["meta"]["event_count"] == 2
        assert ch_mem["meta"]["batch_id"] == result["batch_id"]

        # Strategy 2: jaccard_similarity should have 1 memory from the 2 similar events
        assert len(by_strategy.get("jaccard_similarity", [])) == 1
        jac_mem = by_strategy["jaccard_similarity"][0]
        assert jac_mem["meta"]["source"] == "heuristic"
        assert jac_mem["meta"]["strategy"] == "jaccard_similarity"
        assert jac_mem["meta"]["event_count"] == 2
        assert jac_mem["meta"]["batch_id"] == result["batch_id"]

        # Strategy 3: tag_grouping should have 1 memory from the 2 shared-tag events
        assert len(by_strategy.get("tag_grouping", [])) == 1
        tg_mem = by_strategy["tag_grouping"][0]
        assert tg_mem["content"] == (
            "Related activities:\n"
            "- src/models.py: alpha schema creation\n"
            "- src/migrations.py: beta migration runner"
        )
        assert tg_mem["meta"]["source"] == "heuristic"
        assert tg_mem["meta"]["strategy"] == "tag_grouping"
        assert tg_mem["meta"]["event_count"] == 2
        assert tg_mem["meta"]["batch_id"] == result["batch_id"]

        # Strategy 4: temporal_clustering should have 1 memory (the README event)
        assert len(by_strategy.get("temporal_clustering", [])) == 1
        tc_mem = by_strategy["temporal_clustering"][0]
        assert tc_mem["content"] == "[Edit] README.md: Updated project documentation overview"
        assert tc_mem["meta"]["source"] == "heuristic"
        assert tc_mem["meta"]["strategy"] == "temporal_clustering"
        assert tc_mem["meta"]["event_count"] == 1
        assert tc_mem["meta"]["batch_id"] == result["batch_id"]

        # Total: 4 memories from 7 events
        assert result["memories_created"] == 4

        # Verify audit log has correct compression ratio
        cursor = conn.execute(
            "SELECT details FROM memory_audit_log WHERE action = 'consolidation_complete'"
        )
        audit_row = cursor.fetchone()
        assert audit_row is not None
        audit_details = json.loads(audit_row[0])
        assert audit_details["batch_id"] == result["batch_id"]
        assert audit_details["events_consolidated"] == 7
        assert audit_details["memories_created"] == 4
        assert audit_details["compression_ratio"] == round(4 / 7, 3)
        assert set(audit_details["strategies_used"]) == {
            "content_hash", "jaccard_similarity", "tag_grouping", "temporal_clustering",
        }

    def test_strategies_run_in_pipeline_order(self, db):
        """Strategies consume events in order: content_hash, jaccard, tag_grouping, temporal."""
        # Seed events that will be consumed at different pipeline stages:
        # 2 exact duplicates (consumed by content_hash)
        for _ in range(2):
            log_raw_event(
                db_path=db,
                session_id="sess-1",
                project="ns",
                event_type="tool_use",
                tool_name="Read",
                subject="src/dup.py",
                summary="Read exact same content here",
                tags="python,dup",
            )
        # 1 unique event (will pass through to temporal_clustering)
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="ns",
            event_type="tool_use",
            tool_name="Edit",
            subject="src/unique.py",
            summary="Completely different topic about databases and migrations",
            tags="sql",
        )

        result = consolidate_batch(db_path=db, namespace="ns")

        assert result["status"] == "success"
        assert result["events_consolidated"] == 3

        # Verify which strategies created memories
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT meta FROM memories WHERE namespace = ?", ("ns",),
        )
        strategies = sorted(json.loads(r[0])["strategy"] for r in cursor.fetchall())

        # content_hash consumed the 2 duplicates, temporal_clustering consumed the unique event
        assert strategies == ["content_hash", "temporal_clustering"]


# --- Bibliographic coupling after consolidation (heuristic pipeline) ---


class TestBibliographicCouplingIntegration:
    def test_consolidation_creates_bibliographic_links(self, db):
        """After heuristic consolidation produces memories with shared citations,
        verify memory_links contains a bibliographic coupling entry."""
        # Seed events whose subjects are file paths (so _extract_citations finds them)
        # Two events with subject "src/shared.py" will be deduped by content_hash
        # if identical, or grouped by temporal_clustering if different.
        # We need 2 memories that each cite "src/shared.py" to get bibliographic coupling.
        # Best approach: events with different content but file-path subjects that overlap.

        # Group 1: two identical events -> content_hash memory citing "src/shared.py"
        for _ in range(2):
            log_raw_event(
                db_path=db,
                session_id="sess-1",
                project="ns",
                event_type="tool_use",
                tool_name="Read",
                subject="src/shared.py",
                summary="Read shared utility functions",
                tags="python,utils",
            )

        # Group 2: a single event -> temporal_clustering memory also citing "src/shared.py"
        log_raw_event(
            db_path=db,
            session_id="sess-2",
            project="ns",
            event_type="tool_use",
            tool_name="Edit",
            subject="src/shared.py",
            summary="Edited shared helper methods",
            tags="python,refactor",
        )

        result = consolidate_batch(db_path=db, namespace="ns")

        assert result["status"] == "success"
        assert result["memories_created"] == 2

        # Verify bibliographic coupling link was created
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT memory_a, memory_b, link_type, weight FROM memory_links "
            "WHERE link_type = 'bibliographic'"
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        # Both memories cite only "src/shared.py" -> Jaccard = 1.0
        row = rows[0]
        assert row[2] == "bibliographic"
        assert abs(row[3] - 1.0) < 0.01


# --- purge_deleted cascade ---


class TestPurgeDeletedCascade:
    def test_purge_removes_citations_and_links(self, db):
        """Purging a deleted memory also removes its citations and links."""
        # Create two memories with citations and a link between them
        id1 = insert_memory(
            db_path=db, content="memory to be purged",
            memory_type="fact", namespace="ns",
            tags=["purge"],
            citations=[
                {"file_path": "src/purge_target.py", "line_range": "1-10", "snippet": "..."},
            ],
        )
        id2 = insert_memory(
            db_path=db, content="memory that stays",
            memory_type="fact", namespace="ns",
            tags=["keep"],
            citations=[
                {"file_path": "src/keep.py", "line_range": "1-5", "snippet": "..."},
            ],
        )
        insert_link(db, id1, id2, "bibliographic", weight=0.5)

        # Soft-delete memory 1 and backdate it past retention
        soft_delete_memory(db, id1)
        conn = get_connection(db)
        conn.execute(
            "UPDATE memories SET deleted_at = datetime('now', '-31 days') WHERE id = ?",
            (id1,),
        )
        conn.commit()

        # Verify citations and links exist before purge
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_citations WHERE memory_id = ?", (id1,),
        )
        assert cursor.fetchone()[0] == 1

        a, b = (id1, id2) if id1 < id2 else (id2, id1)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_links WHERE memory_a = ? AND memory_b = ?",
            (a, b),
        )
        assert cursor.fetchone()[0] == 1

        # Purge
        count = purge_deleted(db, retention_days=30)
        assert count == 1

        # Memory should be gone
        assert get_memory(db, id1) is None

        # Citations for purged memory should be gone
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_citations WHERE memory_id = ?", (id1,),
        )
        assert cursor.fetchone()[0] == 0

        # Links involving purged memory should be gone
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_links WHERE memory_a = ? OR memory_b = ?",
            (id1, id1),
        )
        assert cursor.fetchone()[0] == 0

        # The other memory and its citations should still exist
        assert get_memory(db, id2) is not None
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memory_citations WHERE memory_id = ?", (id2,),
        )
        assert cursor.fetchone()[0] == 1


# --- Helper functions ---


class TestExtractKeywords:
    def test_filters_stop_words_and_short_words(self):
        """Stop words and words <= 2 chars are removed."""
        result = _extract_keywords("the quick brown fox is a fast animal")
        assert result == {"quick", "brown", "fox", "fast", "animal"}

    def test_lowercases_input(self):
        """All words are lowercased."""
        result = _extract_keywords("Python Authentication Module")
        assert result == {"python", "authentication", "module"}

    def test_empty_string(self):
        """Empty string returns empty set."""
        result = _extract_keywords("")
        assert result == set()


class TestEventText:
    def test_combines_subject_and_summary(self):
        """Returns 'subject: summary' format."""
        event = {"subject": "src/auth.py", "summary": "Read authentication module"}
        assert _event_text(event) == "src/auth.py: Read authentication module"


class TestExtractCitations:
    def test_path_with_slash(self):
        """Subject with '/' is treated as a file path."""
        result = _extract_citations("src/auth.py")
        assert result == [{"file_path": "src/auth.py"}]

    def test_known_extension(self):
        """Subject ending with known extension without '/' is a citation."""
        result = _extract_citations("config.toml")
        assert result == [{"file_path": "config.toml"}]

    def test_no_path_no_extension(self):
        """Subject without path separator or known extension returns empty."""
        result = _extract_citations("v2.0 release notes")
        assert result == []

    def test_case_insensitive_extension(self):
        """Extension check is case-insensitive."""
        result = _extract_citations("README.MD")
        assert result == [{"file_path": "README.MD"}]


# --- Strategy 1: Content-Hash Dedup ---


class TestStrategyContentHashDedup:
    def test_exact_duplicates_merged(self):
        """Events with identical normalized content produce one memory."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read src/a.py lines 1-10", "tags": "python"},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read src/a.py lines 1-10", "tags": "python"},
            {"id": 3, "session_id": "s1", "timestamp": "2026-01-01T00:02:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/b.py",
             "summary": "Read src/b.py lines 1-5", "tags": "python"},
        ]
        memories, unconsumed = _strategy_content_hash_dedup(events)

        # Events 1+2 are identical -> one memory; event 3 is unique -> unconsumed
        assert len(memories) == 1
        assert memories[0]["event_ids"] == [1, 2]
        assert memories[0]["strategy"] == "content_hash"
        assert memories[0]["memory_type"] == "fact"
        assert memories[0]["content"] == "[Read] src/a.py: Read src/a.py lines 1-10"
        assert memories[0]["tags"] == ["python"]
        assert memories[0]["citations"] == [{"file_path": "src/a.py"}]

        assert len(unconsumed) == 1
        assert unconsumed[0]["id"] == 3

    def test_whitespace_normalization(self):
        """Events with different whitespace/casing but same content are deduped."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read  src/a.py   lines 1-10", "tags": ""},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read src/a.py lines 1-10", "tags": ""},
        ]
        memories, unconsumed = _strategy_content_hash_dedup(events)
        # _content_hash normalizes whitespace, so these are duplicates
        assert len(memories) == 1
        assert memories[0]["event_ids"] == [1, 2]
        assert len(unconsumed) == 0

    def test_no_duplicates_all_unconsumed(self):
        """When all events are unique, no memories are produced."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read alpha", "tags": ""},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Edit", "subject": "src/b.py",
             "summary": "Edit beta", "tags": ""},
        ]
        memories, unconsumed = _strategy_content_hash_dedup(events)
        assert memories == []
        assert len(unconsumed) == 2
        assert {e["id"] for e in unconsumed} == {1, 2}

    def test_tag_merging_across_duplicates(self):
        """Tags from all duplicates in a group are merged and sorted."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read src/a.py lines 1-10", "tags": "python,auth"},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read", "subject": "src/a.py",
             "summary": "Read src/a.py lines 1-10", "tags": "python,backend"},
        ]
        memories, unconsumed = _strategy_content_hash_dedup(events)
        assert len(memories) == 1
        assert memories[0]["tags"] == ["auth", "backend", "python"]


# --- Strategy 2: Jaccard Similarity ---


class TestStrategyJaccardSimilarity:
    def test_similar_events_grouped(self):
        """Events with Jaccard similarity >= threshold are grouped."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/auth.py",
             "summary": "Read authentication module configuration setup",
             "tags": "python,auth"},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/auth.py",
             "summary": "Read authentication module configuration handler",
             "tags": "python,auth"},
            {"id": 3, "session_id": "s1", "timestamp": "2026-01-01T00:02:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Edit",
             "subject": "src/database.py",
             "summary": "Edited database migration schema completely different topic",
             "tags": "python,db"},
        ]
        memories, unconsumed = _strategy_jaccard_similarity(events)
        # Events 1 and 2 share "authentication", "module", "configuration" -> similar
        assert len(memories) == 1
        assert set(memories[0]["event_ids"]) == {1, 2}
        assert memories[0]["strategy"] == "jaccard_similarity"
        assert memories[0]["memory_type"] == "fact"
        # Merged content contains both event texts joined by "; "
        assert memories[0]["content"] == (
            "[Read] src/auth.py: Read authentication module configuration setup; "
            "[Read] src/auth.py: Read authentication module configuration handler"
        )
        assert memories[0]["tags"] == ["auth", "python"]
        assert memories[0]["citations"] == [{"file_path": "src/auth.py"}]
        # Event 3 should be unconsumed (different topic)
        assert len(unconsumed) == 1
        assert unconsumed[0]["id"] == 3

    def test_short_texts_skipped(self):
        """Events with fewer than MIN_MEANINGFUL_WORDS are passed through."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "a.py", "summary": "ok", "tags": ""},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "b.py", "summary": "ok", "tags": ""},
        ]
        memories, unconsumed = _strategy_jaccard_similarity(events)
        assert memories == []
        assert len(unconsumed) == 2

    def test_tag_boost(self):
        """Events at borderline similarity with 50%+ tag overlap get boosted above threshold.

        Without boost: Jaccard = 5/9 = 0.556 (below 0.6 threshold)
        With boost (+0.1): 0.656 (above 0.6 threshold)
        """
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/module.py",
             "summary": "authentication handler validates tokens config requests",
             "tags": "auth,security,python"},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/module.py",
             "summary": "authentication handler validates sessions config responses",
             "tags": "auth,security,python"},
        ]
        memories, unconsumed = _strategy_jaccard_similarity(events)
        # With tag boost, these should be grouped
        assert len(memories) == 1
        assert memories[0]["strategy"] == "jaccard_similarity"
        assert set(memories[0]["event_ids"]) == {1, 2}

    def test_single_event_returns_unconsumed(self):
        """A single event cannot be grouped, returned as unconsumed."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/a.py", "summary": "Read authentication module config",
             "tags": "python"},
        ]
        memories, unconsumed = _strategy_jaccard_similarity(events)
        assert memories == []
        assert len(unconsumed) == 1
        assert unconsumed[0]["id"] == 1


# --- Strategy 3: Tag Grouping ---


class TestStrategyTagGrouping:
    def test_shared_tags_grouped(self):
        """Events sharing >= MIN_SHARED_TAGS are grouped."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/a.py", "summary": "alpha work",
             "tags": "python,auth,backend"},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Edit",
             "subject": "src/b.py", "summary": "beta work",
             "tags": "python,auth,frontend"},
            {"id": 3, "session_id": "s1", "timestamp": "2026-01-01T00:02:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/c.py", "summary": "gamma work",
             "tags": "rust,wasm"},
        ]
        memories, unconsumed = _strategy_tag_grouping(events)
        # Events 1 and 2 share "python" and "auth" (2 tags >= MIN_SHARED_TAGS)
        assert len(memories) == 1
        assert set(memories[0]["event_ids"]) == {1, 2}
        assert memories[0]["strategy"] == "tag_grouping"
        assert memories[0]["tags"] == ["auth", "backend", "frontend", "python"]
        assert memories[0]["content"] == (
            "Related activities:\n"
            "- src/a.py: alpha work\n"
            "- src/b.py: beta work"
        )
        # Event 3 has no overlap -> unconsumed
        unconsumed_ids = {e["id"] for e in unconsumed}
        assert 3 in unconsumed_ids

    def test_no_tags_passed_through(self):
        """Events with no tags are passed through as unconsumed."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "a.py", "summary": "work", "tags": ""},
        ]
        memories, unconsumed = _strategy_tag_grouping(events)
        assert memories == []
        assert len(unconsumed) == 1

    def test_single_shared_tag_not_grouped(self):
        """Events sharing only 1 tag are not grouped (below MIN_SHARED_TAGS)."""
        events = [
            {"id": 1, "session_id": "s1", "timestamp": "2026-01-01T00:00:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Read",
             "subject": "a.py", "summary": "work", "tags": "python"},
            {"id": 2, "session_id": "s1", "timestamp": "2026-01-01T00:01:00", "project": "p",
             "event_type": "tool_use", "tool_name": "Edit",
             "subject": "b.py", "summary": "more", "tags": "python"},
        ]
        memories, unconsumed = _strategy_tag_grouping(events)
        assert memories == []
        assert len(unconsumed) == 2


# --- Strategy 4: Temporal Clustering ---


class TestStrategyTemporalClustering:
    def test_same_session_subject_within_gap(self):
        """Events in same session, same subject, within gap are clustered."""
        events = [
            {"id": 1, "session_id": "sess-1", "timestamp": "2026-01-01T10:00:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/main.py", "summary": "Read main header", "tags": "python"},
            {"id": 2, "session_id": "sess-1", "timestamp": "2026-01-01T10:15:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Edit",
             "subject": "src/main.py", "summary": "Edited main function", "tags": "python"},
        ]
        memories, unconsumed = _strategy_temporal_clustering(events)
        assert len(memories) == 1
        assert set(memories[0]["event_ids"]) == {1, 2}
        assert memories[0]["strategy"] == "temporal_clustering"
        assert memories[0]["content"] == (
            "Session activity on src/main.py: Read main header; Edited main function"
        )
        assert memories[0]["tags"] == ["python"]
        assert unconsumed == []

    def test_gap_exceeds_threshold_splits_clusters(self):
        """Events with gap > TEMPORAL_GAP_MINUTES become separate clusters."""
        events = [
            {"id": 1, "session_id": "sess-1", "timestamp": "2026-01-01T10:00:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/main.py", "summary": "Morning work", "tags": ""},
            {"id": 2, "session_id": "sess-1", "timestamp": "2026-01-01T11:00:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/main.py", "summary": "After break work", "tags": ""},
        ]
        memories, unconsumed = _strategy_temporal_clustering(events)
        assert len(memories) == 2  # Two separate clusters
        assert memories[0]["event_ids"] == [1]
        assert memories[1]["event_ids"] == [2]
        assert unconsumed == []

    def test_different_sessions_separate(self):
        """Events from different sessions are not merged even if close in time."""
        events = [
            {"id": 1, "session_id": "sess-1", "timestamp": "2026-01-01T10:00:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/main.py", "summary": "Session 1 work", "tags": ""},
            {"id": 2, "session_id": "sess-2", "timestamp": "2026-01-01T10:05:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/main.py", "summary": "Session 2 work", "tags": ""},
        ]
        memories, unconsumed = _strategy_temporal_clustering(events)
        assert len(memories) == 2  # Separate sessions
        assert memories[0]["event_ids"] == [1]
        assert memories[1]["event_ids"] == [2]

    def test_single_event_produces_memory(self):
        """A single event still produces a memory (fallback behavior)."""
        events = [
            {"id": 1, "session_id": "sess-1", "timestamp": "2026-01-01T10:00:00+00:00",
             "project": "p", "event_type": "tool_use", "tool_name": "Read",
             "subject": "src/main.py", "summary": "Solo read", "tags": "python"},
        ]
        memories, unconsumed = _strategy_temporal_clustering(events)
        assert len(memories) == 1
        assert memories[0]["event_ids"] == [1]
        assert memories[0]["content"] == "[Read] src/main.py: Solo read"
        assert unconsumed == []
