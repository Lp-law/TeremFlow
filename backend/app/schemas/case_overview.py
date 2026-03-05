"""Case overview summary for top-of-details snapshot."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class FeesOverview(BaseModel):
    total_fees_ils: Decimal = Decimal("0.00")
    fees_due_ils: Decimal = Decimal("0.00")  # not covered by retainer credit
    last_fee_event_date: str | None = None  # YYYY-MM-DD
    last_fee_event_amount: Decimal | None = None


class RetainerOverview(BaseModel):
    current_credit_ils: Decimal = Decimal("0.00")
    monthly_gross_ils: Decimal = Decimal("0.00")


class ExpensesOverview(BaseModel):
    total_expenses_ils: Decimal = Decimal("0.00")
    deductible_consumed_ils: Decimal = Decimal("0.00")


class DeductibleOverview(BaseModel):
    total_ils: Decimal = Decimal("0.00")
    remaining_ils: Decimal = Decimal("0.00")
    excess_remaining_ils: Decimal | None = None


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
