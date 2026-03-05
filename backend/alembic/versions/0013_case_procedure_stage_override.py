"""add cases.procedure_stage_override (manual stage for display; does not affect fees)

Revision ID: 0013_procedure_stage_override (kept <=32 chars for alembic_version.version_num)
Revises: 0012_retainer_payment_note
Create Date: 2026-02-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_procedure_stage_override"
down_revision = "0012_retainer_payment_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent for PostgreSQL (re-run safe if 0013 failed after adding column but before updating version)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS procedure_stage_override VARCHAR(80)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cases_procedure_stage_override ON cases (procedure_stage_override)"))
    else:
        op.add_column(
            "cases",
            sa.Column("procedure_stage_override", sa.String(80), nullable=True),
        )
        op.create_index("ix_cases_procedure_stage_override", "cases", ["procedure_stage_override"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cases_procedure_stage_override", table_name="cases")
    op.drop_column("cases", "procedure_stage_override")
