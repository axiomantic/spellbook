"""Integration tests for the full memory bridge pipeline.

These tests verify the end-to-end flow from hook capture through
consolidation to MEMORY.md regeneration.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

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

        # Simulate what the endpoint does when the hook dispatches to it
        with patch("hooks.spellbook_hook._http_post") as mock_post, \
             patch("hooks.spellbook_hook._resolve_git_context",
                   return_value=("/Users/alice/project", "main")):
            _memory_bridge("Write", data)

            # Verify two HTTP calls were dispatched
            assert mock_post.call_count == 2

            # Now simulate what the endpoint does with the content payload
            content_payload = mock_post.call_args_list[1][0][1]

        # Replay the endpoint logic: store the brief-summary event
        result = do_log_event(
            db_path=db,
            session_id=content_payload["session_id"],
            project=content_payload["project"],
            tool_name="auto_memory_bridge",
            subject=content_payload["file_path"],
            summary=f"MEMORY.md updated: 3 lines, sections: Key Facts",
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
        """Session init regenerates MEMORY.md from structured store.

        Creates a temp directory structure mimicking auto-memory, stores
        memories in DB, calls regenerate_memory_md_for_project, and
        verifies the MEMORY.md was written with the bootstrap header.
        """
        from spellbook.memory.bootstrap import regenerate_memory_md_for_project

        insert_memory(
            db_path=db,
            content="Project uses microservices architecture",
            memory_type="fact",
            namespace="tmp-test",
            tags=["architecture"],
            citations=[],
        )

        with patch("spellbook.memory.bootstrap._resolve_auto_memory_dir",
                    return_value=auto_memory_dir), \
             patch("spellbook.memory.bootstrap.get_db_path",
                    return_value=Path(db)), \
             patch("spellbook.memory.bootstrap.encode_cwd",
                    return_value="tmp-test"), \
             patch("spellbook.memory.bootstrap.resolve_repo_root",
                    return_value="/tmp/test"), \
             patch("spellbook.memory.bootstrap.get_current_branch",
                    return_value="main"):
            regenerate_memory_md_for_project("/tmp/test")

        memory_md = auto_memory_dir / "MEMORY.md"
        assert memory_md.exists()
        content = memory_md.read_text(encoding="utf-8")
        assert "spellbook-managed" in content
        assert "memory_store_memories" in content

    def test_regenerated_md_contains_stored_memories(self, db):
        """Regenerated MEMORY.md includes memories from the structured store.

        Stores specific memories with known content, generates MEMORY.md,
        and verifies those memories appear in the output.
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

        result = generate_memory_md(
            db_path=db,
            project_path="/tmp/test",
            namespace="tmp-test",
        )

        assert "tests with -x flag" in result
        assert "PostgreSQL" in result

    def test_full_cycle(self, db, auto_memory_dir):
        """Full cycle: write -> capture -> consolidate -> regenerate -> verify.

        This is the critical end-to-end test simulating the complete lifecycle:
        1. Hook captures a Write to auto-memory (simulated via do_log_event)
        2. Endpoint stores events in DB
        3. Memories are consolidated into structured store (simulated via insert_memory)
        4. Session init regenerates MEMORY.md
        5. Regenerated file contains the original content (transformed)
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
        result = generate_memory_md(
            db_path=db,
            project_path="/tmp/test",
            namespace="tmp-test",
        )

        # Step 5: Verify content
        assert "spellbook-managed" in result
        assert "RabbitMQ" in result
        assert "memory_store_memories" in result
