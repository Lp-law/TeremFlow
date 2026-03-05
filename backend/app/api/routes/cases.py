from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.case import Case
from app.services import case_export as export_service
from app.schemas.case import CaseBulkUpdateRequest, CaseBulkUpdateResponse, CaseCreate, CaseOut, CaseUpdateStatus
from app.schemas.case_overview import CaseOverviewSummaryOut
from app.schemas.warnings import CaseWarningOut, CaseWarningsOut
from app.services import cases as case_service

router = APIRouter()


@router.get("/", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), _=Depends(require_auth)):
    items = case_service.list_cases(db)
    case_ids = [c.id for c in items]
    stages = case_service.get_latest_fee_stage_by_case_ids(db, case_ids)
    return [
        CaseOut(**case_service.to_case_out(db, c, current_procedure_stage=stages.get(c.id)))
        for c in items
    ]


@router.get("/{case_id}/overview-summary", response_model=CaseOverviewSummaryOut)
def get_case_overview_summary(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    data = case_service.build_case_overview_summary(db, case_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return CaseOverviewSummaryOut(**data)


@router.get("/{case_id}/warnings", response_model=CaseWarningsOut)
def get_case_warnings(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    warnings = case_service.get_case_warnings(db, case_id)
    return CaseWarningsOut(warnings=[CaseWarningOut(**w) for w in warnings])


@router.get("/{case_id}/export")
def export_case(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    """Smart Case Export: download single-case XLSX (overview, fees, retainer, expenses, deductible, raw import)."""
    xlsx_bytes, filename = export_service.build_case_export_xlsx(db, case_id)
    if not xlsx_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    stages = case_service.get_latest_fee_stage_by_case_ids(db, [c.id])
    return CaseOut(**case_service.to_case_out(db, c, current_procedure_stage=stages.get(c.id)))


@router.post("/", response_model=CaseOut)
def create_case(
    payload: CaseCreate, db: Session = Depends(get_db), user=Depends(require_auth)
):
    c = case_service.create_case(db, payload)
    from app.services.activity_log import log_activity
    log_activity(db, action="case_create", entity_type="case", entity_id=c.id, user_id=user.id)
    return CaseOut(**case_service.to_case_out(db, c))


@router.patch("/bulk-update", response_model=CaseBulkUpdateResponse)
def bulk_update_cases(
    payload: CaseBulkUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    if payload.updates.is_empty():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="At least one field in updates must be provided")
    updated_count = case_service.bulk_update_cases(db, payload.case_ids, payload.updates)
    from app.services.activity_log import log_activity
    log_activity(
        db,
        action="cases_bulk_update",
        entity_type="case",
        entity_id=0,
        user_id=user.id,
        details={"updated_count": updated_count, "fields": list(payload.updates.model_dump(exclude_unset=True).keys())},
    )
    return CaseBulkUpdateResponse(updated_count=updated_count)


@router.patch("/{case_id}/status", response_model=CaseOut)
def update_case_status(case_id: int, payload: CaseUpdateStatus, db: Session = Depends(get_db), _=Depends(require_auth)):
    c = case_service.update_case_status(db, case_id=case_id, status_value=payload.status)
    return CaseOut(**case_service.to_case_out(db, c))


