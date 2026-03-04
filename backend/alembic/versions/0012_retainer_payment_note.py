"""add retainer_payments.note

Revision ID: 0012_retainer_payment_note
Revises: 0011_raw_import_fields
Create Date: 2026-02-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_retainer_payment_note"
down_revision = "0011_raw_import_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retainer_payments",
        sa.Column("note", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("retainer_payments", "note")
