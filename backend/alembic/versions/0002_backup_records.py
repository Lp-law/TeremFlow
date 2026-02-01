"""backup records

Revision ID: 0002_backup_records
Revises: 0001_init
Create Date: 2026-01-13

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_backup_records"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("tables_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_backup_records_created_by_user_id", "backup_records", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_backup_records_created_by_user_id", table_name="backup_records")
    op.drop_table("backup_records")


