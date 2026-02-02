from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.schemas.case import CaseCreate, CaseOut, CaseUpdateStatus
from app.models.case import Case
from app.services import cases as case_service

router = APIRouter()


@router.get("/", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), _=Depends(require_auth)):
    items = case_service.list_cases(db)
    return [CaseOut(**case_service.to_case_out(db, c)) for c in items]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return CaseOut(**case_service.to_case_out(db, c))


@router.post("/", response_model=CaseOut)
def create_case(
    payload: CaseCreate, db: Session = Depends(get_db), user=Depends(require_auth)
):
    c = case_service.create_case(db, payload)
    from app.services.activity_log import log_activity
    log_activity(db, action="case_create", entity_type="case", entity_id=c.id, user_id=user.id)
    return CaseOut(**case_service.to_case_out(db, c))


@router.patch("/{case_id}/status", response_model=CaseOut)
def update_case_status(case_id: int, payload: CaseUpdateStatus, db: Session = Depends(get_db), _=Depends(require_auth)):
    c = case_service.update_case_status(db, case_id=case_id, status_value=payload.status)
    return CaseOut(**case_service.to_case_out(db, c))


