from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_auth
from app.db.session import get_db
from app.models.retainer import RetainerAccrual, RetainerPayment
from app.schemas.retainer import (
    RetainerAccrualOut,
    RetainerDatesUpdate,
    RetainerFreezeRequest,
    RetainerLedgerOut,
    RetainerLegacyRangeCreate,
    RetainerPaymentCreate,
    RetainerPaymentOut,
    RetainerSummary,
)
from app.schemas.case import CaseOut
from app.services import cases as case_service
from app.services import fees as fee_service
from app.services import retainer as retainer_service

router = APIRouter()


def _get_case_or_404(db: Session, case_id: int):
    c = case_service.get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return c


def _accrual_out(a: RetainerAccrual) -> RetainerAccrualOut:
    return RetainerAccrualOut(
        id=a.id,
        accrual_month=a.accrual_month,
        invoice_date=a.invoice_date,
        due_date=a.due_date,
        amount_ils_gross=a.amount_ils_gross,
        is_paid=a.is_paid,
    )


def _payment_out(p: RetainerPayment) -> RetainerPaymentOut:
    return RetainerPaymentOut(
        id=p.id,
        payment_date=p.payment_date,
        amount_ils_gross=p.amount_ils_gross,
        note=p.note,
    )


@router.get("/accruals", response_model=list[RetainerAccrualOut])
def list_accruals(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    _get_case_or_404(db, case_id)
    items = (
        db.query(RetainerAccrual)
        .filter(RetainerAccrual.case_id == case_id)
        .order_by(RetainerAccrual.accrual_month.desc())
        .all()
    )
    return [_accrual_out(a) for a in items]


@router.get("/payments", response_model=list[RetainerPaymentOut])
def list_payments(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    _get_case_or_404(db, case_id)
    items = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.desc(), RetainerPayment.id.desc())
        .all()
    )
    return [_payment_out(p) for p in items]


@router.post("/legacy-range", response_model=list[RetainerPaymentOut])
def create_legacy_range(
    case_id: int,
    payload: RetainerLegacyRangeCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    """Create N retainer_payments (one per month in range). Admin-only."""
    _get_case_or_404(db, case_id)
    created = retainer_service.create_legacy_range_payments(
        db,
        case_id=case_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        monthly_amount_ils_gross=payload.monthly_amount_ils_gross,
        note=payload.note,
    )
    fee_service.apply_retainer_credit(db, case_id=case_id)
    items = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.desc(), RetainerPayment.id.desc())
        .all()
    )
    return [_payment_out(x) for x in items]


@router.post("/payments", response_model=list[RetainerPaymentOut])
def add_payment(
    case_id: int, payload: RetainerPaymentCreate, db: Session = Depends(get_db), user=Depends(require_auth)
):
    _get_case_or_404(db, case_id)
    p = RetainerPayment(
        case_id=case_id,
        payment_date=payload.payment_date,
        amount_ils_gross=payload.amount_ils_gross,
        note=payload.note,
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    retainer_service.allocate_payments_to_accruals(db, case_id=case_id)
    fee_service.apply_retainer_credit(db, case_id=case_id)

    from app.services.activity_log import log_activity
    log_activity(db, action="retainer_payment_add", entity_type="retainer_payment", entity_id=p.id, user_id=user.id, details={"case_id": case_id})

    items = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.desc(), RetainerPayment.id.desc())
        .all()
    )
    return [_payment_out(x) for x in items]


@router.get("/summary", response_model=RetainerSummary)
def summary(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    _get_case_or_404(db, case_id)
    s = retainer_service.retainer_summary(db, case_id=case_id)
    return RetainerSummary(**s)


@router.get("/ledger", response_model=RetainerLedgerOut)
def ledger(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    data = retainer_service.build_retainer_ledger(db, case_id=case_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return RetainerLedgerOut(**data)


@router.get("/debug-theoretical")
def debug_theoretical(
    case_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Admin-only: theoretical from ledger (current + legacy periods)."""
    c = _get_case_or_404(db, case_id)
    total, total_current, total_legacy = retainer_service.get_total_retainer_theoretical_ils(db, c)
    period_months = retainer_service.get_retainer_period_months(c)
    legacy_months = sum(1 for _, k in period_months if k == "legacy")
    current_months = sum(1 for _, k in period_months if k == "current")
    return {
        "case_id": case_id,
        "current_months_count": current_months,
        "legacy_months_count": legacy_months,
        "total_current_theoretical_ils": float(total_current),
        "total_legacy_theoretical_ils": float(total_legacy),
        "retainer_charged_to_date_ils": float(total),
    }


@router.patch("/dates", response_model=CaseOut)
def update_retainer_dates(case_id: int, payload: RetainerDatesUpdate, db: Session = Depends(get_db), _=Depends(require_auth)):
    """Update retainer_anchor_date, retainer_snapshot_through_month, and/or retainer_end_date (send null to clear end date)."""
    updates = payload.model_dump(exclude_unset=True)
    c = case_service.update_case_retainer_dates(
        db,
        case_id=case_id,
        retainer_anchor_date=updates.get("retainer_anchor_date"),
        retainer_snapshot_through_month=updates.get("retainer_snapshot_through_month"),
        retainer_end_date=updates.get("retainer_end_date") if "retainer_end_date" in updates else None,
        retainer_end_date_sent="retainer_end_date" in updates,
        retainer_current_start_date=updates.get("retainer_current_start_date"),
        retainer_current_end_date=updates.get("retainer_current_end_date"),
        retainer_legacy_start_date=updates.get("retainer_legacy_start_date"),
        retainer_legacy_end_date=updates.get("retainer_legacy_end_date"),
        current_start_sent="retainer_current_start_date" in updates,
        current_end_sent="retainer_current_end_date" in updates,
        legacy_start_sent="retainer_legacy_start_date" in updates,
        legacy_end_sent="retainer_legacy_end_date" in updates,
    )
    stages = case_service.get_latest_fee_stage_by_case_ids(db, [c.id])
    return CaseOut(**case_service.to_case_out(db, c, current_procedure_stage=stages.get(c.id)))


@router.post("/freeze", response_model=CaseOut)
def retainer_freeze(case_id: int, payload: RetainerFreezeRequest, db: Session = Depends(get_db), _=Depends(require_auth)):
    """Toggle retainer freeze: when frozen, charged months and accruals stop at retainer_frozen_at."""
    c = case_service.set_retainer_freeze(db, case_id=case_id, freeze=payload.freeze)
    stages = case_service.get_latest_fee_stage_by_case_ids(db, [c.id])
    return CaseOut(**case_service.to_case_out(db, c, current_procedure_stage=stages.get(c.id)))


