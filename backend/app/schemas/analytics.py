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


# --- Analytics v2 (case-based filters, unified model) ---


class AnalyticsV2Filters(BaseModel):
    start_date: dt.date
    end_date: dt.date
    case_type: str | None = None  # ALL or COURT / DEMAND_LETTER / SMALL_CLAIMS
    status: str | None = None  # ALL or OPEN / CLOSED
    branch_name: str | None = None  # ALL or specific branch
    denominator_cases: int = 0


class AnalyticsV2KPIs(BaseModel):
    avg_stage_fee_ils: Decimal
    avg_retainer_fee_ils: Decimal
    avg_expenses_ils: Decimal


class ClosingStageRow(BaseModel):
    code: str
    label: str
    count: int
    pct: float


class BranchCaseTypeRow(BaseModel):
    branch_name: str | None
    case_type: str
    count: int


class ByBranchRow(BaseModel):
    branch_name: str | None
    count: int


class ByCaseTypeRow(BaseModel):
    case_type: str
    count: int


class AnalyticsV2Distributions(BaseModel):
    closing_stage: list[ClosingStageRow]
    branch_case_type: list[BranchCaseTypeRow]


class AnalyticsV2Totals(BaseModel):
    by_branch: list[ByBranchRow]
    by_case_type: list[ByCaseTypeRow]


# --- v2 extra metrics: average closing stage index (COURT, CLOSED, stages 1-5 only) ---


class ClosingStageIndexRow(BaseModel):
    """Count/pct for one of stages 1-5 (explains avg_closing_stage_index)."""
    stage: int  # 1..5
    count: int
    pct: float


class ExtraMetrics(BaseModel):
    avg_closing_stage_index: float  # 2 decimals; only COURT CLOSED with stage in 1-5
    closing_stage_index_denominator_cases: int
    closing_stage_index_distribution: list[ClosingStageIndexRow]  # stages 1-5 only


# --- v2 branch fee averages (stage-fee vs retainer-fee by branch) ---


class BranchFeeAverageRow(BaseModel):
    branch_name: str  # "ללא סניף" when null
    cases_count: int
    avg_stage_fee_ils: Decimal
    avg_retainer_fee_ils: Decimal
    avg_expenses_ils: Decimal


class BranchCaseTypeFeeAverageRow(BaseModel):
    branch_name: str
    case_type: str
    cases_count: int
    avg_stage_fee_ils: Decimal
    avg_retainer_fee_ils: Decimal
    avg_expenses_ils: Decimal


class AnalyticsV2Response(BaseModel):
    filters: AnalyticsV2Filters
    kpis: AnalyticsV2KPIs
    distributions: AnalyticsV2Distributions
    totals: AnalyticsV2Totals
    extra_metrics: ExtraMetrics | None = None
    branch_fee_averages: list[BranchFeeAverageRow] = []
    branch_case_type_fee_averages: list[BranchCaseTypeFeeAverageRow] = []


