"""Tests for spellbook.db ORM model definitions.

Verifies that all 29 spellbook.db SQLAlchemy models match the actual
CREATE TABLE schemas defined in spellbook/core/db.py and
spellbook/coordination/curator.py.
"""

import json

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from spellbook.db.base import SpellbookBase


# All 29 expected tables and their exact column definitions.
# Derived from spellbook/core/db.py and
# spellbook/coordination/curator.py.
EXPECTED_TABLES = {
    "souls": [
        "id", "project_path", "session_id", "bound_at", "persona",
        "active_skill", "skill_phase", "todos", "recent_files",
        "exact_position", "workflow_pattern", "summoned_at",
    ],
    "subagents": [
        "id", "soul_id", "project_path", "spawned_at",
        "prompt_summary", "persona", "status", "last_output",
    ],
    "decisions": [
        "id", "project_path", "decision", "rationale", "decided_at",
    ],
    "corrections": [
        "id", "project_path", "constraint_type", "constraint_text",
        "recorded_at",
    ],
    "heartbeat": [
        "id", "timestamp",
    ],
    "skill_outcomes": [
        "id", "skill_name", "skill_version", "session_id",
        "project_encoded", "start_time", "end_time", "duration_seconds",
        "outcome", "tokens_used", "corrections", "retries",
        "experiment_variant_id", "created_at",
    ],
    "telemetry_config": [
        "id", "enabled", "endpoint_url", "last_sync", "updated_at",
    ],
    "workflow_state": [
        "id", "project_path", "state_json", "trigger", "created_at",
        "updated_at",
    ],
    "experiments": [
        "id", "name", "skill_name", "status", "description",
        "created_at", "started_at", "completed_at",
    ],
    "experiment_variants": [
        "id", "experiment_id", "variant_name", "skill_version",
        "weight", "created_at",
    ],
    "variant_assignments": [
        "id", "experiment_id", "session_id", "variant_id",
        "assigned_at",
    ],
    "trust_registry": [
        "id", "content_hash", "source", "trust_level",
        "registered_at", "expires_at", "registered_by",
        "signature", "signing_key_id", "analysis_status", "analysis_at",
    ],
    "security_events": [
        "id", "event_type", "severity", "source", "detail",
        "session_id", "tool_name", "action_taken", "created_at",
    ],
    "canary_tokens": [
        "id", "token", "token_type", "context", "created_at",
        "triggered_at", "triggered_by",
    ],
    "security_mode": [
        "id", "mode", "updated_at", "updated_by", "auto_restore_at",
    ],
    "spawn_rate_limit": [
        "id", "timestamp", "session_id",
    ],
    "memories": [
        "id", "content", "memory_type", "namespace", "branch",
        "scope", "importance", "created_at", "accessed_at", "status",
        "deleted_at", "content_hash", "meta",
    ],
    "memory_citations": [
        "id", "memory_id", "file_path", "line_range",
        "content_snippet",
    ],
    "memory_links": [
        "memory_a", "memory_b", "link_type", "weight", "last_seen",
    ],
    "memory_branches": [
        "memory_id", "branch_name", "association_type", "created_at",
    ],
    "raw_events": [
        "id", "session_id", "timestamp", "project", "branch",
        "event_type", "tool_name", "subject", "summary", "tags",
        "consolidated", "batch_id",
    ],
    "memory_audit_log": [
        "id", "timestamp", "action", "memory_id", "details",
    ],
    "stint_stack": [
        "id", "project_path", "session_id", "stack_json", "updated_at",
    ],
    "stint_correction_events": [
        "id", "project_path", "session_id", "correction_type",
        "old_stack_json", "new_stack_json", "diff_summary", "created_at",
    ],
    "curator_events": [
        "id", "session_id", "tool_ids", "tokens_saved", "strategy",
        "timestamp",
    ],
    "intent_checks": [
        "id", "session_id", "content_hash", "source_tool",
        "classification", "confidence", "evidence",
        "checked_at", "latency_ms", "cached",
    ],
    "session_content_accumulator": [
        "id", "session_id", "content_hash", "source_tool",
        "content_summary", "content_size", "received_at", "expires_at",
    ],
    "sleuth_budget": [
        "id", "session_id", "calls_remaining", "reset_at",
    ],
    "sleuth_cache": [
        "id", "content_hash", "classification", "confidence",
        "cached_at", "expires_at",
    ],
}


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with all spellbook models."""
    from spellbook.db.spellbook_models import (  # noqa: F401 - triggers registration
        Soul, Subagent, Decision, Correction, Heartbeat,
        SkillOutcome, TelemetryConfig, WorkflowState,
        Experiment, ExperimentVariant, VariantAssignment,
        TrustRegistry, SecurityEvent, CanaryToken,
        SecurityMode, SpawnRateLimit, Memory, MemoryCitation,
        MemoryLink, MemoryBranch, RawEvent, MemoryAuditLog,
        StintStack, StintCorrectionEvent, CuratorEvent,
        IntentCheck, SessionContentAccumulator, SleuthBudget, SleuthCache,
    )
    engine = create_engine("sqlite:///:memory:")
    SpellbookBase.metadata.create_all(engine)
    return engine


class TestAllTablesExist:
    """Verify all 29 expected tables are created by the ORM models."""

    def test_all_29_tables_created(self, engine):
        """All 29 spellbook.db tables must exist after create_all."""
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        expected = set(EXPECTED_TABLES.keys())
        missing = expected - table_names
        extra = table_names - expected
        assert missing == set(), f"Missing tables: {missing}"
        # Extra tables are acceptable (e.g. SQLAlchemy internals) but none expected
        assert extra == set(), f"Unexpected extra tables: {extra}"


class TestTableColumns:
    """Verify every table has exactly the expected columns."""

    @pytest.mark.parametrize("table_name,expected_columns", list(EXPECTED_TABLES.items()))
    def test_table_has_exact_columns(self, engine, table_name, expected_columns):
        """Table {table_name} must have exactly the expected columns."""
        inspector = inspect(engine)
        actual_columns = [col["name"] for col in inspector.get_columns(table_name)]
        assert sorted(actual_columns) == sorted(expected_columns), (
            f"Column mismatch for {table_name}.\n"
            f"  Expected: {sorted(expected_columns)}\n"
            f"  Actual:   {sorted(actual_columns)}\n"
            f"  Missing:  {sorted(set(expected_columns) - set(actual_columns))}\n"
            f"  Extra:    {sorted(set(actual_columns) - set(expected_columns))}"
        )


class TestSoulModel:
    """Tests for the Soul ORM model."""

    def test_to_dict_all_fields(self, engine):
        """Soul.to_dict() returns all columns with correct values."""
        from spellbook.db.spellbook_models import Soul
        soul = Soul(
            id="soul-1",
            project_path="/home/user/project",
            session_id="sess-abc",
            bound_at="2026-01-15T10:00:00",
            persona="A helpful assistant",
            active_skill="develop",
            skill_phase="DESIGN",
            todos='[{"text": "implement feature", "done": false}]',
            recent_files='["src/main.py", "tests/test_main.py"]',
            exact_position="line 42 of main.py",
            workflow_pattern="TDD",
            summoned_at="2026-01-15T09:00:00",
        )
        d = soul.to_dict()
        assert d == {
            "id": "soul-1",
            "project_path": "/home/user/project",
            "session_id": "sess-abc",
            "bound_at": "2026-01-15T10:00:00",
            "persona": "A helpful assistant",
            "active_skill": "develop",
            "skill_phase": "DESIGN",
            "todos": [{"text": "implement feature", "done": False}],
            "recent_files": ["src/main.py", "tests/test_main.py"],
            "exact_position": "line 42 of main.py",
            "workflow_pattern": "TDD",
            "summoned_at": "2026-01-15T09:00:00",
        }

    def test_to_dict_null_json_fields(self, engine):
        """Soul.to_dict() handles null JSON fields gracefully."""
        from spellbook.db.spellbook_models import Soul
        soul = Soul(
            id="soul-2",
            project_path="/test",
            todos=None,
            recent_files=None,
        )
        d = soul.to_dict()
        assert d == {
            "id": "soul-2",
            "project_path": "/test",
            "session_id": None,
            "bound_at": None,
            "persona": None,
            "active_skill": None,
            "skill_phase": None,
            "todos": None,
            "recent_files": None,
            "exact_position": None,
            "workflow_pattern": None,
            "summoned_at": None,
        }

    def test_relationship_to_subagents(self, engine):
        """Soul.subagents relationship loads correctly."""
        from spellbook.db.spellbook_models import Soul, Subagent
        with Session(engine) as session:
            soul = Soul(id="soul-1", project_path="/test")
            sub = Subagent(id="sub-1", soul_id="soul-1", project_path="/test")
            session.add_all([soul, sub])
            session.commit()

            loaded = session.get(Soul, "soul-1")
            assert len(loaded.subagents) == 1
            assert loaded.subagents[0].id == "sub-1"


class TestSubagentModel:
    """Tests for the Subagent ORM model."""

    def test_to_dict_all_fields(self, engine):
        """Subagent.to_dict() returns all columns with correct values."""
        from spellbook.db.spellbook_models import Subagent
        sub = Subagent(
            id="sub-1",
            soul_id="soul-1",
            project_path="/test",
            spawned_at="2026-01-15T10:00:00",
            prompt_summary="Explore codebase",
            persona="Explorer",
            status="completed",
            last_output="Found 3 files",
        )
        d = sub.to_dict()
        assert d == {
            "id": "sub-1",
            "soul_id": "soul-1",
            "project_path": "/test",
            "spawned_at": "2026-01-15T10:00:00",
            "prompt_summary": "Explore codebase",
            "persona": "Explorer",
            "status": "completed",
            "last_output": "Found 3 files",
        }


class TestDecisionModel:
    """Tests for the Decision ORM model."""

    def test_to_dict_all_fields(self, engine):
        """Decision.to_dict() returns correct columns (decision, rationale, decided_at)."""
        from spellbook.db.spellbook_models import Decision
        dec = Decision(
            id=1,
            project_path="/test",
            decision="Use TDD",
            rationale="Ensures quality",
            decided_at="2026-01-15T10:00:00",
        )
        d = dec.to_dict()
        assert d == {
            "id": 1,
            "project_path": "/test",
            "decision": "Use TDD",
            "rationale": "Ensures quality",
            "decided_at": "2026-01-15T10:00:00",
        }


class TestCorrectionModel:
    """Tests for the Correction ORM model."""

    def test_to_dict_all_fields(self, engine):
        """Correction.to_dict() uses constraint_type/constraint_text/recorded_at."""
        from spellbook.db.spellbook_models import Correction
        c = Correction(
            id=1,
            project_path="/test",
            constraint_type="naming",
            constraint_text="Use snake_case for functions",
            recorded_at="2026-01-15T10:00:00",
        )
        d = c.to_dict()
        assert d == {
            "id": 1,
            "project_path": "/test",
            "constraint_type": "naming",
            "constraint_text": "Use snake_case for functions",
            "recorded_at": "2026-01-15T10:00:00",
        }


class TestHeartbeatModel:
    """Tests for the Heartbeat ORM model."""

    def test_to_dict_all_fields(self, engine):
        """Heartbeat.to_dict() has id and timestamp (not last_seen)."""
        from spellbook.db.spellbook_models import Heartbeat
        h = Heartbeat(id=1, timestamp="2026-01-15T10:00:00")
        d = h.to_dict()
        assert d == {"id": 1, "timestamp": "2026-01-15T10:00:00"}
        assert "last_seen" not in d


class TestSkillOutcomeModel:
    """Tests for the SkillOutcome ORM model."""

    def test_to_dict_all_fields(self, engine):
        """SkillOutcome.to_dict() returns all 14 columns."""
        from spellbook.db.spellbook_models import SkillOutcome
        so = SkillOutcome(
            id=1,
            skill_name="develop",
            skill_version="2.0",
            session_id="sess-1",
            project_encoded="Users-alice-proj",
            start_time="2026-01-15T10:00:00",
            end_time="2026-01-15T11:00:00",
            duration_seconds=3600.0,
            outcome="success",
            tokens_used=5000,
            corrections=2,
            retries=1,
            experiment_variant_id="var-1",
            created_at="2026-01-15T10:00:00",
        )
        d = so.to_dict()
        assert d == {
            "id": 1,
            "skill_name": "develop",
            "skill_version": "2.0",
            "session_id": "sess-1",
            "project_encoded": "Users-alice-proj",
            "start_time": "2026-01-15T10:00:00",
            "end_time": "2026-01-15T11:00:00",
            "duration_seconds": 3600.0,
            "outcome": "success",
            "tokens_used": 5000,
            "corrections": 2,
            "retries": 1,
            "experiment_variant_id": "var-1",
            "created_at": "2026-01-15T10:00:00",
        }


class TestTelemetryConfigModel:
    """Tests for the TelemetryConfig ORM model."""

    def test_to_dict_all_fields(self, engine):
        """TelemetryConfig.to_dict() has endpoint_url and last_sync."""
        from spellbook.db.spellbook_models import TelemetryConfig
        tc = TelemetryConfig(
            id=1,
            enabled=1,
            endpoint_url="https://example.com/telemetry",
            last_sync="2026-01-15T10:00:00",
            updated_at="2026-01-15T10:00:00",
        )
        d = tc.to_dict()
        assert d == {
            "id": 1,
            "enabled": 1,
            "endpoint_url": "https://example.com/telemetry",
            "last_sync": "2026-01-15T10:00:00",
            "updated_at": "2026-01-15T10:00:00",
        }


class TestWorkflowStateModel:
    """Tests for the WorkflowState ORM model."""

    def test_to_dict_parses_state_json(self, engine):
        """WorkflowState.to_dict() parses state_json to state dict."""
        from spellbook.db.spellbook_models import WorkflowState
        ws = WorkflowState(
            id=1,
            project_path="/test",
            state_json='{"phase": "DESIGN", "step": 3}',
            trigger="skill_invoke",
            created_at="2026-01-15T10:00:00",
            updated_at="2026-01-15T10:00:00",
        )
        d = ws.to_dict()
        assert d == {
            "id": 1,
            "project_path": "/test",
            "state": {"phase": "DESIGN", "step": 3},
            "trigger": "skill_invoke",
            "created_at": "2026-01-15T10:00:00",
            "updated_at": "2026-01-15T10:00:00",
        }
        assert "state_json" not in d


class TestExperimentModel:
    """Tests for the Experiment ORM model."""

    def test_to_dict_all_fields(self, engine):
        """Experiment.to_dict() returns all columns."""
        from spellbook.db.spellbook_models import Experiment
        e = Experiment(
            id="exp-1",
            name="test-experiment",
            skill_name="develop",
            status="running",
            description="Testing TDD",
            created_at="2026-01-15T10:00:00",
            started_at="2026-01-15T10:30:00",
            completed_at=None,
        )
        d = e.to_dict()
        assert d == {
            "id": "exp-1",
            "name": "test-experiment",
            "skill_name": "develop",
            "status": "running",
            "description": "Testing TDD",
            "created_at": "2026-01-15T10:00:00",
            "started_at": "2026-01-15T10:30:00",
            "completed_at": None,
        }

    def test_relationship_to_variants(self, engine):
        """Experiment.variants relationship loads correctly."""
        from spellbook.db.spellbook_models import Experiment, ExperimentVariant
        with Session(engine) as session:
            exp = Experiment(
                id="exp-1", name="test", skill_name="develop",
                status="created", created_at="2026-01-15T10:00:00",
            )
            var = ExperimentVariant(
                id="var-1", experiment_id="exp-1",
                variant_name="control", weight=50,
                created_at="2026-01-15T10:00:00",
            )
            session.add_all([exp, var])
            session.commit()
            loaded = session.get(Experiment, "exp-1")
            assert len(loaded.variants) == 1
            assert loaded.variants[0].id == "var-1"


class TestExperimentVariantModel:
    """Tests for the ExperimentVariant ORM model."""

    def test_to_dict_all_fields(self, engine):
        """ExperimentVariant uses variant_name, skill_version, weight INTEGER."""
        from spellbook.db.spellbook_models import ExperimentVariant
        v = ExperimentVariant(
            id="var-1",
            experiment_id="exp-1",
            variant_name="control",
            skill_version="1.0",
            weight=75,
            created_at="2026-01-15T10:00:00",
        )
        d = v.to_dict()
        assert d == {
            "id": "var-1",
            "experiment_id": "exp-1",
            "variant_name": "control",
            "skill_version": "1.0",
            "weight": 75,
            "created_at": "2026-01-15T10:00:00",
        }


class TestVariantAssignmentModel:
    """Tests for the VariantAssignment ORM model."""

    def test_to_dict_all_fields(self, engine):
        """VariantAssignment.to_dict() returns all columns."""
        from spellbook.db.spellbook_models import VariantAssignment
        va = VariantAssignment(
            id=1,
            experiment_id="exp-1",
            session_id="sess-1",
            variant_id="var-1",
            assigned_at="2026-01-15T10:00:00",
        )
        d = va.to_dict()
        assert d == {
            "id": 1,
            "experiment_id": "exp-1",
            "session_id": "sess-1",
            "variant_id": "var-1",
            "assigned_at": "2026-01-15T10:00:00",
        }


class TestTrustRegistryModel:
    """Tests for the TrustRegistry ORM model."""

    def test_to_dict_uses_content_hash(self, engine):
        """TrustRegistry uses content_hash, source, trust_level (NOT entity, reason)."""
        from spellbook.db.spellbook_models import TrustRegistry
        t = TrustRegistry(
            id=1,
            content_hash="abc123def456",
            source="manual",
            trust_level="high",
            registered_at="2026-01-15T10:00:00",
            expires_at="2026-06-15T10:00:00",
            registered_by="user-1",
        )
        d = t.to_dict()
        assert d == {
            "id": 1,
            "content_hash": "abc123def456",
            "source": "manual",
            "trust_level": "high",
            "registered_at": "2026-01-15T10:00:00",
            "expires_at": "2026-06-15T10:00:00",
            "registered_by": "user-1",
            "signature": None,
            "signing_key_id": None,
            "analysis_status": None,
            "analysis_at": None,
        }
        assert "entity" not in d
        assert "reason" not in d


class TestSecurityEventModel:
    """Tests for the SecurityEvent ORM model."""

    def test_to_dict_all_fields(self, engine):
        """SecurityEvent.to_dict() returns all columns."""
        from spellbook.db.spellbook_models import SecurityEvent
        se = SecurityEvent(
            id=1,
            event_type="injection_attempt",
            severity="high",
            source="file_content",
            detail="Suspicious directive found",
            session_id="sess-1",
            tool_name="Read",
            action_taken="blocked",
            created_at="2026-01-15T10:00:00",
        )
        d = se.to_dict()
        assert d == {
            "id": 1,
            "event_type": "injection_attempt",
            "severity": "high",
            "source": "file_content",
            "detail": "Suspicious directive found",
            "session_id": "sess-1",
            "tool_name": "Read",
            "action_taken": "blocked",
            "created_at": "2026-01-15T10:00:00",
        }


class TestCanaryTokenModel:
    """Tests for the CanaryToken ORM model."""

    def test_to_dict_all_fields(self, engine):
        """CanaryToken has token_type, context, triggered_at, triggered_by."""
        from spellbook.db.spellbook_models import CanaryToken
        ct = CanaryToken(
            id=1,
            token="CANARY-abc123",
            token_type="system_prompt",
            context="Embedded in instructions",
            created_at="2026-01-15T10:00:00",
            triggered_at="2026-01-15T11:00:00",
            triggered_by="external_agent",
        )
        d = ct.to_dict()
        assert d == {
            "id": 1,
            "token": "CANARY-abc123",
            "token_type": "system_prompt",
            "context": "Embedded in instructions",
            "created_at": "2026-01-15T10:00:00",
            "triggered_at": "2026-01-15T11:00:00",
            "triggered_by": "external_agent",
        }
        assert "label" not in d


class TestSecurityModeModel:
    """Tests for the SecurityMode ORM model."""

    def test_to_dict_all_fields(self, engine):
        """SecurityMode has updated_by and auto_restore_at columns."""
        from spellbook.db.spellbook_models import SecurityMode
        sm = SecurityMode(
            id=1,
            mode="lockdown",
            updated_at="2026-01-15T10:00:00",
            updated_by="admin",
            auto_restore_at="2026-01-15T12:00:00",
        )
        d = sm.to_dict()
        assert d == {
            "id": 1,
            "mode": "lockdown",
            "updated_at": "2026-01-15T10:00:00",
            "updated_by": "admin",
            "auto_restore_at": "2026-01-15T12:00:00",
        }


class TestSpawnRateLimitModel:
    """Tests for the SpawnRateLimit ORM model."""

    def test_to_dict_timestamp_is_real(self, engine):
        """SpawnRateLimit.timestamp is REAL type, not TEXT."""
        from spellbook.db.spellbook_models import SpawnRateLimit
        srl = SpawnRateLimit(
            id=1,
            timestamp=1705312800.5,
            session_id="sess-1",
        )
        d = srl.to_dict()
        assert d == {
            "id": 1,
            "timestamp": 1705312800.5,
            "session_id": "sess-1",
        }
        # Verify the column type is REAL via introspection
        inspector = inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("spawn_rate_limit")}
        ts_type = str(columns["timestamp"]["type"]).upper()
        assert ts_type in ("REAL", "FLOAT"), (
            f"Expected REAL type for timestamp, got {ts_type}"
        )


class TestMemoryModel:
    """Tests for the Memory ORM model."""

    def test_to_dict_parses_meta_json(self, engine):
        """Memory.to_dict() parses meta JSON string to dict."""
        from spellbook.db.spellbook_models import Memory
        m = Memory(
            id="mem-1",
            content="Important discovery",
            memory_type="insight",
            namespace="project-a",
            branch="main",
            importance=0.9,
            created_at="2026-01-15T10:00:00",
            accessed_at="2026-01-15T11:00:00",
            status="active",
            deleted_at=None,
            content_hash="hash123",
            meta='{"source": "session", "tags": ["important"]}',
        )
        d = m.to_dict()
        assert d == {
            "id": "mem-1",
            "content": "Important discovery",
            "memory_type": "insight",
            "namespace": "project-a",
            "branch": "main",
            "scope": None,
            "importance": 0.9,
            "created_at": "2026-01-15T10:00:00",
            "accessed_at": "2026-01-15T11:00:00",
            "status": "active",
            "deleted_at": None,
            "content_hash": "hash123",
            "meta": {"source": "session", "tags": ["important"]},
        }

    def test_to_dict_null_meta(self, engine):
        """Memory.to_dict() handles null meta gracefully."""
        from spellbook.db.spellbook_models import Memory
        m = Memory(
            id="mem-2", content="test", namespace="ns",
            created_at="2026-01-15", content_hash="abc",
            meta=None,
        )
        d = m.to_dict()
        assert d == {
            "id": "mem-2",
            "content": "test",
            "memory_type": None,
            "namespace": "ns",
            "branch": None,
            "scope": None,
            "importance": None,
            "created_at": "2026-01-15",
            "accessed_at": None,
            "status": None,
            "deleted_at": None,
            "content_hash": "abc",
            "meta": None,
        }

    def test_to_dict_empty_meta(self, engine):
        """Memory.to_dict() handles default '{}' meta."""
        from spellbook.db.spellbook_models import Memory
        m = Memory(
            id="mem-3", content="test", namespace="ns",
            created_at="2026-01-15", content_hash="abc",
            meta="{}",
        )
        d = m.to_dict()
        assert d["meta"] == {}

    def test_relationship_to_citations(self, engine):
        """Memory.citations relationship loads correctly."""
        from spellbook.db.spellbook_models import Memory, MemoryCitation
        with Session(engine) as session:
            mem = Memory(
                id="mem-1", content="test", namespace="ns",
                created_at="2026-01-15", content_hash="abc",
            )
            cit = MemoryCitation(
                id=1, memory_id="mem-1",
                file_path="/src/main.py", line_range="10-20",
                content_snippet="def main():",
            )
            session.add_all([mem, cit])
            session.commit()
            loaded = session.get(Memory, "mem-1")
            assert len(loaded.citations) == 1
            assert loaded.citations[0].file_path == "/src/main.py"

    def test_relationship_to_branches(self, engine):
        """Memory.branches relationship loads correctly."""
        from spellbook.db.spellbook_models import Memory, MemoryBranch
        with Session(engine) as session:
            mem = Memory(
                id="mem-1", content="test", namespace="ns",
                created_at="2026-01-15", content_hash="abc",
            )
            branch = MemoryBranch(
                memory_id="mem-1", branch_name="feature-x",
                association_type="origin",
                created_at="2026-01-15T10:00:00",
            )
            session.add_all([mem, branch])
            session.commit()
            loaded = session.get(Memory, "mem-1")
            assert len(loaded.branches) == 1
            assert loaded.branches[0].branch_name == "feature-x"


class TestMemoryCitationModel:
    """Tests for the MemoryCitation ORM model."""

    def test_to_dict_all_fields(self, engine):
        """MemoryCitation.to_dict() returns all columns."""
        from spellbook.db.spellbook_models import MemoryCitation
        mc = MemoryCitation(
            id=1,
            memory_id="mem-1",
            file_path="/src/main.py",
            line_range="10-20",
            content_snippet="def main():",
        )
        d = mc.to_dict()
        assert d == {
            "id": 1,
            "memory_id": "mem-1",
            "file_path": "/src/main.py",
            "line_range": "10-20",
            "content_snippet": "def main():",
        }


class TestMemoryLinkModel:
    """Tests for the MemoryLink ORM model."""

    def test_composite_pk(self, engine):
        """MemoryLink has 3-column composite PK (memory_a, memory_b, link_type)."""
        from spellbook.db.spellbook_models import MemoryLink
        with Session(engine) as session:
            link = MemoryLink(
                memory_a="m1", memory_b="m2",
                link_type="related", weight=0.8,
                last_seen="2026-01-15T10:00:00",
            )
            session.add(link)
            session.commit()
            loaded = session.get(MemoryLink, ("m1", "m2", "related"))
            assert loaded is not None
            assert loaded.weight == 0.8
            assert loaded.last_seen == "2026-01-15T10:00:00"

    def test_to_dict_all_fields(self, engine):
        """MemoryLink.to_dict() returns all columns."""
        from spellbook.db.spellbook_models import MemoryLink
        ml = MemoryLink(
            memory_a="m1", memory_b="m2",
            link_type="related", weight=0.8,
            last_seen="2026-01-15T10:00:00",
        )
        d = ml.to_dict()
        assert d == {
            "memory_a": "m1",
            "memory_b": "m2",
            "link_type": "related",
            "weight": 0.8,
            "last_seen": "2026-01-15T10:00:00",
        }


class TestMemoryBranchModel:
    """Tests for the MemoryBranch ORM model."""

    def test_composite_pk(self, engine):
        """MemoryBranch has 2-column composite PK (memory_id, branch_name)."""
        from spellbook.db.spellbook_models import MemoryBranch
        with Session(engine) as session:
            mb = MemoryBranch(
                memory_id="mem-1", branch_name="main",
                association_type="origin",
                created_at="2026-01-15T10:00:00",
            )
            session.add(mb)
            session.commit()
            loaded = session.get(MemoryBranch, ("mem-1", "main"))
            assert loaded is not None
            assert loaded.association_type == "origin"

    def test_to_dict_all_fields(self, engine):
        """MemoryBranch uses branch_name (not branch) and association_type."""
        from spellbook.db.spellbook_models import MemoryBranch
        mb = MemoryBranch(
            memory_id="mem-1", branch_name="feature-x",
            association_type="ancestor",
            created_at="2026-01-15T10:00:00",
        )
        d = mb.to_dict()
        assert d == {
            "memory_id": "mem-1",
            "branch_name": "feature-x",
            "association_type": "ancestor",
            "created_at": "2026-01-15T10:00:00",
        }


class TestRawEventModel:
    """Tests for the RawEvent ORM model."""

    def test_to_dict_all_fields(self, engine):
        """RawEvent has project, tool_name, subject, etc. (NOT payload_json)."""
        from spellbook.db.spellbook_models import RawEvent
        re = RawEvent(
            id=1,
            session_id="sess-1",
            timestamp="2026-01-15T10:00:00",
            project="/test",
            branch="main",
            event_type="tool_call",
            tool_name="Read",
            subject="test.py",
            summary="Read a test file",
            tags="read,file",
            consolidated=0,
            batch_id="batch-1",
        )
        d = re.to_dict()
        assert d == {
            "id": 1,
            "session_id": "sess-1",
            "timestamp": "2026-01-15T10:00:00",
            "project": "/test",
            "branch": "main",
            "event_type": "tool_call",
            "tool_name": "Read",
            "subject": "test.py",
            "summary": "Read a test file",
            "tags": "read,file",
            "consolidated": 0,
            "batch_id": "batch-1",
        }
        assert "payload_json" not in d


class TestMemoryAuditLogModel:
    """Tests for the MemoryAuditLog ORM model."""

    def test_to_dict_all_fields(self, engine):
        """MemoryAuditLog has timestamp (not created_at) and details (plural)."""
        from spellbook.db.spellbook_models import MemoryAuditLog
        mal = MemoryAuditLog(
            id=1,
            timestamp="2026-01-15T10:00:00",
            action="create",
            memory_id="mem-1",
            details="Created memory from session observation",
        )
        d = mal.to_dict()
        assert d == {
            "id": 1,
            "timestamp": "2026-01-15T10:00:00",
            "action": "create",
            "memory_id": "mem-1",
            "details": "Created memory from session observation",
        }
        assert "created_at" not in d


class TestStintStackModel:
    """Tests for the StintStack ORM model."""

    def test_to_dict_parses_stack_json(self, engine):
        """StintStack.to_dict() parses stack_json to list."""
        from spellbook.db.spellbook_models import StintStack
        ss = StintStack(
            id=1,
            project_path="/test",
            session_id="sess-1",
            stack_json='[{"name": "task-1", "depth": 0}]',
            updated_at="2026-01-15T10:00:00",
        )
        d = ss.to_dict()
        assert d == {
            "id": 1,
            "project_path": "/test",
            "session_id": "sess-1",
            "stack": [{"name": "task-1", "depth": 0}],
            "updated_at": "2026-01-15T10:00:00",
        }
        assert "stack_json" not in d


class TestStintCorrectionEventModel:
    """Tests for the StintCorrectionEvent ORM model."""

    def test_to_dict_renames_json_fields(self, engine):
        """StintCorrectionEvent.to_dict() renames old/new_stack_json."""
        from spellbook.db.spellbook_models import StintCorrectionEvent
        sce = StintCorrectionEvent(
            id=1,
            project_path="/test",
            session_id="sess-1",
            correction_type="llm_wrong",
            old_stack_json='[{"name": "old"}]',
            new_stack_json='[{"name": "new"}]',
            diff_summary="Replaced top item",
            created_at="2026-01-15T10:00:00",
        )
        d = sce.to_dict()
        assert d == {
            "id": 1,
            "project_path": "/test",
            "session_id": "sess-1",
            "correction_type": "llm_wrong",
            "old_stack": [{"name": "old"}],
            "new_stack": [{"name": "new"}],
            "diff_summary": "Replaced top item",
            "created_at": "2026-01-15T10:00:00",
        }
        assert "old_stack_json" not in d
        assert "new_stack_json" not in d


class TestCuratorEventModel:
    """Tests for the CuratorEvent ORM model."""

    def test_to_dict_parses_tool_ids_json(self, engine):
        """CuratorEvent.to_dict() parses tool_ids JSON string to list."""
        from spellbook.db.spellbook_models import CuratorEvent
        ce = CuratorEvent(
            id=1,
            session_id="sess-1",
            tool_ids='["tool-1", "tool-2"]',
            tokens_saved=500,
            strategy="aggressive",
            timestamp="2026-01-15T10:00:00",
        )
        d = ce.to_dict()
        assert d == {
            "id": 1,
            "session_id": "sess-1",
            "tool_ids": ["tool-1", "tool-2"],
            "tokens_saved": 500,
            "strategy": "aggressive",
            "timestamp": "2026-01-15T10:00:00",
        }
