from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.schemas.expense import ExpenseCreate, ExpenseOut
from app.services import expenses as expense_service

router = APIRouter()

def _to_out(e) -> ExpenseOut:
    return ExpenseOut(
        id=e.id,
        case_id=e.case_id,
        supplier_name=e.supplier_name,
        amount_ils_gross=e.amount_ils_gross,
        service_description=e.service_description,
        demand_received_date=e.demand_received_date,
        expense_date=e.expense_date,
        category=e.category,
        payer=e.payer,
        attachment_url=e.attachment_url,
        split_group_id=str(e.split_group_id) if e.split_group_id else None,
        is_split_part=e.is_split_part,
    )


@router.get("/", response_model=list[ExpenseOut])
def list_expenses(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    items = expense_service.list_expenses(db, case_id)
    return [_to_out(e) for e in items]


@router.post("/", response_model=list[ExpenseOut])
def add_expense(case_id: int, payload: ExpenseCreate, db: Session = Depends(get_db), _=Depends(require_auth)):
    # returns 1 expense or 2 split parts
    created = expense_service.add_expense(db, case_id=case_id, payload=payload)
    return [_to_out(e) for e in created]


