from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import FeeEventType


class FeeEventCreate(BaseModel):
    event_type: FeeEventType
    event_date: dt.date
    quantity: int = Field(default=1, ge=1)
    amount_override_ils_gross: Decimal | None = Field(default=None, gt=0)


class FeeEventOut(BaseModel):
    id: int
    event_type: FeeEventType
    event_date: dt.date
    quantity: int
    amount_override_ils_gross: Decimal | None
    computed_amount_ils_gross: Decimal
    amount_covered_by_credit_ils_gross: Decimal
    amount_due_cash_ils_gross: Decimal


