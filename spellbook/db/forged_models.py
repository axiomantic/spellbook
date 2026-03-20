"""SQLAlchemy ORM models for forged.db.

Schema source of truth: spellbook/forged/schema.py:init_forged_schema()

Tables: forge_tokens, iteration_state, reflections, tool_analytics, gate_completions.
"""

from sqlalchemy import Column, Index, Integer, Text, text

from spellbook.db.base import ForgedBase


class ForgeToken(ForgedBase):
    """Workflow tokens for stage transition enforcement."""

    __tablename__ = "forge_tokens"

    id = Column(Text, primary_key=True)
    feature_name = Column(Text, nullable=False, index=True)
    stage = Column(Text, nullable=False, index=True)
    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))
    invalidated_at = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class IterationState(ForgedBase):
    """Core iteration state tracking with composite primary key."""

    __tablename__ = "iteration_state"

    project_path = Column(Text, primary_key=True, nullable=False)
    feature_name = Column(Text, primary_key=True, nullable=False)
    iteration_number = Column(Integer, nullable=False)
    current_stage = Column(Text, nullable=False, index=True)
    accumulated_knowledge = Column(Text, nullable=True)
    feedback_history = Column(Text, nullable=True)
    artifacts_produced = Column(Text, nullable=True)
    preferences = Column(Text, nullable=True)
    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))
    updated_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class ForgeReflection(ForgedBase):
    """Learning from failures - reflection tracking."""

    __tablename__ = "reflections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(Text, nullable=False, index=True)
    validator = Column(Text, nullable=False, index=True)
    iteration = Column(Integer, nullable=False)
    failure_description = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    lesson_learned = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default="PENDING", index=True)
    created_at = Column(Text, nullable=False, server_default=text("datetime('now')"))
    resolved_at = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class ToolAnalytic(ForgedBase):
    """Tool usage analytics tracking."""

    __tablename__ = "tool_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_name = Column(Text, nullable=False, index=True)
    project_path = Column(Text, nullable=False, index=True)
    feature_name = Column(Text, nullable=True)
    stage = Column(Text, nullable=True)
    iteration = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Integer, nullable=False, server_default="1")
    called_at = Column(Text, nullable=False, server_default=text("datetime('now')"), index=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class GateCompletion(ForgedBase):
    """Per-gate roundtable completion tracking."""

    __tablename__ = "gate_completions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_path = Column(Text, nullable=False)
    feature_name = Column(Text, nullable=False)
    gate = Column(Text, nullable=False)
    stage = Column(Text, nullable=False)
    consensus = Column(Integer, nullable=False, server_default="0")
    iteration = Column(Integer, nullable=False, server_default="1")
    verdict_summary = Column(Text, nullable=True)
    completed_at = Column(Text, nullable=False, server_default=text("datetime('now')"))

    __table_args__ = (
        Index("idx_gate_completions_feature", "project_path", "feature_name"),
        Index("idx_gate_completions_gate", "project_path", "feature_name", "gate"),
    )

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
