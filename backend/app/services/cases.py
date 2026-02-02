from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import CaseStatus
from app.services.boi_fx import FxLookupError, get_usd_ils_rate
from app.services.expenses import get_case_excess_remaining
from app.services.retainer import ensure_accruals_up_to, get_retainer_anchor_date


def q_ils(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def list_cases(db: Session) -> list[Case]:
    return db.query(Case).order_by(Case.open_date.desc(), Case.id.desc()).all()


def create_case(db: Session, payload) -> Case:
    if payload.deductible_usd is None and payload.deductible_ils_gross is None:
        raise HTTPException(status_code=400, detail="Must provide deductible_usd or deductible_ils_gross")

    # Prevent accidental duplicates (common in imports / repeated clicks).
    existing = db.query(Case).filter(Case.case_reference == payload.case_reference).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Case with this case_reference already exists")

    fx_rate = None
    fx_date_used = None
    fx_source = "BOI"

    if payload.deductible_usd is not None:
        try:
            fx_rate, fx_date_used = get_usd_ils_rate(payload.open_date, db=db)
        except FxLookupError as e:
            raise HTTPException(status_code=400, detail=str(e))
        deductible_ils = q_ils(Decimal(str(payload.deductible_usd)) * fx_rate)
    else:
        fx_source = "IMPORTED"
        deductible_ils = q_ils(Decimal(str(payload.deductible_ils_gross)))

    anchor = getattr(payload, "retainer_anchor_date", None) or get_retainer_anchor_date(payload.open_date)
    branch = getattr(payload, "branch_name", None)

    c = Case(
        case_reference=payload.case_reference,
        case_type=payload.case_type,
        status=CaseStatus.OPEN,
        open_date=payload.open_date,
        retainer_anchor_date=anchor,
        branch_name=branch,
        deductible_usd=payload.deductible_usd,
        fx_rate_usd_ils=fx_rate,
        fx_date_used=fx_date_used,
        fx_source=fx_source,
        deductible_ils_gross=deductible_ils,
        insurer_started=False,
        insurer_start_date=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    # Retainer accruals: generate up to current month using anchor.
    ensure_accruals_up_to(db, case_id=c.id, retainer_anchor_date=c.retainer_anchor_date)
    return c


def update_case_status(db: Session, *, case_id: int, status_value) -> Case:
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    c.status = status_value
    db.commit()
    db.refresh(c)
    return c


def to_case_out(db: Session, case: Case) -> dict:
    excess = get_case_excess_remaining(db, case)
    return {
        "id": case.id,
        "case_reference": case.case_reference,
        "case_type": case.case_type,
        "status": case.status,
        "open_date": case.open_date,
        "retainer_anchor_date": case.retainer_anchor_date,
        "branch_name": case.branch_name,
        "deductible_usd": case.deductible_usd,
        "fx_rate_usd_ils": case.fx_rate_usd_ils,
        "fx_date_used": case.fx_date_used,
        "fx_source": case.fx_source,
        "deductible_ils_gross": case.deductible_ils_gross,
        "insurer_started": case.insurer_started,
        "insurer_start_date": case.insurer_start_date,
        "excess_remaining_ils_gross": excess,
    }


