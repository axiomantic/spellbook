"""add worker_llm_calls

Revision ID: 0001_worker_llm_calls
Revises:
Create Date: 2026-04-21

Initial migration for the spellbook database's ``worker_llm_calls`` table.
Mirrors the ``WorkerLLMCall`` model in ``spellbook.db.spellbook_models``:
10 columns, 3 single-column indexes (timestamp, task, status), and 2
compound indexes (timestamp+status, timestamp+task) matching the hot
admin query shapes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_worker_llm_calls"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_llm_calls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_len", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_len", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("override_loaded", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_worker_llm_calls_timestamp",
        "worker_llm_calls",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_worker_llm_calls_task",
        "worker_llm_calls",
        ["task"],
        unique=False,
    )
    op.create_index(
        "ix_worker_llm_calls_status",
        "worker_llm_calls",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_worker_llm_calls_ts_status",
        "worker_llm_calls",
        ["timestamp", "status"],
        unique=False,
    )
    op.create_index(
        "ix_worker_llm_calls_ts_task",
        "worker_llm_calls",
        ["timestamp", "task"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_worker_llm_calls_ts_task", table_name="worker_llm_calls")
    op.drop_index("ix_worker_llm_calls_ts_status", table_name="worker_llm_calls")
    op.drop_index("ix_worker_llm_calls_status", table_name="worker_llm_calls")
    op.drop_index("ix_worker_llm_calls_task", table_name="worker_llm_calls")
    op.drop_index("ix_worker_llm_calls_timestamp", table_name="worker_llm_calls")
    op.drop_table("worker_llm_calls")
