from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import (
    ClaimsCategory,
    ClaimsFinalOutcomeType,
    ClaimsReportCaseStatus,
    ClaimsReportStatus,
    ClaimsRowLinkageType,
)


class ClaimsReportCreate(BaseModel):
    client_name: str = Field(default="טרם", min_length=1, max_length=160)
    institution_name: str | None = Field(default=None, max_length=160)
    title: str = Field(min_length=2, max_length=220)
    report_cutoff_date: dt.date
    updated_to_date: dt.date | None = None
    recommended_reserve_ils: Decimal | None = Field(default=None, ge=0)
    intro_text: str | None = None
    closing_text: str | None = None
    template_key: str | None = Field(default=None, max_length=64)


class ClaimsReportUpdate(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=160)
    institution_name: str | None = Field(default=None, max_length=160)
    title: str | None = Field(default=None, min_length=2, max_length=220)
    report_cutoff_date: dt.date | None = None
    updated_to_date: dt.date | None = None
    recommended_reserve_ils: Decimal | None = Field(default=None, ge=0)
    intro_text: str | None = None
    closing_text: str | None = None
    template_key: str | None = Field(default=None, max_length=64)


class ClaimsReportOut(BaseModel):
    id: int
    client_name: str
    institution_name: str | None
    title: str
    report_cutoff_date: dt.date
    updated_to_date: dt.date | None
    recommended_reserve_ils: Decimal | None
    intro_text: str | None
    closing_text: str | None
    status: ClaimsReportStatus
    template_key: str | None
    created_by_user_id: int | None
    finalized_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    rows_count: int = 0


class ClaimsReportFinalizeOut(BaseModel):
    id: int
    status: ClaimsReportStatus
    finalized_at: dt.datetime | None


class ClaimsReportRowBase(BaseModel):
    linked_case_id: int | None = None
    linkage_type: ClaimsRowLinkageType = ClaimsRowLinkageType.MANUAL
    case_reference_text: str | None = Field(default=None, max_length=120)
    case_title: str | None = Field(default=None, max_length=220)
    court_name: str | None = Field(default=None, max_length=220)
    proceeding_number: str | None = Field(default=None, max_length=120)
    branch_name: str | None = Field(default=None, max_length=120)
    institution_name: str | None = Field(default=None, max_length=160)
    category_for_report: ClaimsCategory = ClaimsCategory.OTHER
    report_case_status: ClaimsReportCaseStatus = ClaimsReportCaseStatus.OPEN
    status_note: str | None = None
    current_risk_assessment_ils: Decimal | None = Field(default=None, ge=0)
    risk_assessment_text: str | None = None
    final_outcome_type: ClaimsFinalOutcomeType | None = None
    final_outcome_amount_ils: Decimal | None = Field(default=None, ge=0)
    awarded_costs_to_terem_ils: Decimal | None = Field(default=None, ge=0)
    final_outcome_date: dt.date | None = None
    final_outcome_text: str | None = None
    deductible_usd: Decimal | None = Field(default=None, ge=0)
    deductible_ils_gross: Decimal | None = Field(default=None, ge=0)
    amount_already_paid_on_deductible_ils: Decimal | None = Field(default=None, ge=0)
    remaining_deductible_ils: Decimal | None = Field(default=None, ge=0)
    expenses_total_ils: Decimal | None = Field(default=None, ge=0)
    fees_total_ils: Decimal | None = Field(default=None, ge=0)
    retainer_charged_ils: Decimal | None = Field(default=None, ge=0)
    exposure_for_reserve_ils: Decimal | None = Field(default=None, ge=0)
    narrative_text: str | None = None
    legal_summary_text: str | None = None
    internal_notes: str | None = None
    include_in_report: bool = True


class ClaimsReportRowCreate(ClaimsReportRowBase):
    pass


class ClaimsReportRowUpdate(BaseModel):
    linked_case_id: int | None = None
    linkage_type: ClaimsRowLinkageType | None = None
    case_reference_text: str | None = Field(default=None, max_length=120)
    case_title: str | None = Field(default=None, max_length=220)
    court_name: str | None = Field(default=None, max_length=220)
    proceeding_number: str | None = Field(default=None, max_length=120)
    branch_name: str | None = Field(default=None, max_length=120)
    institution_name: str | None = Field(default=None, max_length=160)
    category_for_report: ClaimsCategory | None = None
    report_case_status: ClaimsReportCaseStatus | None = None
    status_note: str | None = None
    current_risk_assessment_ils: Decimal | None = Field(default=None, ge=0)
    risk_assessment_text: str | None = None
    final_outcome_type: ClaimsFinalOutcomeType | None = None
    final_outcome_amount_ils: Decimal | None = Field(default=None, ge=0)
    awarded_costs_to_terem_ils: Decimal | None = Field(default=None, ge=0)
    final_outcome_date: dt.date | None = None
    final_outcome_text: str | None = None
    deductible_usd: Decimal | None = Field(default=None, ge=0)
    deductible_ils_gross: Decimal | None = Field(default=None, ge=0)
    amount_already_paid_on_deductible_ils: Decimal | None = Field(default=None, ge=0)
    remaining_deductible_ils: Decimal | None = Field(default=None, ge=0)
    expenses_total_ils: Decimal | None = Field(default=None, ge=0)
    fees_total_ils: Decimal | None = Field(default=None, ge=0)
    retainer_charged_ils: Decimal | None = Field(default=None, ge=0)
    exposure_for_reserve_ils: Decimal | None = Field(default=None, ge=0)
    narrative_text: str | None = None
    legal_summary_text: str | None = None
    internal_notes: str | None = None
    include_in_report: bool | None = None


class ClaimsReportRowOut(BaseModel):
    id: int
    report_id: int
    linked_case_id: int | None
    linkage_type: ClaimsRowLinkageType
    case_reference_text: str | None
    case_title: str | None
    court_name: str | None
    proceeding_number: str | None
    branch_name: str | None
    institution_name: str | None
    category_for_report: ClaimsCategory
    report_case_status: ClaimsReportCaseStatus
    status_note: str | None
    current_risk_assessment_ils: Decimal | None
    risk_assessment_text: str | None
    risk_assessment_updated_at: dt.datetime | None
    risk_assessment_updated_by_user_id: int | None
    final_outcome_type: ClaimsFinalOutcomeType | None
    final_outcome_amount_ils: Decimal | None
    awarded_costs_to_terem_ils: Decimal | None
    final_outcome_date: dt.date | None
    final_outcome_text: str | None
    deductible_usd: Decimal | None
    deductible_ils_gross: Decimal | None
    amount_already_paid_on_deductible_ils: Decimal | None
    remaining_deductible_ils: Decimal | None
    expenses_total_ils: Decimal | None
    fees_total_ils: Decimal | None
    retainer_charged_ils: Decimal | None
    exposure_for_reserve_ils: Decimal | None
    narrative_text: str | None
    legal_summary_text: str | None
    internal_notes: str | None
    include_in_report: bool
    last_synced_at: dt.datetime | None
    last_manual_update_at: dt.datetime | None
    source_snapshot_json: dict | None
    created_at: dt.datetime
    updated_at: dt.datetime
    narrative_preview: str


class ClaimsImportFromCasesRequest(BaseModel):
    case_ids: list[int] = Field(default_factory=list)
    category_for_report: ClaimsCategory = ClaimsCategory.OTHER
    include_in_report: bool = True


class ClaimsImportFromCasesOut(BaseModel):
    created_rows: int
    skipped_rows: int


class ClaimsRefreshLinkedRowsOut(BaseModel):
    refreshed_rows: int
    skipped_rows: int


class ClaimsReportDetailsOut(BaseModel):
    report: ClaimsReportOut
    rows: list[ClaimsReportRowOut]
