from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

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
    breakdown_json: dict | None = None


# --- Stage billing (create fee event from performed stages) ---


class StageBillingAdjustment(BaseModel):
    kind: Literal["DISCOUNT", "SURCHARGE"]
    amount_ils: Decimal = Field(..., ge=0)  # amount in ILS only
    reason: str = ""


class StageBillingCreate(BaseModel):
    event_date: dt.date
    codes: list[str] = Field(..., min_length=1)  # Performed-to-date (full set); only new codes are charged
    adjustment: StageBillingAdjustment | None = None
    confirm_zero_new_codes: bool = False  # If true, allow creating event when new_codes is empty (0 amount)


