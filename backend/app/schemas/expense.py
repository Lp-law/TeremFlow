from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import ExpenseCategory, ExpensePayer


class ExpenseCreate(BaseModel):
    supplier_name: str = Field(min_length=2, max_length=120)
    amount_ils_gross: Decimal = Field(gt=0)
    service_description: str = Field(min_length=1)
    demand_received_date: dt.date
    expense_date: dt.date = Field(default_factory=lambda: dt.date.today())
    category: ExpenseCategory
    payer: ExpensePayer | None = None  # allow override; otherwise auto
    attachment_url: str | None = None


class ExpenseOut(BaseModel):
    id: int
    case_id: int
    supplier_name: str
    amount_ils_gross: Decimal
    service_description: str
    demand_received_date: dt.date
    expense_date: dt.date
    category: ExpenseCategory
    payer: ExpensePayer
    attachment_url: str | None
    split_group_id: str | None
    is_split_part: bool


