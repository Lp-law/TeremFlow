"""claims reports module

Revision ID: 0020_claims_reports_module
Revises: 0019_retainer_periods
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_claims_reports_module"
down_revision = "0019_retainer_periods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    enums_sql = [
        ("claimsreportstatus", "DRAFT", "FINAL"),
        ("claimsrowlinkagetype", "LINKED", "MANUAL"),
        (
            "claimscategory",
            "COURT_REPORTED_TO_INSURER",
            "REPORTED_WITHOUT_CLAIM",
            "NOT_REPORTED_TO_INSURER",
            "NON_MEDICAL_MALPRACTICE",
            "OTHER",
        ),
        (
            "claimsreportcasestatus",
            "OPEN",
            "CLOSED",
            "CANNOT_ASSESS_YET",
            "NO_EXPOSURE",
            "REJECTED_EXPECTED",
            "SETTLED",
            "JUDGMENT",
            "REJECTED",
            "REJECTED_WITH_COSTS",
        ),
        (
            "claimsfinaloutcometype",
            "SETTLEMENT",
            "JUDGMENT_FOR_PLAINTIFF",
            "CLAIM_REJECTED",
            "CLAIM_REJECTED_WITH_COSTS",
            "CLOSED_WITHOUT_PAYMENT",
            "OTHER",
        ),
    ]
    for row in enums_sql:
        name, *values = row
        vals = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({vals}); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    claims_report_status = postgresql.ENUM("DRAFT", "FINAL", name="claimsreportstatus", create_type=False)
    linkage_type = postgresql.ENUM("LINKED", "MANUAL", name="claimsrowlinkagetype", create_type=False)
    category_enum = postgresql.ENUM(
        "COURT_REPORTED_TO_INSURER",
        "REPORTED_WITHOUT_CLAIM",
        "NOT_REPORTED_TO_INSURER",
        "NON_MEDICAL_MALPRACTICE",
        "OTHER",
        name="claimscategory",
        create_type=False,
    )
    report_case_status = postgresql.ENUM(
        "OPEN",
        "CLOSED",
        "CANNOT_ASSESS_YET",
        "NO_EXPOSURE",
        "REJECTED_EXPECTED",
        "SETTLED",
        "JUDGMENT",
        "REJECTED",
        "REJECTED_WITH_COSTS",
        name="claimsreportcasestatus",
        create_type=False,
    )
    final_outcome_type = postgresql.ENUM(
        "SETTLEMENT",
        "JUDGMENT_FOR_PLAINTIFF",
        "CLAIM_REJECTED",
        "CLAIM_REJECTED_WITH_COSTS",
        "CLOSED_WITHOUT_PAYMENT",
        "OTHER",
        name="claimsfinaloutcometype",
        create_type=False,
    )

    op.create_table(
        "claims_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_name", sa.String(length=160), nullable=False, server_default="טרם"),
        sa.Column("institution_name", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("report_cutoff_date", sa.Date(), nullable=False),
        sa.Column("updated_to_date", sa.Date(), nullable=True),
        sa.Column("recommended_reserve_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("intro_text", sa.Text(), nullable=True),
        sa.Column("closing_text", sa.Text(), nullable=True),
        sa.Column("status", claims_report_status, nullable=False, server_default="DRAFT"),
        sa.Column("template_key", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_claims_reports_created_by_user_id", "claims_reports", ["created_by_user_id"], unique=False)
    op.create_index("ix_claims_reports_created_at", "claims_reports", ["created_at"], unique=False)
    op.create_index("ix_claims_reports_updated_at", "claims_reports", ["updated_at"], unique=False)
    op.create_index("ix_claims_reports_report_cutoff_date", "claims_reports", ["report_cutoff_date"], unique=False)
    op.create_index("ix_claims_reports_updated_to_date", "claims_reports", ["updated_to_date"], unique=False)
    op.create_index("ix_claims_reports_status", "claims_reports", ["status"], unique=False)
    op.create_index("ix_claims_reports_deleted_at", "claims_reports", ["deleted_at"], unique=False)

    op.create_table(
        "claims_report_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("claims_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("linked_case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linkage_type", linkage_type, nullable=False, server_default="MANUAL"),
        sa.Column("case_reference_text", sa.String(length=120), nullable=True),
        sa.Column("case_title", sa.String(length=220), nullable=True),
        sa.Column("court_name", sa.String(length=220), nullable=True),
        sa.Column("proceeding_number", sa.String(length=120), nullable=True),
        sa.Column("branch_name", sa.String(length=120), nullable=True),
        sa.Column("institution_name", sa.String(length=160), nullable=True),
        sa.Column("category_for_report", category_enum, nullable=False, server_default="OTHER"),
        sa.Column("report_case_status", report_case_status, nullable=False, server_default="OPEN"),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("current_risk_assessment_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("risk_assessment_text", sa.Text(), nullable=True),
        sa.Column("risk_assessment_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_assessment_updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("final_outcome_type", final_outcome_type, nullable=True),
        sa.Column("final_outcome_amount_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("awarded_costs_to_terem_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("final_outcome_date", sa.Date(), nullable=True),
        sa.Column("final_outcome_text", sa.Text(), nullable=True),
        sa.Column("deductible_usd", sa.Numeric(14, 2), nullable=True),
        sa.Column("deductible_ils_gross", sa.Numeric(14, 2), nullable=True),
        sa.Column("amount_already_paid_on_deductible_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("remaining_deductible_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("expenses_total_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("fees_total_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("retainer_charged_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("exposure_for_reserve_ils", sa.Numeric(14, 2), nullable=True),
        sa.Column("narrative_text", sa.Text(), nullable=True),
        sa.Column("legal_summary_text", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("include_in_report", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_claims_report_rows_report_id", "claims_report_rows", ["report_id"], unique=False)
    op.create_index("ix_claims_report_rows_linked_case_id", "claims_report_rows", ["linked_case_id"], unique=False)
    op.create_index("ix_claims_report_rows_linkage_type", "claims_report_rows", ["linkage_type"], unique=False)
    op.create_index("ix_claims_report_rows_case_reference_text", "claims_report_rows", ["case_reference_text"], unique=False)
    op.create_index("ix_claims_report_rows_branch_name", "claims_report_rows", ["branch_name"], unique=False)
    op.create_index("ix_claims_report_rows_category_for_report", "claims_report_rows", ["category_for_report"], unique=False)
    op.create_index("ix_claims_report_rows_report_case_status", "claims_report_rows", ["report_case_status"], unique=False)
    op.create_index("ix_claims_report_rows_final_outcome_type", "claims_report_rows", ["final_outcome_type"], unique=False)
    op.create_index("ix_claims_report_rows_include_in_report", "claims_report_rows", ["include_in_report"], unique=False)
    op.create_index("ix_claims_report_rows_risk_assessment_updated_by_user_id", "claims_report_rows", ["risk_assessment_updated_by_user_id"], unique=False)
    op.create_index("ix_claims_report_rows_created_at", "claims_report_rows", ["created_at"], unique=False)
    op.create_index("ix_claims_report_rows_updated_at", "claims_report_rows", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_table("claims_report_rows")
    op.drop_table("claims_reports")
    for enum_name in (
        "claimsfinaloutcometype",
        "claimsreportcasestatus",
        "claimscategory",
        "claimsrowlinkagetype",
        "claimsreportstatus",
    ):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
