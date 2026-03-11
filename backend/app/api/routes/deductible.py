"""Deductible / excess summary per case (unified model)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.schemas.deductible import DeductibleSummaryOut
from app.services import cases as case_service
from app.services.unified import get_unified_summary

router = APIRouter()


@router.get("/summary", response_model=DeductibleSummaryOut)
def deductible_summary(
    case_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    case = case_service.get_case_if_not_deleted(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    summary = get_unified_summary(db, case)
    raw = getattr(case, "manual_overrides_json", None)
    overrides = raw if isinstance(raw, dict) else {}
    return DeductibleSummaryOut(
        excess_total_ils=summary["excess_total_ils"],
        retainer_charged_to_date_ils=summary["retainer_charged_to_date_ils"],
        expenses_total_ils=summary["expenses_total_ils"],
        fees_by_stages_ils=summary["fees_by_stages_ils"],
        excess_remaining_ils=summary["excess_remaining_ils"],
        fee_diff_ils=summary["fee_diff_ils"],
        manual_overrides=overrides,
    )
