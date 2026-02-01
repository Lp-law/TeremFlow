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


class RetainerPaymentCreate(BaseModel):
    payment_date: dt.date
    amount_ils_gross: Decimal = Field(gt=0)


class RetainerPaymentOut(BaseModel):
    id: int
    payment_date: dt.date
    amount_ils_gross: Decimal


class RetainerSummary(BaseModel):
    retainer_accrued_total_ils_gross: Decimal
    retainer_paid_total_ils_gross: Decimal
    retainer_applied_to_fees_total_ils_gross: Decimal
    retainer_credit_balance_ils_gross: Decimal
    fees_due_total_ils_gross: Decimal


