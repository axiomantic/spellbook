"""Tests for memory consolidation pipeline."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

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


# --- consolidate_batch ---


class TestConsolidateBatch:
    def test_success(self, db):
        """Successful consolidation creates memories and marks events."""
        _seed_events(db, 15)

        mock_response = json.dumps({
            "memories": [
                {
                    "content": "Modules are organized by number",
                    "memory_type": "fact",
                    "tags": ["organization", "modules"],
                    "citations": [
                        {"file_path": "src/module_0.py", "line_range": "1-10", "snippet": "..."}
                    ],
                }
            ]
        })

        with patch(
            "spellbook_mcp.memory_consolidation._call_llm",
            return_value=mock_response,
        ):
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result["status"] == "success"
        assert result["events_consolidated"] == 15
        assert result["memories_created"] == 1
        assert "batch_id" in result
        # Verify batch_id is a valid UUID4 string
        import uuid
        uuid.UUID(result["batch_id"], version=4)

        # Events should now be marked consolidated
        remaining = get_unconsolidated_events(db, limit=50)
        assert remaining == []

        # Verify the memory was actually inserted into the database
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT content, memory_type, namespace FROM memories WHERE namespace = ?",
            ("Users-alice-myproject",),
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Modules are organized by number"
        assert rows[0][1] == "fact"
        assert rows[0][2] == "Users-alice-myproject"

    def test_llm_failure_leaves_events_unconsolidated(self, db):
        """LLM failure leaves events unconsolidated and logs error."""
        _seed_events(db, 15)

        with patch(
            "spellbook_mcp.memory_consolidation._call_llm",
            side_effect=RuntimeError("LLM timeout"),
        ):
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result == {
            "status": "error",
            "error": "LLM timeout",
            "events_consolidated": 0,
            "memories_created": 0,
        }

        # Events should remain unconsolidated
        remaining = get_unconsolidated_events(db, limit=50)
        assert len(remaining) == 15

        # Verify audit log entry was created
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT action, details FROM memory_audit_log WHERE action = 'consolidation_error'"
        )
        row = cursor.fetchone()
        assert row is not None
        details = json.loads(row[1])
        assert details["error"] == "LLM timeout"
        assert details["event_count"] == 15

    def test_empty_parse_marks_events_consolidated(self, db):
        """Empty LLM parse result still marks events as consolidated (prevents infinite retry)."""
        _seed_events(db, 15)

        # LLM returns valid JSON but no extractable memories
        mock_response = json.dumps({"memories": []})

        with patch(
            "spellbook_mcp.memory_consolidation._call_llm",
            return_value=mock_response,
        ):
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result == {
            "status": "success",
            "events_consolidated": 15,
            "memories_created": 0,
        }

        # Events should be marked consolidated despite no memories
        remaining = get_unconsolidated_events(db, limit=50)
        assert remaining == []

    def test_no_events(self, db):
        """No unconsolidated events returns early."""
        result = consolidate_batch(
            db_path=db,
            namespace="Users-alice-myproject",
        )
        assert result == {
            "status": "no_events",
            "events_consolidated": 0,
            "memories_created": 0,
        }

    def test_dedup_via_content_hash(self, db):
        """Duplicate content produces only one memory (dedup via content_hash)."""
        _seed_events(db, 15)

        mock_response = json.dumps({
            "memories": [
                {
                    "content": "Duplicated fact",
                    "memory_type": "fact",
                    "tags": ["dup"],
                    "citations": [],
                },
                {
                    "content": "Duplicated fact",
                    "memory_type": "fact",
                    "tags": ["dup"],
                    "citations": [],
                },
            ]
        })

        with patch(
            "spellbook_mcp.memory_consolidation._call_llm",
            return_value=mock_response,
        ):
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result["status"] == "success"
        assert result["events_consolidated"] == 15
        # Both entries get the same memory ID due to dedup, but memories_created
        # counts all IDs returned (including the dedup'd one that returns existing ID)
        assert result["memories_created"] == 2

        # But only one memory actually exists in the database
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE namespace = ?",
            ("Users-alice-myproject",),
        )
        assert cursor.fetchone()[0] == 1

    def test_piggyback_gc(self, db):
        """Consolidation calls purge_deleted at the end."""
        _seed_events(db, 15)

        mock_response = json.dumps({
            "memories": [
                {
                    "content": "GC test memory",
                    "memory_type": "fact",
                    "tags": ["gc"],
                    "citations": [],
                }
            ]
        })

        with patch(
            "spellbook_mcp.memory_consolidation._call_llm",
            return_value=mock_response,
        ), patch(
            "spellbook_mcp.memory_consolidation.purge_deleted",
            return_value=2,
        ) as mock_purge:
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result["purged"] == 2
        mock_purge.assert_called_once_with(db)


# --- _call_llm ---


class TestCallLlm:
    def test_missing_api_key_raises(self):
        """_call_llm raises RuntimeError when ANTHROPIC_API_KEY is not set."""
        from spellbook_mcp.memory_consolidation import _call_llm

        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                _call_llm("test prompt")

    def test_calls_anthropic_api(self):
        """_call_llm calls the Anthropic messages API with correct parameters."""
        from spellbook_mcp.memory_consolidation import _call_llm

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"memories": []}')]

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key123"}):
            with patch("spellbook_mcp.memory_consolidation.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client_instance
                mock_anthropic.RateLimitError = Exception
                mock_anthropic.APIError = Exception

                result = _call_llm("test prompt")

        assert result == '{"memories": []}'
        mock_anthropic.Anthropic.assert_called_once_with(api_key="sk-ant-test-key123")
        mock_client_instance.messages.create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": "test prompt"}],
        )

    def test_retries_on_rate_limit(self):
        """_call_llm retries with exponential backoff on RateLimitError."""
        from spellbook_mcp.memory_consolidation import _call_llm

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        mock_client_instance = MagicMock()

        # Create a real exception class for RateLimitError
        class FakeRateLimitError(Exception):
            pass

        class FakeAPIError(Exception):
            pass

        # First two calls raise rate limit, third succeeds
        mock_client_instance.messages.create.side_effect = [
            FakeRateLimitError("rate limited"),
            FakeRateLimitError("rate limited"),
            mock_response,
        ]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key123"}):
            with patch("spellbook_mcp.memory_consolidation.anthropic") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client_instance
                mock_anthropic.RateLimitError = FakeRateLimitError
                mock_anthropic.APIError = FakeAPIError

                with patch("time.sleep") as mock_sleep:
                    result = _call_llm("test prompt")

        assert result == "ok"
        assert mock_client_instance.messages.create.call_count == 3
        # Verify exponential backoff: sleep(1), sleep(2)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)


# --- Bibliographic coupling after consolidation ---


class TestBibliographicCouplingIntegration:
    def test_consolidation_creates_bibliographic_links(self, db):
        """After consolidation with two memories citing the same file,
        verify memory_links contains a bibliographic coupling entry
        with correct Jaccard weight."""
        _seed_events(db, 15)

        # LLM returns two memories that share a citation (src/shared.py)
        mock_response = json.dumps({
            "memories": [
                {
                    "content": "Module handles authentication logic",
                    "memory_type": "fact",
                    "tags": ["auth"],
                    "citations": [
                        {"file_path": "src/shared.py", "line_range": "1-10", "snippet": "..."},
                        {"file_path": "src/auth.py", "line_range": "1-5", "snippet": "..."},
                    ],
                },
                {
                    "content": "Module handles user registration",
                    "memory_type": "fact",
                    "tags": ["users"],
                    "citations": [
                        {"file_path": "src/shared.py", "line_range": "20-30", "snippet": "..."},
                        {"file_path": "src/models.py", "line_range": "1-5", "snippet": "..."},
                    ],
                },
            ]
        })

        with patch(
            "spellbook_mcp.memory_consolidation._call_llm",
            return_value=mock_response,
        ):
            result = consolidate_batch(
                db_path=db,
                namespace="Users-alice-myproject",
            )

        assert result["status"] == "success"
        assert result["memories_created"] == 2

        # Verify bibliographic coupling link was created in memory_links
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT memory_a, memory_b, link_type, weight FROM memory_links "
            "WHERE link_type = 'bibliographic'"
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row[2] == "bibliographic"
        # Jaccard: |{shared.py}| / |{shared.py, auth.py, models.py}| = 1/3
        assert abs(row[3] - (1.0 / 3.0)) < 0.01


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
        assert len(memories) >= 1
        # Verify events 1+2 are grouped together
        grouped_ids = set()
        for m in memories:
            grouped_ids.update(m["event_ids"])
        assert {1, 2}.issubset(grouped_ids)
        assert memories[0]["strategy"] == "jaccard_similarity"
        # Event 3 should be unconsumed (different topic)
        unconsumed_ids = {e["id"] for e in unconsumed}
        assert 3 in unconsumed_ids

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
