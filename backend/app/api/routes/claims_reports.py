from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.schemas.claims_report import (
    ClaimsImportFromCasesOut,
    ClaimsImportFromCasesRequest,
    ClaimsReportCreate,
    ClaimsReportDetailsOut,
    ClaimsReportFinalizeOut,
    ClaimsReportOut,
    ClaimsReportRowCreate,
    ClaimsReportRowOut,
    ClaimsReportRowUpdate,
    ClaimsReportUpdate,
)
from app.services import claims_reports as claims_service
from app.services.claims_report_export import build_claims_report_docx

router = APIRouter()


@router.get("", response_model=list[ClaimsReportOut])
def list_claims_reports(db: Session = Depends(get_db), _=Depends(require_auth)):
    rows = claims_service.list_reports(db)
    return [ClaimsReportOut(**r) for r in rows]


@router.post("", response_model=ClaimsReportOut)
def create_claims_report(payload: ClaimsReportCreate, db: Session = Depends(get_db), user=Depends(require_auth)):
    report = claims_service.create_report(db, payload, user_id=user.id)
    return ClaimsReportOut(**claims_service.report_to_out(db, report))


@router.get("/{report_id}", response_model=ClaimsReportDetailsOut)
def get_claims_report(report_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    data = claims_service.get_report_details(db, report_id)
    return ClaimsReportDetailsOut(
        report=ClaimsReportOut(**data["report"]),
        rows=[ClaimsReportRowOut(**r) for r in data["rows"]],
    )


@router.patch("/{report_id}", response_model=ClaimsReportOut)
def update_claims_report(report_id: int, payload: ClaimsReportUpdate, db: Session = Depends(get_db), _=Depends(require_auth)):
    report = claims_service.update_report(db, report_id=report_id, payload=payload)
    return ClaimsReportOut(**claims_service.report_to_out(db, report))


@router.delete("/{report_id}", response_model=ClaimsReportOut)
def delete_claims_report(report_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    report = claims_service.soft_delete_report(db, report_id=report_id)
    return ClaimsReportOut(**claims_service.report_to_out(db, report))


@router.post("/{report_id}/finalize", response_model=ClaimsReportFinalizeOut)
def finalize_claims_report(report_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    report = claims_service.finalize_report(db, report_id=report_id)
    return ClaimsReportFinalizeOut(id=report.id, status=report.status, finalized_at=report.finalized_at)


@router.post("/{report_id}/duplicate", response_model=ClaimsReportOut)
def duplicate_claims_report(report_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    report = claims_service.duplicate_report(db, report_id=report_id, user_id=user.id)
    return ClaimsReportOut(**claims_service.report_to_out(db, report))


@router.post("/{report_id}/rows", response_model=ClaimsReportRowOut)
def create_claims_report_row(
    report_id: int, payload: ClaimsReportRowCreate, db: Session = Depends(get_db), user=Depends(require_auth)
):
    row = claims_service.create_row(db, report_id=report_id, payload=payload, user_id=user.id)
    return ClaimsReportRowOut(**claims_service.row_to_out(row))


@router.patch("/{report_id}/rows/{row_id}", response_model=ClaimsReportRowOut)
def update_claims_report_row(
    report_id: int, row_id: int, payload: ClaimsReportRowUpdate, db: Session = Depends(get_db), user=Depends(require_auth)
):
    row = claims_service.update_row(db, report_id=report_id, row_id=row_id, payload=payload, user_id=user.id)
    return ClaimsReportRowOut(**claims_service.row_to_out(row))


@router.delete("/{report_id}/rows/{row_id}")
def delete_claims_report_row(report_id: int, row_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    claims_service.delete_row(db, report_id=report_id, row_id=row_id)
    return {"ok": True}


@router.post("/{report_id}/rows/import-from-cases", response_model=ClaimsImportFromCasesOut)
def import_claims_rows_from_cases(
    report_id: int,
    payload: ClaimsImportFromCasesRequest,
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    created, skipped = claims_service.import_rows_from_cases(
        db,
        report_id=report_id,
        case_ids=payload.case_ids,
        category_for_report=payload.category_for_report,
        include_in_report=payload.include_in_report,
    )
    return ClaimsImportFromCasesOut(created_rows=created, skipped_rows=skipped)


@router.post("/{report_id}/export/docx")
def export_claims_report_docx(report_id: int, db: Session = Depends(get_db), _=Depends(require_auth)) -> Response:
    report, rows = claims_service.build_report_docx_payload(db, report_id)
    content, filename = build_claims_report_docx(report, rows)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
