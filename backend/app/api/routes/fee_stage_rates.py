"""Fee stage rates (configurable ILS per code) for stage-billing modal. amount_ils is always gross (כולל מע\"מ)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.services import fees as fee_service

router = APIRouter()


@router.get("", response_model=list[dict])
def list_fee_stage_rates(db: Session = Depends(get_db), _=Depends(require_auth)):
    """Return active rates: [{ code, amount_ils }, ...]. amount_ils is gross (including VAT)."""
    rows = fee_service.get_fee_stage_rates(db)
    return [{"code": r.code, "amount_ils": float(r.amount_ils)} for r in rows]
