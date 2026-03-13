from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field


class RetainerAccrualOut(BaseModel):
    id: int
    accrual_month: dt.date
    invoice_date: dt.date
    due_date: dt.date
    amount_ils_gross: Decimal
    is_paid: bool


class RetainerFreezeRequest(BaseModel):
    freeze: bool  # True = freeze, False = unfreeze


class RetainerDatesUpdate(BaseModel):
    """Update retainer dates and/or two periods: current + legacy (start/end). Send null to clear."""
    retainer_anchor_date: dt.date | None = None
    retainer_snapshot_through_month: dt.date | None = None  # YYYY-MM-01
    retainer_end_date: dt.date | None = None  # current period end (alias)
    retainer_current_start_date: dt.date | None = None
    retainer_current_end_date: dt.date | None = None
    retainer_legacy_start_date: dt.date | None = None
    retainer_legacy_end_date: dt.date | None = None


class RetainerPaymentCreate(BaseModel):
    payment_date: dt.date
    amount_ils_gross: Decimal = Field(gt=0)
    note: str | None = None


class RetainerLegacyRangeCreate(BaseModel):
    """Create N retainer_payments (one per month in range). Admin/import use."""
    start_date: dt.date
    end_date: dt.date
    monthly_amount_ils_gross: Decimal = Field(gt=0)
    note: str | None = None


class RetainerPaymentOut(BaseModel):
    id: int
    payment_date: dt.date
    amount_ils_gross: Decimal
    note: str | None = None


class RetainerSummary(BaseModel):
    retainer_accrued_total_ils_gross: Decimal
    retainer_paid_total_ils_gross: Decimal
    retainer_applied_to_fees_total_ils_gross: Decimal
    retainer_credit_balance_ils_gross: Decimal
    fees_due_total_ils_gross: Decimal


class RetainerLedgerRow(BaseModel):
    month: str  # YYYY-MM
    accrued_ils: Decimal
    paid_ils: Decimal
    running_credit_ils: Decimal
    row_type: str  # "snapshot" | "accrual" | "payment"
    notes: str | None = None


class RetainerLedgerConfig(BaseModel):
    monthly_base_net_ils: Decimal
    vat_pct: str  # e.g. "18%"
    monthly_gross_ils: Decimal  # example for current month


class RetainerLedgerOut(BaseModel):
    config: RetainerLedgerConfig
    anchor_date: str  # YYYY-MM-DD
    snapshot_through_month: str | None
    snapshot_paid_ils: Decimal
    current_credit_ils: Decimal
    charged_months_count: int
    retainer_paid_total_ils_gross: Decimal  # total paid (payments)
    total_accrued_ils: Decimal  # sum of accrued in rows
    total_retainer_theoretical_ils_gross: Decimal = Decimal("0")  # source of truth: months × 945+VAT
    total_current_theoretical_ils: Decimal = Decimal("0")
    total_legacy_theoretical_ils: Decimal = Decimal("0")
    rows: list[RetainerLedgerRow]


