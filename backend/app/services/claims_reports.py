from __future__ import annotations

import datetime as dt
import re
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
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

UNIQUE_LINKED_ROW_INDEX = "uq_claims_report_rows_active_linked_case_per_report"

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
    "needs_manual_review",
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
        .filter(ClaimsReportRow.deleted_at.is_(None))
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
                "seed_import_metadata_json": report.seed_import_metadata_json,
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
    if report.status == ClaimsReportStatus.FINAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Final report cannot be deleted",
        )
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
        seed_import_metadata_json=src.seed_import_metadata_json,
        created_by_user_id=user_id,
    )
    db.add(new_report)
    db.flush()
    src_rows = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.report_id == src.id, ClaimsReportRow.deleted_at.is_(None))
        .all()
    )
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
                needs_manual_review=r.needs_manual_review,
                import_metadata_json=r.import_metadata_json,
                deleted_at=None,
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
        "needs_manual_review": row.needs_manual_review,
        "last_synced_at": row.last_synced_at,
        "last_manual_update_at": row.last_manual_update_at,
        "import_metadata_json": row.import_metadata_json,
        "source_snapshot_json": row.source_snapshot_json,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "narrative_preview": narrative_preview,
    }


def _report_to_out(db: Session, report: ClaimsReport) -> dict[str, Any]:
    rows_count = (
        db.query(func.count(ClaimsReportRow.id))
        .filter(ClaimsReportRow.report_id == report.id, ClaimsReportRow.deleted_at.is_(None))
        .scalar()
        or 0
    )
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
        "seed_import_metadata_json": report.seed_import_metadata_json,
    }


def get_report_details(db: Session, report_id: int) -> dict[str, Any]:
    report = get_report_or_404(db, report_id)
    rows = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.report_id == report.id, ClaimsReportRow.deleted_at.is_(None))
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


def _normalize_text(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _first_non_empty(data: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        if k in data and data[k] not in (None, "", []):
            return data[k]
    return None


def _to_decimal_or_none(v: Any) -> Decimal | None:
    if v in (None, ""):
        return None
    try:
        return q_ils(Decimal(str(v).replace(",", "").strip()))
    except Exception:
        return None


def _to_bool(v: Any, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y", "כן"}:
        return True
    if s in {"false", "0", "no", "n", "לא"}:
        return False
    return default


def _map_category(raw_value: Any):
    v = _normalize_text(raw_value)
    if not v:
        return None
    mapping = {
        "court_reported": "COURT_REPORTED_TO_INSURER",
        "prelitigation_reported": "REPORTED_WITHOUT_CLAIM",
        "not_reported_or_small_claims": "NOT_REPORTED_TO_INSURER",
        "non_medical_malpractice": "NON_MEDICAL_MALPRACTICE",
        "court_reported_to_insurer": "COURT_REPORTED_TO_INSURER",
        "בתי משפט + דווח לביטוח": "COURT_REPORTED_TO_INSURER",
        "reported_without_claim": "REPORTED_WITHOUT_CLAIM",
        "דווח ללא תביעה": "REPORTED_WITHOUT_CLAIM",
        "not_reported_to_insurer": "NOT_REPORTED_TO_INSURER",
        "לא דווח לביטוח": "NOT_REPORTED_TO_INSURER",
        "non_medical_malpractice": "NON_MEDICAL_MALPRACTICE",
        "לא רשלנות רפואית": "NON_MEDICAL_MALPRACTICE",
        "other": "OTHER",
        "אחר": "OTHER",
    }
    enum_key = mapping.get(v)
    if not enum_key:
        return None
    from app.models.enums import ClaimsCategory

    return ClaimsCategory(enum_key)


def _is_strong_identifier(value: str) -> bool:
    if not value:
        return False
    digits = sum(ch.isdigit() for ch in value)
    # Conservative rule to avoid over-matching generic tokens.
    return len(value) >= 6 and digits >= 3


def _map_final_outcome(raw_value: Any):
    v = _normalize_text(raw_value)
    if not v:
        return None
    mapping = {
        "settlement": "SETTLEMENT",
        "פשרה": "SETTLEMENT",
        "judgment_for_plaintiff": "JUDGMENT_FOR_PLAINTIFF",
        "פסק דין לטובת התובע": "JUDGMENT_FOR_PLAINTIFF",
        "claim_rejected": "CLAIM_REJECTED",
        "תביעה נדחתה": "CLAIM_REJECTED",
        "claim_rejected_with_costs": "CLAIM_REJECTED_WITH_COSTS",
        "תביעה נדחתה עם הוצאות": "CLAIM_REJECTED_WITH_COSTS",
        "closed_without_payment": "CLOSED_WITHOUT_PAYMENT",
        "נסגר ללא תשלום": "CLOSED_WITHOUT_PAYMENT",
        "other": "OTHER",
        "אחר": "OTHER",
    }
    enum_key = mapping.get(v)
    if not enum_key:
        return None
    from app.models.enums import ClaimsFinalOutcomeType

    return ClaimsFinalOutcomeType(enum_key)


def _map_report_case_status(raw_value: Any):
    v = _normalize_text(raw_value)
    if not v:
        return None
    mapping = {
        "open": "OPEN",
        "פתוח": "OPEN",
        "closed": "CLOSED",
        "סגור": "CLOSED",
        "cannot_assess_yet": "CANNOT_ASSESS_YET",
        "לא ניתן להעריך": "CANNOT_ASSESS_YET",
        "no_exposure": "NO_EXPOSURE",
        "ללא חשיפה": "NO_EXPOSURE",
        "rejected_expected": "REJECTED_EXPECTED",
        "צפי לדחייה": "REJECTED_EXPECTED",
        "settled": "SETTLED",
        "פשרה": "SETTLED",
        "judgment": "JUDGMENT",
        "פסק דין": "JUDGMENT",
        "rejected": "REJECTED",
        "נדחה": "REJECTED",
        "rejected_with_costs": "REJECTED_WITH_COSTS",
        "נדחה עם הוצאות": "REJECTED_WITH_COSTS",
    }
    enum_key = mapping.get(v)
    if not enum_key:
        return None
    return ClaimsReportCaseStatus(enum_key)


def _extract_seed_rows(seed_payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report_meta: dict[str, Any] = {}
    normalized_rows: list[dict[str, Any]] = []

    def _append_rows(rows_like: Any, category_hint: Any = None) -> None:
        if not isinstance(rows_like, list):
            return
        for item in rows_like:
            if isinstance(item, dict):
                normalized_rows.append({"raw": item, "category_hint": category_hint})

    if isinstance(seed_payload, list):
        _append_rows(seed_payload)
        return report_meta, normalized_rows

    if not isinstance(seed_payload, dict):
        return report_meta, normalized_rows

    report_meta_obj = _first_non_empty(seed_payload, ["report", "report_metadata", "metadata"])
    if isinstance(report_meta_obj, dict):
        report_meta = report_meta_obj

    _append_rows(_first_non_empty(seed_payload, ["rows", "items", "cases", "records"]))

    categories = seed_payload.get("categories")
    if isinstance(categories, list):
        for cat in categories:
            if not isinstance(cat, dict):
                continue
            hint = _first_non_empty(cat, ["category", "category_name", "title", "name"])
            _append_rows(_first_non_empty(cat, ["rows", "items", "cases", "records"]), hint)
    elif isinstance(categories, dict):
        for cat_name, cat_rows in categories.items():
            _append_rows(cat_rows, cat_name)

    if not normalized_rows:
        for top_key, top_value in seed_payload.items():
            if isinstance(top_value, list) and top_key.lower() not in {"rows", "items", "cases", "records"}:
                _append_rows(top_value, top_key)

    return report_meta, normalized_rows


def _is_proceeding_match_in_raw(case: Case, proceeding_norm: str) -> bool:
    if not proceeding_norm:
        return False
    raw_json = case.raw_import_fields_json or {}
    if not isinstance(raw_json, dict):
        return False
    for val in raw_json.values():
        if _normalize_text(val) == proceeding_norm:
            return True
    return False


def _match_case_for_seed_row(db: Session, row_raw: dict[str, Any]) -> dict[str, Any]:
    explicit_candidate = _first_non_empty(row_raw, ["linked_case_candidate", "case_id", "linked_case_id"])
    explicit_candidate_id: int | None = None
    if isinstance(explicit_candidate, dict):
        maybe_id = _first_non_empty(explicit_candidate, ["id", "case_id", "linked_case_id"])
        try:
            explicit_candidate_id = int(maybe_id) if maybe_id is not None else None
        except Exception:
            explicit_candidate_id = None
    else:
        try:
            explicit_candidate_id = int(explicit_candidate) if explicit_candidate is not None else None
        except Exception:
            explicit_candidate_id = None

    if explicit_candidate_id:
        explicit_case = db.query(Case).filter(Case.id == explicit_candidate_id, Case.deleted_at.is_(None)).first()
        if explicit_case:
            return {
                "matched_case_id": explicit_case.id,
                "suggested_case_id": explicit_case.id,
                "confidence": 1.0,
                "matched_by_rule": "explicit_case_id",
            }

    case_reference = _normalize_text(
        _first_non_empty(row_raw, ["case_reference_text", "case_reference", "reference", "claim_reference"])
    )
    proceeding_number = _normalize_text(_first_non_empty(row_raw, ["proceeding_number", "proceeding_no", "case_number"]))
    case_title = _normalize_text(_first_non_empty(row_raw, ["case_title", "case_name", "title", "name"]))

    if not (case_reference or proceeding_number or case_title):
        return {"matched_case_id": None, "suggested_case_id": None, "confidence": 0.0, "matched_by_rule": None}

    strong_case_reference = case_reference if _is_strong_identifier(case_reference) else ""
    strong_proceeding_number = proceeding_number if _is_strong_identifier(proceeding_number) else ""

    cases = db.query(Case).filter(Case.deleted_at.is_(None)).all()
    ref_matches: list[int] = []
    proceeding_matches: list[int] = []
    title_matches: list[int] = []
    for c in cases:
        c_ref = _normalize_text(c.case_reference)
        c_name = _normalize_text(c.case_name)
        if strong_case_reference and c_ref == strong_case_reference:
            ref_matches.append(c.id)
        if strong_proceeding_number and (c_ref == strong_proceeding_number or _is_proceeding_match_in_raw(c, strong_proceeding_number)):
            proceeding_matches.append(c.id)
        if case_title and c_name and len(case_title) >= 10 and c_name == case_title:
            title_matches.append(c.id)

    if strong_case_reference and strong_proceeding_number:
        overlap = sorted(set(ref_matches).intersection(set(proceeding_matches)))
        if len(overlap) == 1:
            return {
                "matched_case_id": overlap[0],
                "suggested_case_id": overlap[0],
                "confidence": 1.0,
                "matched_by_rule": "case_reference_and_proceeding_exact",
            }
        if len(overlap) > 1:
            return {
                "matched_case_id": None,
                "suggested_case_id": overlap[0],
                "confidence": 0.9,
                "matched_by_rule": "case_reference_and_proceeding_exact_ambiguous",
            }

    if strong_case_reference:
        unique_ref = sorted(set(ref_matches))
        if len(unique_ref) == 1:
            return {
                "matched_case_id": unique_ref[0],
                "suggested_case_id": unique_ref[0],
                "confidence": 0.98,
                "matched_by_rule": "case_reference_exact_strong",
            }
        if len(unique_ref) > 1:
            return {
                "matched_case_id": None,
                "suggested_case_id": unique_ref[0],
                "confidence": 0.85,
                "matched_by_rule": "case_reference_exact_ambiguous",
            }

    if strong_proceeding_number:
        unique_proc = sorted(set(proceeding_matches))
        if len(unique_proc) == 1:
            return {
                "matched_case_id": unique_proc[0],
                "suggested_case_id": unique_proc[0],
                "confidence": 0.97,
                "matched_by_rule": "proceeding_exact_strong",
            }
        if len(unique_proc) > 1:
            return {
                "matched_case_id": None,
                "suggested_case_id": unique_proc[0],
                "confidence": 0.82,
                "matched_by_rule": "proceeding_exact_ambiguous",
            }

    unique_title = sorted(set(title_matches))
    if len(unique_title) == 1:
        return {
            "matched_case_id": None,
            "suggested_case_id": unique_title[0],
            "confidence": 0.7,
            "matched_by_rule": "case_title_exact_suggestion_only",
        }
    if len(unique_title) > 1:
        return {
            "matched_case_id": None,
            "suggested_case_id": unique_title[0],
            "confidence": 0.6,
            "matched_by_rule": "case_title_exact_ambiguous",
        }
    return {"matched_case_id": None, "suggested_case_id": None, "confidence": 0.0, "matched_by_rule": None}


def _ensure_unique_linked_case(
    db: Session,
    *,
    report_id: int,
    linked_case_id: int | None,
    current_row_id: int | None = None,
) -> None:
    if not linked_case_id:
        return
    q = db.query(ClaimsReportRow).filter(
        ClaimsReportRow.report_id == report_id,
        ClaimsReportRow.linked_case_id == linked_case_id,
        ClaimsReportRow.deleted_at.is_(None),
    )
    if current_row_id is not None:
        q = q.filter(ClaimsReportRow.id != current_row_id)
    if q.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A linked row for this case already exists in this report",
        )


def _commit_or_raise_linked_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if UNIQUE_LINKED_ROW_INDEX in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A linked row for this case already exists in this report",
            ) from exc
        raise


def create_row(db: Session, *, report_id: int, payload, user_id: int | None) -> ClaimsReportRow:
    report = get_report_or_404(db, report_id)
    data = payload.model_dump(exclude_unset=True)
    _ensure_unique_linked_case(db, report_id=report_id, linked_case_id=data.get("linked_case_id"))
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
    _commit_or_raise_linked_conflict(db)
    db.refresh(row)
    return row


def update_row(db: Session, *, report_id: int, row_id: int, payload, user_id: int | None) -> ClaimsReportRow:
    report = get_report_or_404(db, report_id)
    row = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.id == row_id, ClaimsReportRow.report_id == report_id, ClaimsReportRow.deleted_at.is_(None))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    data = payload.model_dump(exclude_unset=True)
    target_linked_case_id = data.get("linked_case_id") if "linked_case_id" in data else row.linked_case_id
    _ensure_unique_linked_case(
        db,
        report_id=report_id,
        linked_case_id=target_linked_case_id,
        current_row_id=row_id,
    )
    if "linked_case_id" in data and data["linked_case_id"]:
        case = db.query(Case).filter(Case.id == data["linked_case_id"], Case.deleted_at.is_(None)).first()
        if not case:
            raise HTTPException(status_code=404, detail="Linked case not found")
        _apply_synced_fields_only(row, _prefill_from_case(db, case))
    _apply_payload_to_row(row, data, user_id=user_id)
    _touch_manual_metadata(row, data, user_id=user_id)
    if row.linked_case_id is None and row.linkage_type == ClaimsRowLinkageType.LINKED:
        row.linkage_type = ClaimsRowLinkageType.MANUAL
    _commit_or_raise_linked_conflict(db)
    db.refresh(row)
    return row


def delete_row(db: Session, *, report_id: int, row_id: int) -> None:
    report = get_report_or_404(db, report_id)
    row = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.id == row_id, ClaimsReportRow.report_id == report_id, ClaimsReportRow.deleted_at.is_(None))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")
    row.deleted_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


def import_rows_from_cases(db: Session, *, report_id: int, case_ids: list[int], category_for_report, include_in_report: bool) -> tuple[int, int]:
    report = get_report_or_404(db, report_id)
    unique_ids = sorted({int(c) for c in case_ids if c})
    if not unique_ids:
        return (0, 0)
    existing_case_ids = {
        c_id
        for (c_id,) in db.query(ClaimsReportRow.linked_case_id)
        .filter(
            ClaimsReportRow.report_id == report_id,
            ClaimsReportRow.linked_case_id.is_not(None),
            ClaimsReportRow.deleted_at.is_(None),
        )
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
    _commit_or_raise_linked_conflict(db)
    return (created, skipped)


def import_rows_from_seed_json(
    db: Session,
    *,
    report_id: int,
    seed_payload: Any,
    seed_file_name: str | None,
    allow_append: bool,
    auto_link_cases: bool,
    user_id: int | None,
) -> dict[str, int]:
    report = get_report_or_404(db, report_id)
    existing_rows_before = (
        db.query(func.count(ClaimsReportRow.id))
        .filter(ClaimsReportRow.report_id == report_id, ClaimsReportRow.deleted_at.is_(None))
        .scalar()
        or 0
    )
    if existing_rows_before > 0 and not allow_append:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report already has rows; import blocked unless allow_append=true",
        )

    report_meta, normalized_rows = _extract_seed_rows(seed_payload)
    if not normalized_rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seed JSON does not contain rows")

    batch_id = str(uuid.uuid4())
    imported_at = dt.datetime.now(dt.timezone.utc)
    created_rows = 0
    linked_rows = 0
    manual_rows = 0
    flagged_rows = 0
    skipped_rows = 0

    existing_linked_case_ids = {
        c_id
        for (c_id,) in db.query(ClaimsReportRow.linked_case_id)
        .filter(
            ClaimsReportRow.report_id == report_id,
            ClaimsReportRow.linked_case_id.is_not(None),
            ClaimsReportRow.deleted_at.is_(None),
        )
        .all()
    }

    for item in normalized_rows:
        raw = item["raw"]
        category_hint = item.get("category_hint")

        mapped_category = _map_category(
            _first_non_empty(
                raw,
                ["category_code", "category_for_report", "category", "category_name", "category_label"],
            )
            or category_hint
        )
        mapped_outcome = _map_final_outcome(_first_non_empty(raw, ["final_outcome_type", "outcome_type", "outcome"]))
        mapped_case_status = _map_report_case_status(_first_non_empty(raw, ["report_case_status", "case_status", "status"]))
        raw_text = _first_non_empty(raw, ["raw_text", "raw", "original_text"])
        narrative = _first_non_empty(raw, ["narrative_text", "narrative", "legal_narrative", "summary"])
        legal_summary = _first_non_empty(raw, ["legal_summary_text", "legal_summary"])

        row_payload: dict[str, Any] = {
            "linkage_type": ClaimsRowLinkageType.MANUAL,
            "case_reference_text": _first_non_empty(
                raw,
                ["case_reference_text", "case_reference", "reference", "claim_reference"],
            ),
            "case_title": _first_non_empty(raw, ["case_title", "case_name", "title", "name"]),
            "proceeding_number": _first_non_empty(raw, ["proceeding_number", "proceeding_no", "case_number"]),
            "court_name": _first_non_empty(raw, ["court_name", "court"]),
            "branch_name": _first_non_empty(raw, ["branch_name", "branch"]),
            "institution_name": _first_non_empty(raw, ["institution_name", "institution"]),
            "category_for_report": mapped_category,
            "report_case_status": mapped_case_status,
            "status_note": _first_non_empty(raw, ["status_note", "status_comment"]),
            "current_risk_assessment_ils": _to_decimal_or_none(
                _first_non_empty(raw, ["current_risk_assessment_ils", "risk_assessment_ils", "risk_ils"])
            ),
            "risk_assessment_text": _first_non_empty(raw, ["risk_assessment_text", "risk_text"]),
            "final_outcome_type": mapped_outcome,
            "final_outcome_amount_ils": _to_decimal_or_none(
                _first_non_empty(raw, ["final_outcome_amount_ils", "outcome_amount_ils", "final_amount_ils"])
            ),
            "awarded_costs_to_terem_ils": _to_decimal_or_none(
                _first_non_empty(raw, ["awarded_costs_to_terem_ils", "awarded_costs_ils"])
            ),
            "final_outcome_text": _first_non_empty(raw, ["final_outcome_text", "outcome_text"]),
            "deductible_usd": _to_decimal_or_none(_first_non_empty(raw, ["deductible_usd"])),
            "deductible_ils_gross": _to_decimal_or_none(_first_non_empty(raw, ["deductible_ils_gross"])),
            "amount_already_paid_on_deductible_ils": _to_decimal_or_none(
                _first_non_empty(raw, ["amount_already_paid_on_deductible_ils", "deductible_paid_ils"])
            ),
            "remaining_deductible_ils": _to_decimal_or_none(_first_non_empty(raw, ["remaining_deductible_ils"])),
            "expenses_total_ils": _to_decimal_or_none(_first_non_empty(raw, ["expenses_total_ils"])),
            "fees_total_ils": _to_decimal_or_none(_first_non_empty(raw, ["fees_total_ils"])),
            "retainer_charged_ils": _to_decimal_or_none(_first_non_empty(raw, ["retainer_charged_ils"])),
            "exposure_for_reserve_ils": _to_decimal_or_none(
                _first_non_empty(raw, ["exposure_for_reserve_ils", "reserve_exposure_ils"])
            ),
            "narrative_text": narrative or raw_text,
            "legal_summary_text": legal_summary,
            "internal_notes": _first_non_empty(raw, ["internal_notes", "notes"]),
            "include_in_report": _to_bool(_first_non_empty(raw, ["include_in_report", "include", "included"]), default=True),
        }

        match = _match_case_for_seed_row(db, raw) if auto_link_cases else {
            "matched_case_id": None,
            "suggested_case_id": None,
            "confidence": 0.0,
            "matched_by_rule": None,
        }
        matched_case_id = match["matched_case_id"]
        suggested_case_id = match["suggested_case_id"]

        if matched_case_id and matched_case_id in existing_linked_case_ids:
            skipped_rows += 1
            continue

        needs_manual_review = matched_case_id is None
        if matched_case_id:
            case = db.query(Case).filter(Case.id == matched_case_id, Case.deleted_at.is_(None)).first()
            if case:
                row = ClaimsReportRow(report_id=report_id)
                _apply_synced_fields_only(row, _prefill_from_case(db, case))
                existing_linked_case_ids.add(case.id)
                row_payload["linkage_type"] = ClaimsRowLinkageType.LINKED
                needs_manual_review = False
            else:
                row = ClaimsReportRow(report_id=report_id)
                matched_case_id = None
                needs_manual_review = True
        else:
            row = ClaimsReportRow(report_id=report_id)

        # Normalize enums from free-text values.
        if not row_payload.get("category_for_report"):
            row_payload["category_for_report"] = _map_category(category_hint)
        if row_payload.get("category_for_report") is None:
            from app.models.enums import ClaimsCategory

            row_payload["category_for_report"] = ClaimsCategory.OTHER
        if row_payload.get("report_case_status") is None:
            row_payload["report_case_status"] = ClaimsReportCaseStatus.OPEN

        if matched_case_id:
            row_payload["linked_case_id"] = matched_case_id
            row_payload["linkage_type"] = ClaimsRowLinkageType.LINKED

        _apply_payload_to_row(row, row_payload, user_id=user_id)
        row.needs_manual_review = _to_bool(_first_non_empty(raw, ["needs_manual_review"]), default=needs_manual_review)
        row.last_manual_update_at = imported_at
        row.import_metadata_json = {
            "source": "SEED_JSON",
            "batch_id": batch_id,
            "source_file": seed_file_name or "seed_payload",
            "imported_at": imported_at.isoformat(),
            "raw_text": raw_text,
            "matching": {
                "matched_case_id": matched_case_id,
                "suggested_case_id": suggested_case_id,
                "confidence": match["confidence"],
                "matched_by_rule": match["matched_by_rule"],
            },
            "raw_seed_row": raw,
        }
        db.add(row)
        created_rows += 1
        if matched_case_id:
            linked_rows += 1
        else:
            manual_rows += 1
        if row.needs_manual_review:
            flagged_rows += 1

    # Keep report metadata additive and append-only.
    previous_meta = report.seed_import_metadata_json or {}
    previous_imports = previous_meta.get("imports", []) if isinstance(previous_meta, dict) else []
    summary_entry = {
        "batch_id": batch_id,
        "source_file": seed_file_name or "seed_payload",
        "imported_at": imported_at.isoformat(),
        "rows_in_payload": len(normalized_rows),
        "created_rows": created_rows,
        "linked_rows": linked_rows,
        "manual_rows": manual_rows,
        "flagged_rows": flagged_rows,
        "skipped_rows": skipped_rows,
        "auto_link_cases": auto_link_cases,
        "allow_append": allow_append,
        "report_meta": report_meta,
    }
    report.seed_import_metadata_json = {
        "last_import": summary_entry,
        "imports": [*previous_imports, summary_entry][-20:],
    }

    _commit_or_raise_linked_conflict(db)
    return {
        "created_rows": created_rows,
        "linked_rows": linked_rows,
        "manual_rows": manual_rows,
        "flagged_rows": flagged_rows,
        "skipped_rows": skipped_rows,
        "existing_rows_before": int(existing_rows_before),
    }


def refresh_row_from_linked_case(db: Session, *, report_id: int, row_id: int, user_id: int | None = None) -> ClaimsReportRow:
    _ = user_id  # reserved for future audit detail enrichment
    get_report_or_404(db, report_id)
    row = (
        db.query(ClaimsReportRow)
        .filter(ClaimsReportRow.id == row_id, ClaimsReportRow.report_id == report_id, ClaimsReportRow.deleted_at.is_(None))
        .first()
    )
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
        .filter(
            ClaimsReportRow.report_id == report_id,
            ClaimsReportRow.linked_case_id.is_not(None),
            ClaimsReportRow.deleted_at.is_(None),
        )
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
        .filter(
            ClaimsReportRow.report_id == report.id,
            ClaimsReportRow.include_in_report.is_(True),
            ClaimsReportRow.deleted_at.is_(None),
        )
        .order_by(ClaimsReportRow.category_for_report.asc(), ClaimsReportRow.id.asc())
        .all()
    )
    return report, rows


def row_to_out(row: ClaimsReportRow) -> dict[str, Any]:
    return _row_to_out(row)


def report_to_out(db: Session, report: ClaimsReport) -> dict[str, Any]:
    return _report_to_out(db, report)
