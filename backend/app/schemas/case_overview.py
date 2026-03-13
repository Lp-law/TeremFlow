"""Case overview summary for top-of-details snapshot. Unified model."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class FeesOverview(BaseModel):
    fees_by_stages_ils: Decimal = Decimal("0.00")  # sum of non-deleted fee events
    retainer_charged_to_date_ils: Decimal = Decimal("0.00")  # theoretical charged (945+VAT)*months
    fee_diff_ils: Decimal = Decimal("0.00")  # fees_by_stages - retainer_charged (may be negative)
    last_fee_event_date: str | None = None  # YYYY-MM-DD
    last_fee_event_amount: Decimal | None = None


class RetainerOverview(BaseModel):
    retainer_charged_to_date_ils: Decimal = Decimal("0.00")  # consumed (override or paid/theoretical)
    retainer_theoretical_ils: Decimal = Decimal("0.00")  # total_theoretical from ledger — single source for "שכ״ט תיאורטי"
    retainer_regular_theoretical_ils: Decimal = Decimal("0.00")
    retainer_legacy_theoretical_ils: Decimal = Decimal("0.00")
    charged_months_count: int = 0
    monthly_gross_ils: Decimal = Decimal("0.00")
    retainer_is_frozen: bool = False
    retainer_frozen_at: str | None = None  # YYYY-MM-DD


class ExpensesOverview(BaseModel):
    total_expenses_ils: Decimal = Decimal("0.00")  # case-level editable total


class DeductibleOverview(BaseModel):
    excess_total_ils: Decimal = Decimal("0.00")
    excess_remaining_ils: Decimal = Decimal("0.00")


class CaseOverviewSummaryOut(BaseModel):
    case_reference: str
    case_name: str | None
    branch_name: str | None
    status: str
    current_procedure_stage: str | None
    fees: FeesOverview
    retainer: RetainerOverview
    expenses: ExpensesOverview
    deductible: DeductibleOverview
