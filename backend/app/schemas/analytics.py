from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import CaseStatus, CaseType


class AnalyticsFilters(BaseModel):
    start_date: dt.date
    end_date: dt.date
    case_type: CaseType | None = None
    payer_status: str | None = None  # client|insurer|closed|all


class ExpensesByCaseRow(BaseModel):
    case_id: int
    case_reference: str
    case_type: CaseType
    status: CaseStatus
    payer_status: str  # client|insurer|closed
    total_expenses_ils_gross: Decimal
    attorney_fees_expenses_ils_gross: Decimal
    other_expenses_ils_gross: Decimal
    deductible_remaining_ils_gross: Decimal


class StageDistributionRow(BaseModel):
    stage: int
    count: int


class TimeSeriesPoint(BaseModel):
    period: str  # e.g. 2026-01 / 2026-Q1 / 2026
    total_expenses_ils_gross: Decimal


class AnalyticsOverviewResponse(BaseModel):
    total_expenses_ils_gross: Decimal
    total_on_deductible_ils_gross: Decimal
    total_on_insurer_ils_gross: Decimal
    average_expenses_per_case_ils_gross: Decimal
    cases_switched_to_insurer_count: int
    aggregate_remaining_deductible_open_cases_ils_gross: Decimal

    expenses_by_case: list[ExpensesByCaseRow]
    expense_split: dict[str, Decimal]  # attorney|other
    court_cases_end_stage_distribution: list[StageDistributionRow]
    monthly: list[TimeSeriesPoint]
    quarterly: list[TimeSeriesPoint]
    yearly: list[TimeSeriesPoint]


