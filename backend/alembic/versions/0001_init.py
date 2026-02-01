"""init

Revision ID: 0001_init
Revises: 
Create Date: 2026-01-13

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ENUMs: create only if not exists (safe for re-run after partial deploy)
    conn = op.get_bind()
    enums_sql = [
        ("userrole", "ADMIN", "USER"),
        ("casetype", "COURT", "DEMAND_LETTER", "SMALL_CLAIMS"),
        ("casestatus", "OPEN", "CLOSED"),
        (
            "expensecategory",
            "ATTORNEY_FEE",
            "EXPERT",
            "MEDICAL_INFO",
            "INVESTIGATOR",
            "FEES",
            "OTHER",
        ),
        ("expensepayer", "CLIENT_DEDUCTIBLE", "INSURER"),
        (
            "feeeventtype",
            "COURT_STAGE_1_DEFENSE",
            "COURT_STAGE_2_DAMAGES",
            "COURT_STAGE_3_EVIDENCE",
            "COURT_STAGE_4_PROOFS",
            "COURT_STAGE_5_SUMMARIES",
            "AMENDED_DEFENSE_PARTIAL",
            "AMENDED_DEFENSE_FULL",
            "THIRD_PARTY_NOTICE",
            "ADDITIONAL_PROOF_HEARING",
            "DEMAND_FIX",
            "DEMAND_HOURLY",
            "SMALL_CLAIMS_MANUAL",
        ),
        (
            "notificationtype",
            "DEDUCTIBLE_NEAR_EXHAUSTION",
            "INSURER_STARTED_PAYING",
            "RETAINER_DUE_SOON",
            "RETAINER_OVERDUE",
        ),
    ]
    for row in enums_sql:
        name, *values = row
        vals = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({vals}); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum(name="userrole"), nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_reference", sa.String(length=120), nullable=False),
        sa.Column("case_type", sa.Enum(name="casetype"), nullable=False),
        sa.Column("status", sa.Enum(name="casestatus"), nullable=False, server_default="OPEN"),
        sa.Column("open_date", sa.Date(), nullable=False),
        sa.Column("deductible_usd", sa.Numeric(14, 2), nullable=True),
        sa.Column("fx_rate_usd_ils", sa.Numeric(14, 6), nullable=True),
        sa.Column("fx_date_used", sa.Date(), nullable=True),
        sa.Column("fx_source", sa.String(length=32), nullable=False, server_default="BOI"),
        sa.Column("deductible_ils_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("insurer_started", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("insurer_start_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cases_case_reference", "cases", ["case_reference"])
    op.create_index("ix_cases_case_type", "cases", ["case_type"])
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_open_date", "cases", ["open_date"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_name", sa.String(length=120), nullable=False),
        sa.Column("amount_ils_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("service_description", sa.Text(), nullable=False),
        sa.Column("demand_received_date", sa.Date(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.Enum(name="expensecategory"), nullable=False),
        sa.Column("payer", sa.Enum(name="expensepayer"), nullable=False),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("split_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_split_part", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_expenses_case_id", "expenses", ["case_id"])
    op.create_index("ix_expenses_expense_date", "expenses", ["expense_date"])
    op.create_index("ix_expenses_category", "expenses", ["category"])
    op.create_index("ix_expenses_payer", "expenses", ["payer"])
    op.create_index("ix_expenses_split_group_id", "expenses", ["split_group_id"])

    op.create_table(
        "retainer_accruals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accrual_month", sa.Date(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount_ils_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_retainer_accruals_case_id", "retainer_accruals", ["case_id"])
    op.create_index("ix_retainer_accruals_accrual_month", "retainer_accruals", ["accrual_month"])
    op.create_index("ix_retainer_accruals_due_date", "retainer_accruals", ["due_date"])

    op.create_table(
        "retainer_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount_ils_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_retainer_payments_case_id", "retainer_payments", ["case_id"])
    op.create_index("ix_retainer_payments_payment_date", "retainer_payments", ["payment_date"])

    op.create_table(
        "fee_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Enum(name="feeeventtype"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount_override_ils_gross", sa.Numeric(14, 2), nullable=True),
        sa.Column("computed_amount_ils_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_covered_by_credit_ils_gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount_due_cash_ils_gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_fee_events_case_id", "fee_events", ["case_id"])
    op.create_index("ix_fee_events_event_type", "fee_events", ["event_type"])
    op.create_index("ix_fee_events_event_date", "fee_events", ["event_date"])

    op.create_table(
        "fx_rate_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate_usd_ils", sa.Numeric(14, 6), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="BOI"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_fx_rate_cache_rate_date", "fx_rate_cache", ["rate_date"], unique=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.Enum(name="notificationtype"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notifications_case_id", "notifications", ["case_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("type", sa.Enum(name="notificationtype"), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_alert_events_case_id", "alert_events", ["case_id"])
    op.create_index("ix_alert_events_type", "alert_events", ["type"])
    op.create_index("ix_alert_events_key", "alert_events", ["key"])


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("notifications")
    op.drop_table("fx_rate_cache")
    op.drop_table("fee_events")
    op.drop_table("retainer_payments")
    op.drop_table("retainer_accruals")
    op.drop_table("expenses")
    op.drop_table("cases")
    op.drop_table("users")

    for enum_name in (
        "notificationtype",
        "feeeventtype",
        "expensepayer",
        "expensecategory",
        "casestatus",
        "casetype",
        "userrole",
    ):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)


