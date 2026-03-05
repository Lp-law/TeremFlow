"""Case soft delete, retainer freeze, expenses total, overrides; FeeEvent soft delete

Revision ID: 0014_unified_model
Revises: 0013_procedure_stage_override
Create Date: 2026-03-05

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_unified_model"
down_revision = "0013_procedure_stage_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Case: soft delete
    op.add_column("cases", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("delete_reason", sa.String(500), nullable=True))
    op.create_foreign_key("fk_cases_deleted_by_user", "cases", "users", ["deleted_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_cases_deleted_at", "cases", ["deleted_at"], unique=False)

    # Case: retainer freeze
    op.add_column("cases", sa.Column("retainer_is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("cases", sa.Column("retainer_frozen_at", sa.Date(), nullable=True))

    # Case: single editable expenses total
    op.add_column("cases", sa.Column("expenses_total_ils_gross", sa.Numeric(14, 2), nullable=True))

    # Case: manual overrides for deductible/overview
    op.add_column("cases", sa.Column("manual_overrides_json", sa.JSON(), nullable=True))

    # FeeEvent: soft delete
    op.add_column("fee_events", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fee_events", sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))
    op.add_column("fee_events", sa.Column("delete_reason", sa.String(500), nullable=True))
    op.create_foreign_key("fk_fee_events_deleted_by_user", "fee_events", "users", ["deleted_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_fee_events_deleted_at", "fee_events", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fee_events_deleted_at", table_name="fee_events")
    op.drop_constraint("fk_fee_events_deleted_by_user", "fee_events", type_="foreignkey")
    op.drop_column("fee_events", "delete_reason")
    op.drop_column("fee_events", "deleted_by_user_id")
    op.drop_column("fee_events", "deleted_at")

    op.drop_column("cases", "manual_overrides_json")
    op.drop_column("cases", "expenses_total_ils_gross")
    op.drop_column("cases", "retainer_frozen_at")
    op.drop_column("cases", "retainer_is_frozen")

    op.drop_index("ix_cases_deleted_at", table_name="cases")
    op.drop_constraint("fk_cases_deleted_by_user", "cases", type_="foreignkey")
    op.drop_column("cases", "delete_reason")
    op.drop_column("cases", "deleted_by_user_id")
    op.drop_column("cases", "deleted_at")
