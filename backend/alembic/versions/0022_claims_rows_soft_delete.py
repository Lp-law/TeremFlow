"""claims rows soft delete

Revision ID: 0022_claims_rows_soft_delete
Revises: 0021_claims_rows_sync_metadata
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_claims_rows_soft_delete"
down_revision = "0021_claims_rows_sync_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims_report_rows", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_claims_report_rows_deleted_at", "claims_report_rows", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_claims_report_rows_deleted_at", table_name="claims_report_rows")
    op.drop_column("claims_report_rows", "deleted_at")
