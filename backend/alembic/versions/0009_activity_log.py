"""add activity_log table

Revision ID: 0009_activity_log
Revises: 0008_historical_fee_stages
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_activity_log"
down_revision = "0008_historical_fee_stages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
    )
    op.create_index("ix_activity_log_created_at", "activity_log", ["created_at"])
    op.create_index("ix_activity_log_user_id", "activity_log", ["user_id"])
    op.create_index("ix_activity_log_action", "activity_log", ["action"])
    op.create_index("ix_activity_log_entity_type", "activity_log", ["entity_type"])


def downgrade() -> None:
    op.drop_table("activity_log")
