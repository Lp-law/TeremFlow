from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.claims_report import ClaimsReport, ClaimsReportRow
from app.models.enums import (
    CaseStatus,
    ClaimsFinalOutcomeType,
    ClaimsReportCaseStatus,
    ClaimsReportStatus,
    ClaimsRowLinkageType,
)
from app.services.deductible import q_ils
from app.services.unified import get_unified_summary

SYNCED_FIELDS: tuple[str, ...] = (
    "linked_case_id",
    "linkage_type",
    "case_reference_text",
    "case_title",
    "branch_name",
    "deductible_usd",
    "deductible_ils_gross",
    "amount_already_paid_on_deductible_ils",
    "remaining_deductible_ils",
    "expenses_total_ils",
    "fees_total_ils",
    "retainer_charged_ils",
    "exposure_for_reserve_ils",
    "report_case_status",
    "source_snapshot_json",
)

MANUAL_FIELDS: tuple[str, ...] = (
    "category_for_report",
    "court_name",
    "proceeding_number",
    "institution_name",
    "status_note",
    "current_risk_assessment_ils",
    "risk_assessment_text",
    "final_outcome_type",
    "final_outcome_amount_ils",
    "awarded_costs_to_terem_ils",
    "final_outcome_date",
    "final_outcome_text",
    "narrative_text",
    "legal_summary_text",
    "internal_notes",
    "include_in_report",
)


def _as_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return q_ils(Decimal(str(v)))
    except Exception:
        return None


def get_report_or_404(db: Session, report_id: int) -> ClaimsReport:
    report = db.query(ClaimsReport).filter(ClaimsReport.id == report_id, ClaimsReport.deleted_at.is_(None)).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def list_reports(db: Session) -> list[dict[str, Any]]:
    rows_count_subq = (
        db.query(ClaimsReportRow.report_id, func.count(ClaimsReportRow.id).label("rows_count"))
        .group_by(ClaimsReportRow.report_id)
        .subquery()
    )
    rows = (
        db.query(ClaimsReport, func.coalesce(rows_count_subq.c.rows_count, 0))
        .outerjoin(rows_count_subq, ClaimsReport.id == rows_count_subq.c.report_id)
        .filter(ClaimsReport.deleted_at.is_(None))
        .order_by(ClaimsReport.created_at.desc(), ClaimsReport.id.desc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for report, rows_count in rows:
        out.append(
            {
                "id": report.id,
                "client_name": report.client_name,
                "institution_name": report.institution_name,
                "title": report.title,
                "report_cutoff_date": report.report_cutoff_date,
                "updated_to_date": report.updated_to_date,
                "recommended_reserve_ils": report.recommended_reserve_ils,
                "intro_text": report.intro_text,
                "closing_text": report.closing_text,
                "status": report.status,
                "template_key": report.template_key,
                "created_by_user_id": report.created_by_user_id,
                "finalized_at": report.finalized_at,
                "created_at": report.created_at,
                "updated_at": report.updated_at,
                "rows_count": int(rows_count or 0),
            }
        )
    return out


def create_report(db: Session, payload, *, user_id: int | None) -> ClaimsReport:
    report = ClaimsReport(
        client_name=payload.client_name,
        institution_name=payload.institution_name,
        title=payload.title,
        report_cutoff_date=payload.report_cutoff_date,
        updated_to_date=payload.updated_to_date,
        recommended_reserve_ils=payload.recommended_reserve_ils,
        intro_text=payload.intro_text,
        closing_text=payload.closing_text,
        status=ClaimsReportStatus.DRAFT,
        template_key=payload.template_key,
        created_by_user_id=user_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def update_report(db: Session, *, report_id: int, payload) -> ClaimsReport:
    report = get_report_or_404(db, report_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(report, k, v)
    db.commit()
    db.refresh(report)
    return report


def soft_delete_report(db: Session, *, report_id: int) -> ClaimsReport:
    report = get_report_or_404(db, report_id)
    report.deleted_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(report)
    return report


def finalize_report(db: Session, *, report_id: int) -> ClaimsReport:
    report = get_report_or_404(db, report_id)
    report.status = ClaimsReportStatus.FINAL
    if report.finalized_at is None:
        report.finalized_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    db.refresh(report)
    return report


def duplicate_report(db: Session, *, report_id: int, user_id: int | None) -> ClaimsReport:
    src = get_report_or_404(db, report_id)
    new_report = ClaimsReport(
        client_name=src.client_name,
        institution_name=src.institution_name,
        title=f"{src.title} (העתק)",
        report_cutoff_date=src.report_cutoff_date,
        updated_to_date=src.updated_to_date,
        recommended_reserve_ils=src.recommended_reserve_ils,
        intro_text=src.intro_text,
        closing_text=src.closing_text,
        status=ClaimsReportStatus.DRAFT,
        template_key=src.template_key,
        created_by_user_id=user_id,
    )
    db.add(new_report)
    db.flush()
    src_rows = db.query(ClaimsReportRow).filter(ClaimsReportRow.report_id == src.id).all()
    for r in src_rows:
        db.add(
            ClaimsReportRow(
                report_id=new_report.id,
                linked_case_id=r.linked_case_id,
                linkage_type=r.linkage_type,
                case_reference_text=r.case_reference_text,
                case_title=r.case_title,
                court_name=r.court_name,
                proceeding_number=r.proceeding_number,
                branch_name=r.branch_name,
                institution_name=r.institution_name,
                category_for_report=r.category_for_report,
                report_case_status=r.report_case_status,
                status_note=r.status_note,
                current_risk_assessment_ils=r.current_risk_assessment_ils,
                risk_assessment_text=r.risk_assessment_text,
                risk_assessment_updated_at=r.risk_assessment_updated_at,
                risk_assessment_updated_by_user_id=r.risk_assessment_updated_by_user_id,
                final_outcome_type=r.final_outcome_type,
                final_outcome_amount_ils=r.final_outcome_amount_ils,
                awarded_costs_to_terem_ils=r.awarded_costs_to_terem_ils,
                final_outcome_date=r.final_outcome_date,
                final_outcome_text=r.final_outcome_text,
                deductible_usd=r.deductible_usd,
                deductible_ils_gross=r.deductible_ils_gross,
                amount_already_paid_on_deductible_ils=r.amount_already_paid_on_deductible_ils,
                remaining_deductible_ils=r.remaining_deductible_ils,
                expenses_total_ils=r.expenses_total_ils,
                fees_total_ils=r.fees_total_ils,
                retainer_charged_ils=r.retainer_charged_ils,
                exposure_for_reserve_ils=r.exposure_for_reserve_ils,
                narrative_text=r.narrative_text,
                legal_summary_text=r.legal_summary_text,
                internal_notes=r.internal_notes,
                include_in_report=r.include_in_report,
                last_synced_at=r.last_synced_at,
                last_manual_update_at=r.last_manual_update_at,
                source_snapshot_json=r.source_snapshot_json,
            )
        )
    db.commit()
    db.refresh(new_report)
    return new_report


def compute_default_narrative(row: ClaimsReportRow) -> str:
    if row.report_case_status == ClaimsReportCaseStatus.CANNOT_ASSESS_YET:
        return "בשלב זה לא ניתן לבצע הערכת סיכון."
    if row.report_case_status == ClaimsReportCaseStatus.NO_EXPOSURE:
        return "הערכת הסיכון 0 ₪. אין חשיפה."
    if row.final_outcome_type == ClaimsFinalOutcomeType.SETTLEMENT:
        if row.final_outcome_amount_ils is not None:
            return f"התיק הסתיים בפשרה בסך של כ-{q_ils(Decimal(str(row.final_outcome_amount_ils)))} ₪."
        return "התיק הסתיים בפשרה."
    if row.final_outcome_type == ClaimsFinalOutcomeType.JUDGMENT_FOR_PLAINTIFF:
        if row.final_outcome_amount_ils is not None:
            return f"ניתן פסק דין לטובת התובע בסך של כ-{q_ils(Decimal(str(row.final_outcome_amount_ils)))} ₪."
        return "ניתן פסק דין לטובת התובע."
    if row.final_outcome_type == ClaimsFinalOutcomeType.CLAIM_REJECTED_WITH_COSTS:
        if row.awarded_costs_to_terem_ils is not None:
            return f"התביעה נדחתה והתובע חויב בהוצאות בסך של כ-{q_ils(Decimal(str(row.awarded_costs_to_terem_ils)))} ₪."
        return "התביעה נדחתה תוך חיוב בהוצאות."
    if row.final_outcome_type == ClaimsFinalOutcomeType.CLAIM_REJECTED:
        return "התביעה נדחתה."
    if row.current_risk_assessment_ils is not None:
        return f"חשיפה מוערכת של כ-{q_ils(Decimal(str(row.current_risk_assessment_ils)))} ₪."
    if row.exposure_for_reserve_ils is not None:
        return f"חשיפה לשמירת רזרבה בסך של כ-{q_ils(Decimal(str(row.exposure_for_reserve_ils)))} ₪."
    return "לא הוגדר נרטיב."


def _row_to_out(row: ClaimsReportRow) -> dict[str, Any]:
    narrative_preview = row.narrative_text or compute_default_narrative(row)
    return {
        "id": row.id,
        "report_id": row.report_id,
        "linked_case_id": row.linked_case_id,
        "linkage_type": row.linkage_type,
        "case_reference_text": row.case_reference_text,
        "case_title": row.case_title,
        "court_name": row.court_name,
        "proceeding_number": row.proceeding_number,
        "branch_name": row.branch_name,
        "institution_name": row.institution_name,
        "category_for_report": row.category_for_report,
        "report_case_status": row.report_case_status,
        "status_note": row.status_note,
        "current_risk_assessment_ils": row.current_risk_assessment_ils,
        "risk_assessment_text": row.risk_assessment_text,
        "risk_assessment_updated_at": row.risk_assessment_updated_at,
        "risk_assessment_updated_by_user_id": row.risk_assessment_updated_by_user_id,
        "final_outcome_type": row.final_outcome_type,
        "final_outcome_amount_ils": row.final_outcome_amount_ils,
        "awarded_costs_to_terem_ils": row.awarded_costs_to_terem_ils,
        "final_outcome_date": row.final_outcome_date,
        "final_outcome_text": row.final_outcome_text,
        "deductible_usd": row.deductible_usd,
        "deductible_ils_gross": row.deductible_ils_gross,
        "amount_already_paid_on_deductible_ils": row.amount_already_paid_on_deductible_ils,
        "remaining_deductible_ils": row.remaining_deductible_ils,
        "expenses_total_ils": row.expenses_total_ils,
        "fees_total_ils": row.fees_total_ils,
        "retainer_charged_ils": row.retainer_charged_ils,
        "exposure_for_reserve_ils": row.exposure_for_reserve_ils,
        "narrative_text": row.narrative_text,
        "legal_summary_text": row.legal_summary_text,
        "internal_notes": row.internal_notes,
        "include_in_report": row.include_in_report,
        "last_synced_at": row.last_synced_at,
        "last_manual_update_at": row.last_manual_update_at,
        "source_snapshot_json": row.source_snapshot_json,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "narrative_preview": narrative_preview,
    }


def _report_to_out(db: Session, report: ClaimsReport) -> dict[str, Any]:
    rows_count = db.query(func.count(ClaimsReportRow.id)).filter(ClaimsReportRow.report_id == report.id).scalar() or 0
    return {
        "id": report.id,
        "client_name": report.client_name,
        "institution_name": report.institution_name,
        "title": report.title,
        "report_cutoff_date": report.report_cutoff_date,
        "updated_to_date": report.updated_to_date,
        "recommended_reserve_ils": report.recommended_reserve_ils,
        "intro_text": report.intro_text,
        "closing_text": report.closing_text,
        "status": report.status,
        "template_key": report.template_key,
        "created_by_user_id": report.created_by_user_id,
        "finalized_at": report.finalized_at,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "rows_count": int(rows_count),
    }


def get_report_details(db: Session, report_id: int) -> dict[str, Any]:
    report = get_report_or_404(db, report_id)
    rows = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.report_id == report.id)
        .order_by(ClaimsReportRow.include_in_report.desc(), ClaimsReportRow.id.asc())
        .all()
    )
    return {"report": _report_to_out(db, report), "rows": [_row_to_out(r) for r in rows]}


def _prefill_from_case(db: Session, case: Case) -> dict[str, Any]:
    unified = get_unified_summary(db, case)
    excess_total = _as_decimal(unified.get("excess_total_ils")) or Decimal("0.00")
    remaining = _as_decimal(unified.get("excess_remaining_ils")) or Decimal("0.00")
    amount_paid = q_ils(max(Decimal("0.00"), excess_total - remaining))
    report_status = ClaimsReportCaseStatus.OPEN if case.status == CaseStatus.OPEN else ClaimsReportCaseStatus.CLOSED
    return {
        "linked_case_id": case.id,
        "linkage_type": ClaimsRowLinkageType.LINKED,
        "case_reference_text": case.case_reference,
        "case_title": case.case_name or case.case_reference,
        "branch_name": case.branch_name,
        "institution_name": None,
        "deductible_usd": _as_decimal(case.deductible_usd),
        "deductible_ils_gross": _as_decimal(case.deductible_ils_gross),
        "amount_already_paid_on_deductible_ils": amount_paid,
        "remaining_deductible_ils": remaining,
        "expenses_total_ils": _as_decimal(unified.get("expenses_total_ils")),
        "fees_total_ils": _as_decimal(unified.get("fees_by_stages_ils")),
        "retainer_charged_ils": _as_decimal(unified.get("retainer_charged_to_date_ils")),
        "exposure_for_reserve_ils": remaining,
        "report_case_status": report_status,
        "source_snapshot_json": {
            "pulled_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "case_id": case.id,
            "unified": {k: str(v) for k, v in unified.items() if isinstance(v, (Decimal, int, float, str))},
        },
    }


def _apply_payload_to_row(row: ClaimsReportRow, payload: dict[str, Any], *, user_id: int | None = None) -> None:
    for k, v in payload.items():
        setattr(row, k, v)
    if "current_risk_assessment_ils" in payload or "risk_assessment_text" in payload:
        row.risk_assessment_updated_at = dt.datetime.now(dt.timezone.utc)
        row.risk_assessment_updated_by_user_id = user_id


def _apply_synced_fields_only(row: ClaimsReportRow, synced_payload: dict[str, Any]) -> None:
    for field in SYNCED_FIELDS:
        if field in synced_payload:
            setattr(row, field, synced_payload[field])
    row.last_synced_at = dt.datetime.now(dt.timezone.utc)


def _touch_manual_metadata(row: ClaimsReportRow, payload: dict[str, Any], *, user_id: int | None = None) -> None:
    if any(field in payload for field in MANUAL_FIELDS):
        row.last_manual_update_at = dt.datetime.now(dt.timezone.utc)
    if "current_risk_assessment_ils" in payload or "risk_assessment_text" in payload:
        row.risk_assessment_updated_at = dt.datetime.now(dt.timezone.utc)
        row.risk_assessment_updated_by_user_id = user_id


def create_row(db: Session, *, report_id: int, payload, user_id: int | None) -> ClaimsReportRow:
    report = get_report_or_404(db, report_id)
    data = payload.model_dump(exclude_unset=True)
    row = ClaimsReportRow(report_id=report_id)
    if data.get("linked_case_id"):
        case = db.query(Case).filter(Case.id == data["linked_case_id"], Case.deleted_at.is_(None)).first()
        if not case:
            raise HTTPException(status_code=404, detail="Linked case not found")
        _apply_synced_fields_only(row, _prefill_from_case(db, case))
    _apply_payload_to_row(row, data, user_id=user_id)
    _touch_manual_metadata(row, data, user_id=user_id)
    if row.linked_case_id is None and row.linkage_type == ClaimsRowLinkageType.LINKED:
        row.linkage_type = ClaimsRowLinkageType.MANUAL
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_row(db: Session, *, report_id: int, row_id: int, payload, user_id: int | None) -> ClaimsReportRow:
    report = get_report_or_404(db, report_id)
    row = db.query(ClaimsReportRow).filter(ClaimsReportRow.id == row_id, ClaimsReportRow.report_id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    data = payload.model_dump(exclude_unset=True)
    if "linked_case_id" in data and data["linked_case_id"]:
        case = db.query(Case).filter(Case.id == data["linked_case_id"], Case.deleted_at.is_(None)).first()
        if not case:
            raise HTTPException(status_code=404, detail="Linked case not found")
        _apply_synced_fields_only(row, _prefill_from_case(db, case))
    _apply_payload_to_row(row, data, user_id=user_id)
    _touch_manual_metadata(row, data, user_id=user_id)
    if row.linked_case_id is None and row.linkage_type == ClaimsRowLinkageType.LINKED:
        row.linkage_type = ClaimsRowLinkageType.MANUAL
    db.commit()
    db.refresh(row)
    return row


def delete_row(db: Session, *, report_id: int, row_id: int) -> None:
    report = get_report_or_404(db, report_id)
    row = db.query(ClaimsReportRow).filter(ClaimsReportRow.id == row_id, ClaimsReportRow.report_id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    db.delete(row)
    db.commit()


def import_rows_from_cases(db: Session, *, report_id: int, case_ids: list[int], category_for_report, include_in_report: bool) -> tuple[int, int]:
    report = get_report_or_404(db, report_id)
    unique_ids = sorted({int(c) for c in case_ids if c})
    if not unique_ids:
        return (0, 0)
    existing_case_ids = {
        c_id
        for (c_id,) in db.query(ClaimsReportRow.linked_case_id)
        .filter(ClaimsReportRow.report_id == report_id, ClaimsReportRow.linked_case_id.is_not(None))
        .all()
    }
    cases = db.query(Case).filter(Case.id.in_(unique_ids), Case.deleted_at.is_(None)).all()
    created = 0
    skipped = 0
    for case in cases:
        if case.id in existing_case_ids:
            skipped += 1
            continue
        row = ClaimsReportRow(report_id=report_id)
        _apply_synced_fields_only(row, _prefill_from_case(db, case))
        row.category_for_report = category_for_report
        row.include_in_report = include_in_report
        row.last_manual_update_at = dt.datetime.now(dt.timezone.utc)
        db.add(row)
        created += 1
    db.commit()
    return (created, skipped)


def refresh_row_from_linked_case(db: Session, *, report_id: int, row_id: int, user_id: int | None = None) -> ClaimsReportRow:
    _ = user_id  # reserved for future audit detail enrichment
    get_report_or_404(db, report_id)
    row = db.query(ClaimsReportRow).filter(ClaimsReportRow.id == row_id, ClaimsReportRow.report_id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    if not row.linked_case_id:
        raise HTTPException(status_code=400, detail="Row is not linked to a case")
    case = db.query(Case).filter(Case.id == row.linked_case_id, Case.deleted_at.is_(None)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Linked case not found")
    _apply_synced_fields_only(row, _prefill_from_case(db, case))
    db.commit()
    db.refresh(row)
    return row


def refresh_all_linked_rows(db: Session, *, report_id: int, user_id: int | None = None) -> tuple[int, int]:
    _ = user_id  # reserved for future audit detail enrichment
    get_report_or_404(db, report_id)
    rows = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.report_id == report_id, ClaimsReportRow.linked_case_id.is_not(None))
        .all()
    )
    refreshed = 0
    skipped = 0
    for row in rows:
        case = db.query(Case).filter(Case.id == row.linked_case_id, Case.deleted_at.is_(None)).first()
        if not case:
            skipped += 1
            continue
        _apply_synced_fields_only(row, _prefill_from_case(db, case))
        refreshed += 1
    db.commit()
    return refreshed, skipped


def build_report_docx_payload(db: Session, report_id: int) -> tuple[ClaimsReport, list[ClaimsReportRow]]:
    report = get_report_or_404(db, report_id)
    rows = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.report_id == report.id, ClaimsReportRow.include_in_report.is_(True))
        .order_by(ClaimsReportRow.category_for_report.asc(), ClaimsReportRow.id.asc())
        .all()
    )
    return report, rows


def row_to_out(row: ClaimsReportRow) -> dict[str, Any]:
    return _row_to_out(row)


def report_to_out(db: Session, report: ClaimsReport) -> dict[str, Any]:
    return _report_to_out(db, report)
