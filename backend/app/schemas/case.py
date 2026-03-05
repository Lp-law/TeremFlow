from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CaseStatus, CaseType


class CaseCreate(BaseModel):
    case_reference: str = Field(min_length=2, max_length=120)
    case_name: str | None = Field(default=None, max_length=200)
    case_type: CaseType
    open_date: dt.date

    # For new cases: prefer USD input; system will compute ILS by BOI rate on/prev open_date.
    deductible_usd: Decimal | None = Field(default=None, gt=0)

    # For imports: allow direct ILS deductible (fx marked imported if no usd).
    deductible_ils_gross: Decimal | None = Field(default=None, gt=0)

    # Optional: for imports, Excel column B and C.
    branch_name: str | None = Field(default=None, max_length=120)
    retainer_anchor_date: dt.date | None = None  # If omitted, computed from open_date
    retainer_snapshot_ils_gross: Decimal | None = Field(default=None, ge=0)  # Excel H: historical retainer
    retainer_snapshot_through_month: dt.date | None = None  # Last month included in H. Accruals start next month.
    expenses_snapshot_ils_gross: Decimal | None = Field(default=None, ge=0)  # Excel I: historical non-attorney expenses


class CaseOut(BaseModel):
    id: int
    case_reference: str
    case_name: str | None
    case_type: CaseType
    status: CaseStatus
    open_date: dt.date
    retainer_anchor_date: dt.date
    branch_name: str | None
    # Latest fee event type (procedure stage) for list UX; override takes precedence over computed.
    current_procedure_stage: str | None = None
    procedure_stage_override: str | None = None  # manual override; null = use computed from fee events

    deductible_usd: Decimal | None
    fx_rate_usd_ils: Decimal | None
    fx_date_used: dt.date | None
    fx_source: str
    deductible_ils_gross: Decimal

    insurer_started: bool
    insurer_start_date: dt.date | None

    retainer_snapshot_ils_gross: Decimal | None
    retainer_snapshot_through_month: dt.date | None
    expenses_snapshot_ils_gross: Decimal | None
    historical_fee_stages: list[str]  # FeeEventType codes, read-only
    legacy_fee_text: str | None = None  # from Excel "פירוט חיוב שכ״ט עו״ד"
    performed_fee_stage_codes: list[str] | None = None  # last selection for stage-billing
    raw_import_fields_json: dict | None = None  # display-only; Excel columns not mapped to operational fields
    excess_remaining_ils_gross: Decimal  # unified: excess_total - retainer_charged - expenses_total
    retainer_is_frozen: bool = False
    retainer_frozen_at: dt.date | None = None
    expenses_total_ils_gross: Decimal | None = None
    manual_overrides_json: dict | None = None


class CaseUpdateStatus(BaseModel):
    status: CaseStatus


class CaseDeleteRequest(BaseModel):
    delete_reason: str | None = None


class ManualOverridesUpdate(BaseModel):
    """Merge into case.manual_overrides_json. Send null for a key to clear that override."""
    excess_total_ils_override: Decimal | None = None
    retainer_charged_override: Decimal | None = None
    expenses_total_override: Decimal | None = None
    fees_by_stages_override: Decimal | None = None
    excess_remaining_override: Decimal | None = None
    fee_diff_override: Decimal | None = None


# Allowed procedure_stage_override codes (FeeEventType values)
PROCEDURE_STAGE_OVERRIDE_CODES = frozenset({
    "COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES", "COURT_STAGE_3_EVIDENCE",
    "COURT_STAGE_4_PROOFS", "COURT_STAGE_5_SUMMARIES",
    "AMENDED_DEFENSE_PARTIAL", "AMENDED_DEFENSE_FULL", "THIRD_PARTY_NOTICE",
    "ADDITIONAL_PROOF_HEARING", "DEMAND_FIX", "DEMAND_HOURLY", "SMALL_CLAIMS_MANUAL",
    "APPEAL", "STAGE_BILLING",
})


class CaseBulkUpdateUpdates(BaseModel):
    status: CaseStatus | None = None
    case_type: CaseType | None = None
    procedure_stage_override: str | None = None  # one of PROCEDURE_STAGE_OVERRIDE_CODES or null to clear

    def is_empty(self) -> bool:
        return not self.model_dump(exclude_unset=True)


class CaseBulkUpdateRequest(BaseModel):
    case_ids: list[int]
    updates: CaseBulkUpdateUpdates


class CaseBulkUpdateResponse(BaseModel):
    updated_count: int


