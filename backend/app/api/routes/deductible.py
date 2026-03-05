"""Deductible / excess summary per case."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.case import Case
from app.schemas.deductible import DeductibleSummaryOut
from app.services import expenses as expense_service

router = APIRouter()


@router.get("/summary", response_model=DeductibleSummaryOut)
def deductible_summary(
    case_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Case not found")
    data = expense_service.get_deductible_summary(db, case)
    return DeductibleSummaryOut(**data)
