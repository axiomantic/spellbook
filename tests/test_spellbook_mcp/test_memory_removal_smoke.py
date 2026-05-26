"""Replacement smoke coverage after the memory/soul system removal (Task 7d).

Deleting the soul-chain tests removed the ONLY coverage of the resume/injection
boundary, so this file replaces it at the system-boundary level (design doc
section 7.3). These tests are the green-mirage guard for the removal: each one
fails if its target regression is reintroduced.

No mocking is used. Tests exercise the real functions against real temporary
SQLite databases and real in-memory session message lists. ``monkeypatch`` is
used only to isolate ``HOME`` (environment), per the project's tripwire-only
mocking policy.
"""

import asyncio
import json

from spellbook.core.db import close_all_connections, get_connection, init_db


# ---------------------------------------------------------------------------
# Test 1 — Server import + mapper configuration + zero memory_* tools (S-1 / C-1)
# ---------------------------------------------------------------------------

def test_server_imports_no_memory_tools_and_mappers_configure():
    """Importing the server registers tools, none named ``memory_*``; and the
    SQLAlchemy mappers configure without an InvalidRequestError.

    Primary green-mirage guard. If a missed importer re-registers a memory tool,
    the ``memory_*`` assertion fails. If ``Subagent`` still references the deleted
    ``Soul`` via ``relationship("Soul")`` / ``ForeignKey("souls.id")``,
    ``configure_mappers()`` raises ``InvalidRequestError`` here, turning a
    server-startup crash into a deterministic test failure.
    """
    from spellbook.mcp.server import mcp, register_all_tools

    register_all_tools()

    # mcp.list_tools() is async in FastMCP v3; drive it on a fresh loop.
    tools = asyncio.new_event_loop().run_until_complete(mcp.list_tools())
    memory_tool_names = sorted(
        tool.name for tool in tools if tool.name.startswith("memory_")
    )
    assert memory_tool_names == []

    # Force mapper configuration. A dangling Subagent -> Soul relationship would
    # raise sqlalchemy.exc.InvalidRequestError here.
    import spellbook.db.spellbook_models  # noqa: F401  (registers mapped classes)
    from sqlalchemy.orm import configure_mappers

    configure_mappers()  # must not raise

    # The Subagent mapper must have no relationship to the deleted Soul model.
    from spellbook.db.spellbook_models import Subagent

    relationship_keys = sorted(Subagent.__mapper__.relationships.keys())
    assert relationship_keys == []

    column_names = sorted(column.key for column in Subagent.__mapper__.columns)
    assert column_names == [
        "id",
        "last_output",
        "persona",
        "project_path",
        "prompt_summary",
        "spawned_at",
        "status",
    ]


# ---------------------------------------------------------------------------
# Test 2 — Clean session_init resume (config.py / resume.py / watcher collapse)
# ---------------------------------------------------------------------------

def test_session_init_resume_is_always_unavailable():
    """``_get_resume_context`` collapsed to a constant, and ``session_init``
    surfaces exactly one resume field: ``resume_available`` is False.

    Guards the config.py / resume.py / watcher.py soul-resume collapse. If a soul
    resume read were reintroduced, ``_get_resume_context`` would return more than
    the single constant key, or ``session_init`` would expose extra ``resume_*``
    fields.
    """
    from spellbook.core.config import _get_resume_context

    # The collapse point returns exactly one key, regardless of continuation text.
    assert _get_resume_context("let's continue where we left off", "/tmp/no-proj") == {
        "resume_available": False
    }
    assert _get_resume_context(None, None) == {"resume_available": False}


def test_session_init_returns_clean_resume_fields(monkeypatch, tmp_path):
    """End-to-end ``session_init`` against an isolated HOME returns
    ``resume_available`` False and no other ``resume_*`` field, without raising.

    HOME isolation (environment-only monkeypatch) prevents the developer's real
    spellbook.json / state from perturbing the result so the resume-field
    invariant is deterministic.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SPELLBOOK_CONFIG_DIR", raising=False)
    monkeypatch.delenv("SPELLBOOK_DIR", raising=False)

    from spellbook.core.config import session_init

    project_path = str(tmp_path / "unused-project")
    result = session_init(
        continuation_message="continue please",
        project_path=project_path,
    )

    assert result["resume_available"] is False

    resume_keys = sorted(key for key in result if key.startswith("resume_"))
    assert resume_keys == ["resume_available"]


# ---------------------------------------------------------------------------
# Test 3 — Kept-feature smoke (regression guard for preserved behavior)
# ---------------------------------------------------------------------------

def test_kept_session_listing_shape(tmp_path):
    """``list_sessions_with_samples`` (backing ``find_session`` / ``list_sessions``)
    still returns its full metadata shape after the removal.

    NOTE: ``last_compact_summary`` is STILL emitted by the current source. The
    design doc (section 5) called for dropping this dead key, but no
    implementation task was ever created for that edit, so the production source
    retains it. This test asserts the REAL current shape (key present) rather
    than the design-intended shape; the gap is escalated to the orchestrator.
    """
    from spellbook.sessions.parser import list_sessions_with_samples

    session_path = tmp_path / "auth-flow.jsonl"
    msg_user = {
        "slug": "auth-flow",
        "type": "user",
        "timestamp": "2026-01-01T10:00:00Z",
        "message": {"content": "Implement auth"},
    }
    msg_assistant = {
        "type": "assistant",
        "timestamp": "2026-01-01T10:01:00Z",
        "message": {"content": "Done"},
    }
    session_path.write_text(
        json.dumps(msg_user) + "\n" + json.dumps(msg_assistant) + "\n",
        encoding="utf-8",
    )

    sessions = list_sessions_with_samples(str(tmp_path), limit=5)

    expected_char_count = len(json.dumps(msg_user)) + len(json.dumps(msg_assistant))
    assert sessions == [
        {
            "slug": "auth-flow",
            "custom_title": None,
            "path": str(session_path),
            "created": "2026-01-01T10:00:00Z",
            "last_activity": "2026-01-01T10:01:00Z",
            "message_count": 2,
            "char_count": expected_char_count,
            "compact_count": 0,
            "last_compact_line": None,
            "first_user_message": "Implement auth",
            "last_compact_summary": None,  # design-intended drop NOT yet tasked
            "recent_messages": ["Implement auth", "Done"],
        }
    ]


def test_heartbeat_age_reads_heartbeat_table_directly(tmp_path):
    """``health/checker._get_heartbeat_age`` reads the ``heartbeat`` table via
    direct SQL (M-1): None when no row, a float age when a row exists.

    Guards that the heartbeat-age read survived the removal and still queries the
    preserved ``heartbeat`` table directly rather than via a deleted soul path.
    """
    from datetime import datetime, timezone

    from spellbook.health.checker import _get_heartbeat_age

    db_path = str(tmp_path / "spellbook.db")
    init_db(db_path)

    # No heartbeat row yet -> None.
    assert _get_heartbeat_age(db_path) is None

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO heartbeat (id, timestamp) VALUES (1, ?)",
        (datetime.now(timezone.utc).isoformat(),),
    )
    conn.commit()

    age = _get_heartbeat_age(db_path)
    assert isinstance(age, float)
    assert 0.0 <= age < 60.0

    close_all_connections()


def test_database_health_check_passes_after_souls_dropped(tmp_path):
    """``health/checker._check_database`` reports a fresh DB HEALTHY after the
    ``souls`` table is dropped (R13).

    Guards that ``souls`` was removed from ``critical_tables`` so an upgraded DB
    (where ``souls`` no longer exists) is not reported unhealthy.
    """
    from spellbook.health.checker import HealthStatus, _check_database

    db_path = str(tmp_path / "spellbook.db")
    init_db(db_path)

    check = _check_database(db_path)
    assert check.domain == "database"
    assert check.status == HealthStatus.HEALTHY

    # souls must NOT be among the required tables, and must be absent.
    conn = get_connection(db_path)
    existing = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "souls" not in existing
    assert {"heartbeat", "workflow_state"} <= existing

    close_all_connections()


def test_skill_outcome_analysis_runs():
    """The ``SkillOutcome`` analysis pipeline (skill_analyzer) still runs end to
    end: extract invocations -> aggregate metrics -> build SkillOutcome.

    Guards that skill-outcome analytics, a preserved feature, was not collaterally
    removed with the memory system. Uses a deterministic in-memory message list.
    """
    from spellbook.sessions.skill_analyzer import (
        OUTCOME_COMPLETED,
        SkillOutcome,
        aggregate_metrics,
        extract_skill_invocations,
    )

    messages = [
        {"type": "user", "message": {"content": "go"}},
        {
            "type": "assistant",
            "timestamp": "2026-01-01T10:00:00Z",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "develop"}}
                ]
            },
        },
        {"type": "assistant", "message": {"content": "working"}},
    ]

    invocations = extract_skill_invocations(messages, "sess.jsonl")
    assert len(invocations) == 1
    assert invocations[0].skill == "develop"
    assert invocations[0].version is None
    assert invocations[0].completed is True

    metrics = aggregate_metrics(invocations)
    assert sorted(metrics.keys()) == ["develop"]
    develop_metrics = metrics["develop"]
    assert develop_metrics.skill == "develop"
    assert develop_metrics.invocations == 1
    assert develop_metrics.completions == 1

    outcome = SkillOutcome.from_invocation(
        invocations[0], session_id="sess", project_encoded="proj"
    )
    assert outcome.skill_name == "develop"
    assert outcome.session_id == "sess"
    assert outcome.project_encoded == "proj"
    assert outcome.outcome == OUTCOME_COMPLETED


# ---------------------------------------------------------------------------
# Test 4 — DB drop idempotency + subagents schema (S-3)
# ---------------------------------------------------------------------------

def test_db_drop_idempotent_and_subagents_schema_clean(tmp_path):
    """Initializing the DB twice drops the memory + soul tables (including the
    ``memories_fts`` FTS table), leaves the preserved tables, and does not raise;
    and the surviving ``subagents`` schema no longer references ``souls`` (S-3).
    """
    db_path = str(tmp_path / "spellbook.db")

    init_db(db_path)
    init_db(db_path)  # second call must be a no-op, not raise

    conn = get_connection(db_path)
    existing_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    # Memory + soul tables (incl. the FTS virtual table) are absent.
    absent = {
        "memory_audit_log",
        "memory_branches",
        "memory_links",
        "memory_citations",
        "raw_events",
        "memories_fts",
        "memories",
        "souls",
    }
    assert absent & existing_tables == set()

    # Preserved tables exist.
    preserved = {"skill_outcomes", "workflow_state", "heartbeat", "subagents"}
    assert preserved <= existing_tables

    # subagents schema: no FK to souls, no soul_id column (fresh-init determinism).
    foreign_keys = conn.execute("PRAGMA foreign_key_list(subagents)").fetchall()
    assert foreign_keys == []

    subagents_columns = [
        row[1] for row in conn.execute("PRAGMA table_info(subagents)").fetchall()
    ]
    assert subagents_columns == [
        "id",
        "project_path",
        "spawned_at",
        "prompt_summary",
        "persona",
        "status",
        "last_output",
    ]

    close_all_connections()
