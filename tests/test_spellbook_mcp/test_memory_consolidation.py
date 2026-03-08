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
