from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MoneyILS(ApiModel):
    amount_ils_gross: Decimal = Field(gt=0)


class DateRange(ApiModel):
    start_date: date
    end_date: date


class Timestamped(ApiModel):
    created_at: datetime


