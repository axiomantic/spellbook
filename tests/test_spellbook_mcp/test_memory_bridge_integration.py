"""Integration tests for the full memory bridge pipeline.

These tests verify the end-to-end flow from hook capture through
consolidation to MEMORY.md regeneration.
"""

import tripwire
import pytest
from pathlib import Path

from spellbook.core.db import init_db, close_all_connections
from spellbook.memory.store import insert_memory, get_unconsolidated_events
from spellbook.memory.tools import do_log_event


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


@pytest.fixture
def auto_memory_dir(tmp_path):
    memory_dir = tmp_path / ".claude" / "projects" / "-tmp-test" / "memory"
    memory_dir.mkdir(parents=True)
    return memory_dir


@pytest.mark.integration
class TestMemoryBridgeIntegration:
    """End-to-end integration tests for the memory bridge system."""

    def test_bridge_hook_to_endpoint_roundtrip(self, db):
        """Hook captures a Write, endpoint stores events in DB.

        Simulates the hook dispatching HTTP calls, then replays what the
        endpoint would do with the content payload to verify events land
        in the database correctly.
        """
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md"
        data = {
            "tool_input": {
                "file_path": file_path,
                "content": "# Key Facts\n- Uses Python 3.10\n- FastAPI backend",
            },
            "cwd": "/Users/alice/project",
            "session_id": "integration-test-1",
        }

        # Capture call args from _http_post
        post_calls = []
        mock_post = tripwire.mock("hooks.spellbook_hook:_http_post")
        mock_post.calls(lambda *a, **kw: post_calls.append((a, kw))).calls(
            lambda *a, **kw: post_calls.append((a, kw))
        )
        mock_git = tripwire.mock("hooks.spellbook_hook:_resolve_git_context")
        mock_git.returns(("/Users/alice/project", "main"))

        with tripwire:
            _memory_bridge("Write", data)

        # Verify two HTTP calls were dispatched
        assert len(post_calls) == 2

        with tripwire.in_any_order():
            mock_git.assert_call(
                args=(data["cwd"],),
                kwargs={},
            )
            mock_post.assert_call(
                args=(post_calls[0][0][0], post_calls[0][0][1]),
                kwargs=post_calls[0][1],
            )
            mock_post.assert_call(
                args=(post_calls[1][0][0], post_calls[1][0][1]),
                kwargs=post_calls[1][1],
            )

        # Now simulate what the endpoint does with the content payload
        content_payload = post_calls[1][0][1]

        # Replay the endpoint logic: store the brief-summary event
        result = do_log_event(
            db_path=db,
            session_id=content_payload["session_id"],
            project=content_payload["project"],
            tool_name="auto_memory_bridge",
            subject=content_payload["file_path"],
            summary="MEMORY.md updated: 3 lines, sections: Key Facts",
            tags="auto-memory,bridge,memory",
            event_type="auto_memory_bridge",
            branch=content_payload["branch"],
        )
        assert result["status"] == "logged"
        assert result["event_id"] > 0

        events = get_unconsolidated_events(db, limit=10)
        assert len(events) == 1
        assert events[0]["event_type"] == "auto_memory_bridge"

    def test_bridge_content_triggers_consolidation(self, db):
        """Enough bridge events trigger consolidation check.

        Stores EVENT_THRESHOLD events and verifies should_consolidate
        returns True, confirming the pipeline threshold works for
        bridge-sourced events.
        """
        from spellbook.memory.consolidation import should_consolidate, EVENT_THRESHOLD

        for i in range(EVENT_THRESHOLD):
            do_log_event(
                db_path=db,
                session_id="integration-test-2",
                project="Users-alice-project",
                tool_name="auto_memory_bridge",
                subject=f"/path/file_{i}.md",
                summary=f"bridge event {i}",
                tags="auto-memory,bridge",
                event_type="auto_memory_bridge",
                branch="main",
            )

        assert should_consolidate(db) is True

    def test_session_init_regenerates_memory_md(self, db, auto_memory_dir, tmp_path):
        """Session init regenerates MEMORY.md with the static template.

        Creates a temp directory structure mimicking auto-memory, calls
        regenerate_memory_md_for_project, and verifies the MEMORY.md
        was written with the redirect template header.
        """
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        mock_resolve = tripwire.mock("spellbook.memory.bootstrap:_resolve_auto_memory_dir")
        mock_resolve.returns(auto_memory_dir)
        mock_db_path = tripwire.mock("spellbook.memory.bootstrap:get_db_path")
        mock_db_path.returns(Path(db))
        mock_encode = tripwire.mock("spellbook.memory.bootstrap:encode_cwd")
        mock_encode.returns("tmp-test")

        with tripwire:
            regenerate_memory_md_for_project("/tmp/test")

        mock_resolve.assert_call(args=("/tmp/test",), kwargs={})
        mock_db_path.assert_call(args=(), kwargs={})
        mock_encode.assert_call(args=("/tmp/test",), kwargs={})

        memory_md = auto_memory_dir / "MEMORY.md"
        assert memory_md.exists()
        content = memory_md.read_text(encoding="utf-8")
        assert "# Spellbook Memory System" in content
        assert "memory_store" in content
        assert "memory_recall" in content

    def test_regenerated_md_is_static_template(self, db):
        """Regenerated MEMORY.md is the static redirect template.

        Memories are stored in the DB but do NOT appear in the
        generated MEMORY.md (they are accessed via memory_recall).
        """
        from spellbook.memory.bootstrap import generate_memory_md

        insert_memory(
            db_path=db,
            content="Always run tests with -x flag",
            memory_type="convention",
            namespace="tmp-test",
            tags=["testing"],
            citations=[],
        )
        insert_memory(
            db_path=db,
            content="Database uses PostgreSQL 15",
            memory_type="fact",
            namespace="tmp-test",
            tags=["database"],
            citations=[],
        )

        result = generate_memory_md()

        # Template is present
        assert "# Spellbook Memory System" in result
        assert "memory_recall" in result
        # DB content does NOT appear in the template
        assert "tests with -x flag" not in result
        assert "PostgreSQL" not in result

    def test_full_cycle(self, db, auto_memory_dir):
        """Full cycle: write -> capture -> consolidate -> regenerate -> verify.

        This is the critical end-to-end test simulating the complete lifecycle:
        1. Hook captures a Write to auto-memory (simulated via do_log_event)
        2. Endpoint stores events in DB
        3. Memories are consolidated into structured store (simulated via insert_memory)
        4. Session init regenerates MEMORY.md
        5. Regenerated file contains the redirect template (not captured content)
        """
        from spellbook.memory.bootstrap import generate_memory_md

        # Step 1-2: Simulate bridge capturing content (what the endpoint does)
        do_log_event(
            db_path=db,
            session_id="full-cycle",
            project="tmp-test",
            tool_name="auto_memory_bridge",
            subject="/path/MEMORY.md",
            summary="MEMORY.md updated: 5 lines, sections: Architecture",
            tags="auto-memory,bridge,memory",
            event_type="auto_memory_bridge",
            branch="main",
        )

        # Step 3: Simulate consolidation result (memories extracted from events)
        insert_memory(
            db_path=db,
            content="Service uses event-driven architecture with RabbitMQ",
            memory_type="fact",
            namespace="tmp-test",
            tags=["architecture", "rabbitmq"],
            citations=[],
        )

        # Step 4: Regenerate MEMORY.md
        result = generate_memory_md()

        # Step 5: Verify template content (not DB content)
        assert "# Spellbook Memory System" in result
        assert "memory_store" in result
        assert "memory_recall" in result
        # DB content is accessed via MCP tools, not rendered in the file
        assert "RabbitMQ" not in result
