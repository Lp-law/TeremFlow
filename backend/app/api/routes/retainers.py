from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.retainer import RetainerAccrual, RetainerPayment
from app.schemas.retainer import (
    RetainerAccrualOut,
    RetainerPaymentCreate,
    RetainerPaymentOut,
    RetainerSummary,
)
from app.services import fees as fee_service
from app.services import retainer as retainer_service

router = APIRouter()

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
    return RetainerPaymentOut(id=p.id, payment_date=p.payment_date, amount_ils_gross=p.amount_ils_gross)


@router.get("/accruals", response_model=list[RetainerAccrualOut])
def list_accruals(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    items = (
        db.query(RetainerAccrual)
        .filter(RetainerAccrual.case_id == case_id)
        .order_by(RetainerAccrual.accrual_month.desc())
        .all()
    )
    return [_accrual_out(a) for a in items]


@router.get("/payments", response_model=list[RetainerPaymentOut])
def list_payments(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    items = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.desc(), RetainerPayment.id.desc())
        .all()
    )
    return [_payment_out(p) for p in items]


@router.post("/payments", response_model=list[RetainerPaymentOut])
def add_payment(case_id: int, payload: RetainerPaymentCreate, db: Session = Depends(get_db), _=Depends(require_auth)):
    p = RetainerPayment(case_id=case_id, payment_date=payload.payment_date, amount_ils_gross=payload.amount_ils_gross)
    db.add(p)
    db.commit()
    db.refresh(p)

    retainer_service.allocate_payments_to_accruals(db, case_id=case_id)
    fee_service.apply_retainer_credit(db, case_id=case_id)

    items = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.desc(), RetainerPayment.id.desc())
        .all()
    )
    return [_payment_out(x) for x in items]


@router.get("/summary", response_model=RetainerSummary)
def summary(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    s = retainer_service.retainer_summary(db, case_id=case_id)
    return RetainerSummary(**s)


