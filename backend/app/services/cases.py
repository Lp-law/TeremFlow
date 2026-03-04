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
    snapshot = getattr(payload, "retainer_snapshot_ils_gross", None)
    snapshot_through = getattr(payload, "retainer_snapshot_through_month", None)
    expenses_snapshot = getattr(payload, "expenses_snapshot_ils_gross", None)
    historical_fee_stages = getattr(payload, "historical_fee_stages", None)
    legacy_fee_text = getattr(payload, "legacy_fee_text", None)

    case_name_val = getattr(payload, "case_name", None)
    c = Case(
        case_reference=payload.case_reference,
        case_name=(str(case_name_val).strip() or None) if case_name_val else None,
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
        retainer_snapshot_ils_gross=q_ils(Decimal(str(snapshot))) if snapshot is not None else None,
        retainer_snapshot_through_month=snapshot_through,
        expenses_snapshot_ils_gross=q_ils(Decimal(str(expenses_snapshot))) if expenses_snapshot is not None else None,
        historical_fee_stages=historical_fee_stages,
        legacy_fee_text=legacy_fee_text,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    # Retainer accruals: no snapshot → from anchor; snapshot + through_month → from month after through.
    if c.retainer_snapshot_ils_gross is None:
        ensure_accruals_up_to(db, case_id=c.id, retainer_anchor_date=c.retainer_anchor_date)
    elif c.retainer_snapshot_through_month is not None:
        ensure_accruals_up_to(
            db,
            case_id=c.id,
            retainer_anchor_date=c.retainer_anchor_date,
            snapshot_through_month=c.retainer_snapshot_through_month,
        )
    return c


# Fields that can be updated from Excel update-import (same semantics as create-import).
EXCEL_UPDATE_FIELDS = frozenset({
    "case_name", "case_type", "open_date", "branch_name",
    "deductible_usd", "deductible_ils_gross", "retainer_anchor_date",
    "retainer_snapshot_ils_gross", "retainer_snapshot_through_month",
    "expenses_snapshot_ils_gross", "historical_fee_stages", "legacy_fee_text",
    "performed_fee_stage_codes",
})
# Order for applying updates: deductible_ils_gross after deductible_usd so explicit ILS can override FX result.
EXCEL_UPDATE_FIELD_ORDER = [
    "case_name", "case_type", "open_date", "branch_name",
    "deductible_usd", "deductible_ils_gross", "retainer_anchor_date",
    "retainer_snapshot_ils_gross", "retainer_snapshot_through_month",
    "expenses_snapshot_ils_gross", "historical_fee_stages", "legacy_fee_text",
    "performed_fee_stage_codes",
]


def update_case_from_excel(db: Session, case: Case, updates: dict, *, overwrite_blanks: bool = False) -> Case:
    """
    Apply Excel-import updates to an existing case. updates: logical field name -> value (None = clear if overwrite_blanks).
    Only keys in updates are applied; blank/None does not overwrite unless overwrite_blanks.
    """
    from app.services.retainer import ensure_accruals_up_to

    retainer_changed = False
    for key in EXCEL_UPDATE_FIELD_ORDER:
        if key not in updates:
            continue
        value = updates[key]
        if key not in EXCEL_UPDATE_FIELDS:
            continue
        if value is None and not overwrite_blanks:
            continue
        if key == "case_name":
            case.case_name = (str(value).strip() or None) if value is not None else None
        elif key == "case_type":
            case.case_type = value
        elif key == "open_date":
            case.open_date = value
        elif key == "branch_name":
            case.branch_name = (str(value).strip() or None) if value is not None else None
        elif key == "deductible_usd":
            if value is not None:
                try:
                    fx_rate, fx_date_used = get_usd_ils_rate(case.open_date, db=db)
                    case.deductible_usd = value
                    case.fx_rate_usd_ils = fx_rate
                    case.fx_date_used = fx_date_used
                    case.fx_source = "BOI"
                    case.deductible_ils_gross = q_ils(Decimal(str(value)) * fx_rate)
                except FxLookupError:
                    raise HTTPException(status_code=400, detail="FX rate not available for deductible_usd")
            else:
                case.deductible_usd = None
                case.fx_rate_usd_ils = None
                case.fx_date_used = None
                case.fx_source = "IMPORTED"
        elif key == "deductible_ils_gross":
            case.deductible_ils_gross = q_ils(Decimal(str(value))) if value is not None else case.deductible_ils_gross
            if value is not None:
                case.fx_source = "IMPORTED"
        elif key == "retainer_anchor_date":
            if value is not None:
                case.retainer_anchor_date = value
            elif overwrite_blanks:
                case.retainer_anchor_date = get_retainer_anchor_date(case.open_date)
            retainer_changed = True
        elif key == "retainer_snapshot_ils_gross":
            case.retainer_snapshot_ils_gross = q_ils(Decimal(str(value))) if value is not None else None
            retainer_changed = True
        elif key == "retainer_snapshot_through_month":
            case.retainer_snapshot_through_month = value if value is not None else None
            retainer_changed = True
        elif key == "expenses_snapshot_ils_gross":
            case.expenses_snapshot_ils_gross = q_ils(Decimal(str(value))) if value is not None else None
        elif key == "historical_fee_stages":
            case.historical_fee_stages = value if value is not None else None
        elif key == "legacy_fee_text":
            case.legacy_fee_text = (str(value).strip() or None) if value is not None else None
        elif key == "performed_fee_stage_codes":
            case.performed_fee_stage_codes = value if value is not None else None

    if retainer_changed:
        if case.retainer_snapshot_ils_gross is None:
            ensure_accruals_up_to(db, case_id=case.id, retainer_anchor_date=case.retainer_anchor_date)
        elif case.retainer_snapshot_through_month is not None:
            ensure_accruals_up_to(
                db,
                case_id=case.id,
                retainer_anchor_date=case.retainer_anchor_date,
                snapshot_through_month=case.retainer_snapshot_through_month,
            )
    db.commit()
    db.refresh(case)
    return case


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
        "case_name": case.case_name,
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
        "retainer_snapshot_ils_gross": case.retainer_snapshot_ils_gross,
        "retainer_snapshot_through_month": case.retainer_snapshot_through_month,
        "expenses_snapshot_ils_gross": case.expenses_snapshot_ils_gross,
        "historical_fee_stages": case.historical_fee_stages or [],
        "legacy_fee_text": case.legacy_fee_text,
        "performed_fee_stage_codes": case.performed_fee_stage_codes or [],
        "excess_remaining_ils_gross": excess,
    }


