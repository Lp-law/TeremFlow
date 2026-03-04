"""add cases.raw_import_fields_json (display-only raw Excel columns)

Revision ID: 0011_raw_import_fields
Revises: 0010_fee_stage_rates
Create Date: 2026-02-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_raw_import_fields"
down_revision = "0010_fee_stage_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("raw_import_fields_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "raw_import_fields_json")
