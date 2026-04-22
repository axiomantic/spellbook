"""add hook_events

Revision ID: 0002_hook_events
Revises: 0001_worker_llm_calls
Create Date: 2026-04-22

Second migration for the spellbook database's ``hook_events`` table.
Mirrors the ``HookEvent`` model in ``spellbook.db.spellbook_models``:
9 columns, 3 indexes (timestamp, hook+event compound, event_name) matching
the hot admin query shapes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_hook_events"
down_revision: Union[str, None] = "0001_worker_llm_calls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("hook_name", sa.Text(), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exit_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_hook_events_timestamp",
        "hook_events",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_hook_events_event_name",
        "hook_events",
        ["event_name"],
        unique=False,
    )
    op.create_index(
        "ix_hook_events_hook_event",
        "hook_events",
        ["hook_name", "event_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hook_events_hook_event", table_name="hook_events")
    op.drop_index("ix_hook_events_event_name", table_name="hook_events")
    op.drop_index("ix_hook_events_timestamp", table_name="hook_events")
    op.drop_table("hook_events")
