from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.schemas.fee_event import FeeEventCreate, FeeEventOut
from app.services import fees as fee_service

router = APIRouter()

def _to_out(e) -> FeeEventOut:
    return FeeEventOut(
        id=e.id,
        event_type=e.event_type,
        event_date=e.event_date,
        quantity=e.quantity,
        amount_override_ils_gross=e.amount_override_ils_gross,
        computed_amount_ils_gross=e.computed_amount_ils_gross,
        amount_covered_by_credit_ils_gross=e.amount_covered_by_credit_ils_gross,
        amount_due_cash_ils_gross=e.amount_due_cash_ils_gross,
    )


@router.get("/", response_model=list[FeeEventOut])
def list_fee_events(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    items = fee_service.list_fee_events(db, case_id)
    return [_to_out(e) for e in items]


@router.post("/", response_model=FeeEventOut)
def add_fee_event(
    case_id: int, payload: FeeEventCreate, db: Session = Depends(get_db), user=Depends(require_auth)
):
    e = fee_service.add_fee_event(db, case_id=case_id, payload=payload)
    from app.services.activity_log import log_activity
    log_activity(db, action="fee_event_add", entity_type="fee_event", entity_id=e.id, user_id=user.id, details={"case_id": case_id})
    return _to_out(e)


