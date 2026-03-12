"""Fee stage rates (configurable ILS per code) for stage-billing modal. amount_ils is always gross (כולל מע\"מ)."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_auth
from app.db.session import get_db
from app.services import fees as fee_service

router = APIRouter()


class FeeStageRateVatUpdate(BaseModel):
    vat_pct: float | None = None  # 0.17 or 0.18
    net_ils: float | None = None


@router.get("", response_model=list[dict])
def list_fee_stage_rates(db: Session = Depends(get_db), _=Depends(require_auth)):
    """Return active rates: code, gross_amount_ils (computed), vat_pct, net_ils when applicable."""
    rows = fee_service.get_fee_stage_rates(db)
    out = []
    for r in rows:
        gross = fee_service.fee_stage_gross_ils(r)
        item = {"code": r.code, "gross_amount_ils": float(gross), "amount_ils": float(gross)}
        if getattr(r, "vat_pct", None) is not None:
            item["vat_pct"] = float(r.vat_pct)
        if getattr(r, "net_ils", None) is not None:
            item["net_ils"] = float(r.net_ils)
        out.append(item)
    return out


@router.patch("/{code}", response_model=dict)
def update_fee_stage_rate(
    code: str,
    payload: FeeStageRateVatUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Admin: set vat_pct (0.17 or 0.18) and optionally net_ils for a rate."""
    body = payload.model_dump(exclude_unset=True)
    vat_pct = body.get("vat_pct")
    net_ils = body.get("net_ils")
    rate = fee_service.update_fee_stage_rate_vat(
        db,
        code=code,
        vat_pct=Decimal(str(vat_pct)) if vat_pct is not None else None,
        net_ils=Decimal(str(net_ils)) if net_ils is not None else None,
    )
    gross = fee_service.fee_stage_gross_ils(rate)
    out = {"code": rate.code, "gross_amount_ils": float(gross), "amount_ils": float(gross)}
    if getattr(rate, "vat_pct", None) is not None:
        out["vat_pct"] = float(rate.vat_pct)
    if getattr(rate, "net_ils", None) is not None:
        out["net_ils"] = float(rate.net_ils)
    return out
