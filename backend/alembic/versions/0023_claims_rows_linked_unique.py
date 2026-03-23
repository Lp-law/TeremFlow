"""claims rows linked unique

Revision ID: 0023_claims_rows_linked_unique
Revises: 0022_claims_rows_soft_delete
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_claims_rows_linked_unique"
down_revision = "0022_claims_rows_soft_delete"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_claims_report_rows_active_linked_case_per_report"


def upgrade() -> None:
    # Keep latest active row per (report_id, linked_case_id) and soft-delete older duplicates.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY report_id, linked_case_id
                    ORDER BY updated_at DESC, id DESC
                ) AS rn
            FROM claims_report_rows
            WHERE linked_case_id IS NOT NULL
              AND deleted_at IS NULL
        )
        UPDATE claims_report_rows r
        SET deleted_at = now()
        FROM ranked
        WHERE r.id = ranked.id
          AND ranked.rn > 1
          AND r.deleted_at IS NULL
        """
    )

    op.create_index(
        INDEX_NAME,
        "claims_report_rows",
        ["report_id", "linked_case_id"],
        unique=True,
        postgresql_where=sa.text("linked_case_id IS NOT NULL AND deleted_at IS NULL"),
        sqlite_where=sa.text("linked_case_id IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="claims_report_rows")
