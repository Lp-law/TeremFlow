"""claims seed import metadata

Revision ID: 0024_claims_seed_import_metadata
Revises: 0023_claims_rows_linked_unique
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_claims_seed_import_metadata"
down_revision = "0023_claims_rows_linked_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims_reports", sa.Column("seed_import_metadata_json", sa.JSON(), nullable=True))
    op.add_column("claims_report_rows", sa.Column("needs_manual_review", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("claims_report_rows", sa.Column("import_metadata_json", sa.JSON(), nullable=True))
    op.create_index("ix_claims_report_rows_needs_manual_review", "claims_report_rows", ["needs_manual_review"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_claims_report_rows_needs_manual_review", table_name="claims_report_rows")
    op.drop_column("claims_report_rows", "import_metadata_json")
    op.drop_column("claims_report_rows", "needs_manual_review")
    op.drop_column("claims_reports", "seed_import_metadata_json")
