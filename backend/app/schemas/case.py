from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CaseStatus, CaseType


class CaseCreate(BaseModel):
    case_reference: str = Field(min_length=2, max_length=120)
    case_type: CaseType
    open_date: dt.date

    # For new cases: prefer USD input; system will compute ILS by BOI rate on/prev open_date.
    deductible_usd: Decimal | None = Field(default=None, gt=0)

    # For imports: allow direct ILS deductible (fx marked imported if no usd).
    deductible_ils_gross: Decimal | None = Field(default=None, gt=0)


class CaseOut(BaseModel):
    id: int
    case_reference: str
    case_type: CaseType
    status: CaseStatus
    open_date: dt.date

    deductible_usd: Decimal | None
    fx_rate_usd_ils: Decimal | None
    fx_date_used: dt.date | None
    fx_source: str
    deductible_ils_gross: Decimal

    insurer_started: bool
    insurer_start_date: dt.date | None

    deductible_remaining_ils_gross: Decimal


class CaseUpdateStatus(BaseModel):
    status: CaseStatus


