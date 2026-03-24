"""SQLAlchemy ORM models for spellbook.db (25 tables).

These models mirror the CREATE TABLE statements in spellbook/core/db.py
(lines 102-640) and spellbook/coordination/curator.py (lines 17-26).
"""

import json
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from spellbook.db.base import SpellbookBase


def _parse_json(value: Optional[str]):
    """Parse a JSON string, returning None if the value is None."""
    if value is None:
        return None
    return json.loads(value)


# ---- 1. souls ----

class Soul(SpellbookBase):
    __tablename__ = "souls"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    bound_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_skill: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skill_phase: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    todos: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recent_files: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exact_position: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_pattern: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summoned_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    subagents = relationship("Subagent", back_populates="soul")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "session_id": self.session_id,
            "bound_at": self.bound_at,
            "persona": self.persona,
            "active_skill": self.active_skill,
            "skill_phase": self.skill_phase,
            "todos": _parse_json(self.todos),
            "recent_files": _parse_json(self.recent_files),
            "exact_position": self.exact_position,
            "workflow_pattern": self.workflow_pattern,
            "summoned_at": self.summoned_at,
        }


# ---- 2. subagents ----

class Subagent(SpellbookBase):
    __tablename__ = "subagents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    soul_id: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("souls.id"), nullable=True,
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    spawned_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    prompt_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    soul = relationship("Soul", back_populates="subagents")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "soul_id": self.soul_id,
            "project_path": self.project_path,
            "spawned_at": self.spawned_at,
            "prompt_summary": self.prompt_summary,
            "persona": self.persona,
            "status": self.status,
            "last_output": self.last_output,
        }


# ---- 3. decisions ----

class Decision(SpellbookBase):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "decision": self.decision,
            "rationale": self.rationale,
            "decided_at": self.decided_at,
        }


# ---- 4. corrections ----

class Correction(SpellbookBase):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    constraint_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    constraint_text: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "constraint_type": self.constraint_type,
            "constraint_text": self.constraint_text,
            "recorded_at": self.recorded_at,
        }


# ---- 5. heartbeat ----

class Heartbeat(SpellbookBase):
    __tablename__ = "heartbeat"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True,
    )
    timestamp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="heartbeat_singleton"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
        }


# ---- 6. skill_outcomes ----

class SkillOutcome(SpellbookBase):
    __tablename__ = "skill_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    skill_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_encoded: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(Text, nullable=False)
    end_time: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    corrections: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    retries: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    experiment_variant_id: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, index=True,
    )
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("session_id", "skill_name", "start_time"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "session_id": self.session_id,
            "project_encoded": self.project_encoded,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "outcome": self.outcome,
            "tokens_used": self.tokens_used,
            "corrections": self.corrections,
            "retries": self.retries,
            "experiment_variant_id": self.experiment_variant_id,
            "created_at": self.created_at,
        }


# ---- 7. telemetry_config ----

class TelemetryConfig(SpellbookBase):
    __tablename__ = "telemetry_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    endpoint_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sync: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="telemetry_config_singleton"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "enabled": self.enabled,
            "endpoint_url": self.endpoint_url,
            "last_sync": self.last_sync,
            "updated_at": self.updated_at,
        }


# ---- 8. workflow_state ----

class WorkflowState(SpellbookBase):
    __tablename__ = "workflow_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "state": _parse_json(self.state_json),
            "trigger": self.trigger,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---- 9. experiments ----

class Experiment(SpellbookBase):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    skill_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="created", index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    variants = relationship("ExperimentVariant", back_populates="experiment")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "skill_name": self.skill_name,
            "status": self.status,
            "description": self.description,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ---- 10. experiment_variants ----

class ExperimentVariant(SpellbookBase):
    __tablename__ = "experiment_variants"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        Text, ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    variant_name: Mapped[str] = mapped_column(Text, nullable=False)
    skill_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("experiment_id", "variant_name"),
    )

    experiment = relationship("Experiment", back_populates="variants")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "variant_name": self.variant_name,
            "skill_version": self.skill_version,
            "weight": self.weight,
            "created_at": self.created_at,
        }


# ---- 11. variant_assignments ----

class VariantAssignment(SpellbookBase):
    __tablename__ = "variant_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(
        Text, ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("experiment_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("experiment_id", "session_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "session_id": self.session_id,
            "variant_id": self.variant_id,
            "assigned_at": self.assigned_at,
        }


# ---- 12. trust_registry ----

class TrustRegistry(SpellbookBase):
    __tablename__ = "trust_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    trust_level: Mapped[str] = mapped_column(Text, nullable=False)
    registered_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registered_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Crypto provenance columns (v2)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signing_key_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content_hash": self.content_hash,
            "source": self.source,
            "trust_level": self.trust_level,
            "registered_at": self.registered_at,
            "expires_at": self.expires_at,
            "registered_by": self.registered_by,
            "signature": self.signature,
            "signing_key_id": self.signing_key_id,
            "analysis_status": self.analysis_status,
            "analysis_at": self.analysis_at,
        }


# ---- 13. security_events ----

class SecurityEvent(SpellbookBase):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "detail": self.detail,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "action_taken": self.action_taken,
            "created_at": self.created_at,
        }


# ---- 14. canary_tokens ----

class CanaryToken(SpellbookBase):
    __tablename__ = "canary_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    token_type: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "token": self.token,
            "token_type": self.token_type,
            "context": self.context,
            "created_at": self.created_at,
            "triggered_at": self.triggered_at,
            "triggered_by": self.triggered_by,
        }


# ---- 15. security_mode ----

class SecurityMode(SpellbookBase):
    __tablename__ = "security_mode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_restore_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="security_mode_singleton"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "auto_restore_at": self.auto_restore_at,
        }


# ---- 16. spawn_rate_limit ----

class SpawnRateLimit(SpellbookBase):
    __tablename__ = "spawn_rate_limit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
        }


# ---- 17. memories ----

class Memory(SpellbookBase):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    namespace: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    branch: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="", index=True)
    importance: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=1.0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    accessed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="active", index=True)
    deleted_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")

    citations = relationship("MemoryCitation", back_populates="memory")
    branches = relationship("MemoryBranch", back_populates="memory")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "namespace": self.namespace,
            "branch": self.branch,
            "importance": self.importance,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "status": self.status,
            "deleted_at": self.deleted_at,
            "content_hash": self.content_hash,
            "meta": _parse_json(self.meta),
        }


# ---- 18. memory_citations ----

class MemoryCitation(SpellbookBase):
    __tablename__ = "memory_citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    memory_id: Mapped[str] = mapped_column(
        Text, ForeignKey("memories.id"), nullable=False,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    line_range: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("memory_id", "file_path", "line_range"),
    )

    memory = relationship("Memory", back_populates="citations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "memory_id": self.memory_id,
            "file_path": self.file_path,
            "line_range": self.line_range,
            "content_snippet": self.content_snippet,
        }


# ---- 19. memory_links ----

class MemoryLink(SpellbookBase):
    __tablename__ = "memory_links"

    memory_a: Mapped[str] = mapped_column(Text, primary_key=True)
    memory_b: Mapped[str] = mapped_column(Text, primary_key=True)
    link_type: Mapped[str] = mapped_column(Text, primary_key=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=1.0)
    last_seen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "memory_a": self.memory_a,
            "memory_b": self.memory_b,
            "link_type": self.link_type,
            "weight": self.weight,
            "last_seen": self.last_seen,
        }


# ---- 20. memory_branches ----

class MemoryBranch(SpellbookBase):
    __tablename__ = "memory_branches"

    memory_id: Mapped[str] = mapped_column(
        Text, ForeignKey("memories.id"), primary_key=True,
    )
    branch_name: Mapped[str] = mapped_column(Text, primary_key=True, index=True)
    association_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="origin", index=True,
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    memory = relationship("Memory", back_populates="branches")

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "branch_name": self.branch_name,
            "association_type": self.association_type,
            "created_at": self.created_at,
        }


# ---- 21. raw_events ----

class RawEvent(SpellbookBase):
    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    project: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    branch: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    event_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consolidated: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "project": self.project,
            "branch": self.branch,
            "event_type": self.event_type,
            "tool_name": self.tool_name,
            "subject": self.subject,
            "summary": self.summary,
            "tags": self.tags,
            "consolidated": self.consolidated,
            "batch_id": self.batch_id,
        }


# ---- 22. memory_audit_log ----

class MemoryAuditLog(SpellbookBase):
    __tablename__ = "memory_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    memory_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action,
            "memory_id": self.memory_id,
            "details": self.details,
        }


# ---- 23. stint_stack ----

class StintStack(SpellbookBase):
    __tablename__ = "stint_stack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "session_id": self.session_id,
            "stack": _parse_json(self.stack_json),
            "updated_at": self.updated_at,
        }


# ---- 24. stint_correction_events ----

class StintCorrectionEvent(SpellbookBase):
    __tablename__ = "stint_correction_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correction_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    old_stack_json: Mapped[str] = mapped_column(Text, nullable=False)
    new_stack_json: Mapped[str] = mapped_column(Text, nullable=False)
    diff_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_path": self.project_path,
            "session_id": self.session_id,
            "correction_type": self.correction_type,
            "old_stack": _parse_json(self.old_stack_json),
            "new_stack": _parse_json(self.new_stack_json),
            "diff_summary": self.diff_summary,
            "created_at": self.created_at,
        }


# ---- 25. curator_events ----

class CuratorEvent(SpellbookBase):
    __tablename__ = "curator_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    tool_ids: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_saved: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tool_ids": _parse_json(self.tool_ids),
            "tokens_saved": self.tokens_saved,
            "strategy": self.strategy,
            "timestamp": self.timestamp,
        }


# ---- 26. intent_checks ----

class IntentCheck(SpellbookBase):
    __tablename__ = "intent_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_tool: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cached: Mapped[int] = mapped_column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content_hash": self.content_hash,
            "source_tool": self.source_tool,
            "classification": self.classification,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "checked_at": self.checked_at,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
        }


# ---- 27. session_content_accumulator ----

class SessionContentAccumulator(SpellbookBase):
    __tablename__ = "session_content_accumulator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_tool: Mapped[str] = mapped_column(Text, nullable=False)
    content_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_size: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content_hash": self.content_hash,
            "source_tool": self.source_tool,
            "content_summary": self.content_summary,
            "content_size": self.content_size,
            "received_at": self.received_at,
            "expires_at": self.expires_at,
        }


# ---- 28. sleuth_budget ----

class SleuthBudget(SpellbookBase):
    __tablename__ = "sleuth_budget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    calls_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    reset_at: Mapped[str] = mapped_column(Text, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "calls_remaining": self.calls_remaining,
            "reset_at": self.reset_at,
        }


# ---- 29. sleuth_cache ----

class SleuthCache(SpellbookBase):
    __tablename__ = "sleuth_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    cached_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content_hash": self.content_hash,
            "classification": self.classification,
            "confidence": self.confidence,
            "cached_at": self.cached_at,
            "expires_at": self.expires_at,
        }
