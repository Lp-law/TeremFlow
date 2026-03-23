"""claims rows sync metadata

Revision ID: 0021_claims_rows_sync_metadata
Revises: 0020_claims_reports_module
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_claims_rows_sync_metadata"
down_revision = "0020_claims_reports_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims_report_rows", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("claims_report_rows", sa.Column("last_manual_update_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_claims_report_rows_last_synced_at", "claims_report_rows", ["last_synced_at"], unique=False)
    op.create_index(
        "ix_claims_report_rows_last_manual_update_at",
        "claims_report_rows",
        ["last_manual_update_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_claims_report_rows_last_manual_update_at", table_name="claims_report_rows")
    op.drop_index("ix_claims_report_rows_last_synced_at", table_name="claims_report_rows")
    op.drop_column("claims_report_rows", "last_manual_update_at")
    op.drop_column("claims_report_rows", "last_synced_at")
