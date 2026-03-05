from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, FeeEventType
from app.models.fee_event import FeeEvent
from app.services.boi_fx import FxLookupError, get_usd_ils_rate
from app.services.expenses import get_case_excess_remaining, get_deductible_summary
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
        # When both deductible_ils_gross and deductible_usd present, prefer ILS (no FX).
        if key == "deductible_usd" and "deductible_ils_gross" in updates and updates["deductible_ils_gross"] is not None:
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


def merge_raw_import_fields(
    case: Case, raw: dict[str, Any], *, overwrite_blanks: bool = False
) -> None:
    """Merge raw key/values into case.raw_import_fields_json. Display-only; not used in calculations."""
    current = (case.raw_import_fields_json or {}).copy()
    for k, v in raw.items():
        if overwrite_blanks:
            current[k] = v
        else:
            if v is not None and v != "":
                current[k] = v
    case.raw_import_fields_json = current


def update_case_status(db: Session, *, case_id: int, status_value) -> Case:
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    c.status = status_value
    db.commit()
    db.refresh(c)
    return c


def get_latest_fee_stage_by_case_ids(db: Session, case_ids: list[int]) -> dict[int, str]:
    """
    Return mapping case_id -> display string for current procedure stage (one query).
    - Single-stage fee events: return event_type code (e.g. COURT_STAGE_1_DEFENSE).
    - STAGE_BILLING with new_codes: return last code, optionally "{last_code}(+K)" where K = len(new_codes)-1.
    - STAGE_BILLING with no new_codes: return "STAGE_BILLING:0" for frontend fallback.
    """
    if not case_ids:
        return {}
    from app.models.enums import FeeEventType
    from app.models.fee_event import FeeEvent

    rows = (
        db.query(FeeEvent.case_id, FeeEvent.event_type, FeeEvent.breakdown_json)
        .filter(FeeEvent.case_id.in_(case_ids))
        .order_by(FeeEvent.event_date.desc(), FeeEvent.id.desc())
        .all()
    )
    result: dict[int, str] = {}
    for case_id, event_type, breakdown_json in rows:
        if case_id not in result:
            if event_type == FeeEventType.STAGE_BILLING:
                new_codes = (breakdown_json or {}).get("new_codes") if breakdown_json else None
                if isinstance(new_codes, list) and len(new_codes) > 0:
                    last_code = new_codes[-1]
                    if not isinstance(last_code, str):
                        last_code = str(last_code)
                    if len(new_codes) > 1:
                        result[case_id] = f"{last_code}(+{len(new_codes) - 1})"
                    else:
                        result[case_id] = last_code
                else:
                    result[case_id] = "STAGE_BILLING:0"
            else:
                result[case_id] = event_type.value if hasattr(event_type, "value") else str(event_type)
    return result


def _effective_procedure_stage(case: Case, computed_stage: str | None) -> str | None:
    """Override takes precedence; else computed from fee events."""
    if case.procedure_stage_override and str(case.procedure_stage_override).strip():
        return str(case.procedure_stage_override).strip()
    return computed_stage


def to_case_out(
    db: Session, case: Case, *, current_procedure_stage: str | None = None
) -> dict:
    excess = get_case_excess_remaining(db, case)
    effective_stage = _effective_procedure_stage(case, current_procedure_stage)
    out = {
        "id": case.id,
        "case_reference": case.case_reference,
        "case_name": case.case_name,
        "case_type": case.case_type,
        "status": case.status,
        "open_date": case.open_date,
        "retainer_anchor_date": case.retainer_anchor_date,
        "branch_name": case.branch_name,
        "current_procedure_stage": effective_stage,
        "procedure_stage_override": getattr(case, "procedure_stage_override", None),
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
        "raw_import_fields_json": case.raw_import_fields_json or {},
        "excess_remaining_ils_gross": excess,
    }
    return out


def build_case_overview_summary(db: Session, case_id: int) -> dict | None:
    """
    Build aggregated overview for GET /cases/{id}/overview-summary.
    Single DB session; reuses existing service functions. No billing formula changes.
    """
    import datetime as dt

    from app.models.fee_event import FeeEvent
    from app.services import expenses as expense_service
    from app.services import retainer as retainer_service

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return None

    stages = get_latest_fee_stage_by_case_ids(db, [case.id])
    computed_stage = stages.get(case.id)
    current_stage = _effective_procedure_stage(case, computed_stage)

    # Fees: sum from fee events; last event
    fee_events = (
        db.query(FeeEvent)
        .filter(FeeEvent.case_id == case_id)
        .order_by(FeeEvent.event_date.desc(), FeeEvent.id.desc())
        .all()
    )
    total_fees = sum(Decimal(str(e.computed_amount_ils_gross)) for e in fee_events)
    fees_due = sum(Decimal(str(e.amount_due_cash_ils_gross)) for e in fee_events)
    last_fee = fee_events[0] if fee_events else None
    fees_overview = {
        "total_fees_ils": q_ils(total_fees),
        "fees_due_ils": q_ils(fees_due),
        "last_fee_event_date": last_fee.event_date.isoformat() if last_fee else None,
        "last_fee_event_amount": q_ils(Decimal(str(last_fee.computed_amount_ils_gross))) if last_fee else None,
    }

    # Retainer: credit from summary, monthly from retainer_gross_for_month(today)
    r_summary = retainer_service.retainer_summary(db, case_id=case_id)
    today = dt.date.today()
    monthly = retainer_service.retainer_gross_for_month(today)
    retainer_overview = {
        "current_credit_ils": r_summary["retainer_credit_balance_ils_gross"],
        "monthly_gross_ils": monthly,
    }

    # Expenses & deductible
    exp_summary = expense_service.get_expenses_summary(db, case_id)
    ded_summary = expense_service.get_deductible_summary(db, case)

    return {
        "case_reference": case.case_reference,
        "case_name": case.case_name,
        "branch_name": case.branch_name,
        "status": case.status.value,
        "current_procedure_stage": current_stage,
        "fees": fees_overview,
        "retainer": retainer_overview,
        "expenses": {
            "total_expenses_ils": exp_summary["total_expenses_ils"],
            "deductible_consumed_ils": exp_summary["deductible_consumed_by_expenses_ils"],
        },
        "deductible": {
            "total_ils": ded_summary["deductible_total_ils"],
            "remaining_ils": ded_summary["deductible_remaining_ils"],
            "excess_remaining_ils": ded_summary["excess_remaining_ils"],
        },
    }


# Raw import keys (lowercase) that suggest retainer / deductible / expenses for "not mapped" heuristic.
_RAW_RETAINER_KEY_SUBSTRINGS = ("retainer",)
_RAW_DEDUCTIBLE_KEY_SUBSTRINGS = ("deductible", "excess")
_RAW_EXPENSES_KEY_SUBSTRINGS = ("expense",)


def _raw_has_group(raw: dict | None, substrings: tuple[str, ...]) -> bool:
    if not raw:
        return False
    keys_lower = " ".join(k.lower() for k in raw.keys())
    return any(s in keys_lower for s in substrings)


def get_case_warnings(db: Session, case_id: int) -> list[dict[str, Any]]:
    """
    Data quality warnings for a case (read-only). No formula or data changes.
    Returns list of { code, severity, title, details, action_tab? }.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return []

    warnings: list[dict[str, Any]] = []

    # 1) Missing core fields
    if not (getattr(case, "case_name", None) or "").strip():
        warnings.append({
            "code": "MISSING_CASE_NAME",
            "severity": "warn",
            "title": "חסר שם תיק (צדדים)",
            "details": "מומלץ למלא שם תיק לצורך זיהוי ורישום.",
            "action_tab": "overview",
        })
    if getattr(case, "case_type", None) is None:
        warnings.append({
            "code": "MISSING_CASE_TYPE",
            "severity": "error",
            "title": "חסר סוג תיק",
            "details": "סוג תיק נדרש לדיווח וחיוב.",
            "action_tab": "overview",
        })
    if getattr(case, "open_date", None) is None:
        warnings.append({
            "code": "MISSING_OPEN_DATE",
            "severity": "error",
            "title": "חסר תאריך פתיחה",
            "details": "תאריך פתיחה נדרש לחישובים.",
            "action_tab": "overview",
        })

    # 2) Deductible/excess
    d_ils = getattr(case, "deductible_ils_gross", None)
    d_usd = getattr(case, "deductible_usd", None)
    d_ils_ok = d_ils is not None and (isinstance(d_ils, Decimal) and d_ils > 0 or (not isinstance(d_ils, Decimal) and float(d_ils or 0) > 0))
    d_usd_ok = d_usd is not None and (isinstance(d_usd, Decimal) and d_usd > 0 or (not isinstance(d_usd, Decimal) and float(d_usd or 0) > 0))
    if not d_ils_ok and not d_usd_ok:
        warnings.append({
            "code": "MISSING_DEDUCTIBLE",
            "severity": "error",
            "title": "חסר אקסס",
            "details": "לא הוגדר אקסס (ש״ח או USD).",
            "action_tab": "deductible",
        })
    else:
        ded_summary = get_deductible_summary(db, case)
        total_ils = ded_summary.get("deductible_total_ils") or Decimal("0")
        if total_ils == 0:
            warnings.append({
                "code": "DEDUCTIBLE_ZERO",
                "severity": "warn",
                "title": "אקסס = 0 (בדוק אם תקין)",
                "details": "סה״כ אקסס מוגדר כאפס.",
                "action_tab": "deductible",
            })

    # 3) Retainer configuration
    if getattr(case, "retainer_anchor_date", None) is None:
        warnings.append({
            "code": "MISSING_RETAINER_ANCHOR",
            "severity": "warn",
            "title": "חסר עוגן ריטיינר",
            "details": "תאריך עוגן ריטיינר נדרש לחישוב צבירה.",
            "action_tab": "retainer",
        })
    snap_paid = getattr(case, "retainer_snapshot_ils_gross", None)
    snap_through = getattr(case, "retainer_snapshot_through_month", None)
    snap_paid_set = snap_paid is not None and (float(snap_paid or 0) != 0)
    if snap_through is not None and not snap_paid_set:
        warnings.append({
            "code": "RETAINER_SNAPSHOT_MISMATCH",
            "severity": "warn",
            "title": "סנאפשוט ריטיינר: חסר סכום ששולם",
            "details": "הוגדר חודש סיום סנאפשוט אך לא סכום ששולם.",
            "action_tab": "retainer",
        })
    if snap_paid_set and snap_through is None:
        warnings.append({
            "code": "RETAINER_SNAPSHOT_MISMATCH",
            "severity": "warn",
            "title": "סנאפשוט ריטיינר: חסר חודש סיום",
            "details": "הוגדר סכום סנאפשוט אך לא חודש סיום.",
            "action_tab": "retainer",
        })

    # 4) Raw import fields not mapped (heuristic, info only)
    raw = getattr(case, "raw_import_fields_json", None) or {}
    if _raw_has_group(raw, _RAW_RETAINER_KEY_SUBSTRINGS):
        if not snap_paid_set and getattr(case, "retainer_snapshot_through_month", None) is None:
            warnings.append({
                "code": "RAW_RETAINER_NOT_MAPPED",
                "severity": "info",
                "title": "יש נתוני ריטיינר גולמיים שלא חוברו לחישוב",
                "details": "בדקו בייבוא גולמי והזינו סנאפשוט ריטיינר אם רלוונטי.",
                "action_tab": "retainer",
            })
    if _raw_has_group(raw, _RAW_DEDUCTIBLE_KEY_SUBSTRINGS) and not d_ils_ok and not d_usd_ok:
        warnings.append({
            "code": "RAW_DEDUCTIBLE_NOT_MAPPED",
            "severity": "info",
            "title": "יש נתוני השתתפות עצמית/אקסס גולמיים שלא חוברו",
            "details": "בדקו בייבוא גולמי והזינו אקסס אם רלוונטי.",
            "action_tab": "deductible",
        })
    exp_snap = getattr(case, "expenses_snapshot_ils_gross", None)
    exp_snap_set = exp_snap is not None and (float(exp_snap or 0) != 0)
    if _raw_has_group(raw, _RAW_EXPENSES_KEY_SUBSTRINGS) and not exp_snap_set:
        warnings.append({
            "code": "RAW_EXPENSES_NOT_MAPPED",
            "severity": "info",
            "title": "יש נתוני הוצאות גולמיים שלא חוברו לחישוב",
            "details": "בדקו בייבוא גולמי והזינו סנאפשוט הוצאות אם רלוונטי.",
            "action_tab": "expenses",
        })

    # 5) Fees
    fee_count = db.query(func.count(FeeEvent.id)).filter(FeeEvent.case_id == case_id).scalar() or 0
    has_fee_events = fee_count > 0
    if has_fee_events and getattr(case, "case_type", None) is None:
        warnings.append({
            "code": "FEES_BUT_NO_CASE_TYPE",
            "severity": "warn",
            "title": "קיים חיוב אך סוג תיק חסר",
            "details": "יש אירועי שכ״ט אך סוג התיק לא הוגדר.",
            "action_tab": "fees",
        })
    has_stage_billing = (
        db.query(FeeEvent.id)
        .filter(FeeEvent.case_id == case_id, FeeEvent.event_type == FeeEventType.STAGE_BILLING)
        .limit(1)
        .first()
        is not None
    )
    performed = getattr(case, "performed_fee_stage_codes", None)
    if has_stage_billing and (not performed or not isinstance(performed, list) or len(performed) == 0):
        warnings.append({
            "code": "STAGE_BILLING_NO_PERFORMED_CODES",
            "severity": "warn",
            "title": "קיים חיוב שלב אך לא נשמרו קודי שלבים שבוצעו",
            "details": "מומלץ לעדכן שלבים שבוצעו לצורך תצוגה עקבית.",
            "action_tab": "fees",
        })

    return warnings


def bulk_update_cases(db: Session, case_ids: list[int], updates) -> int:
    """
    Update multiple cases. Only fields set on updates (exclude_unset) are applied.
    procedure_stage_override: must be one of PROCEDURE_STAGE_OVERRIDE_CODES or None to clear.
    """
    from app.schemas.case import CaseBulkUpdateUpdates, PROCEDURE_STAGE_OVERRIDE_CODES

    if not isinstance(updates, CaseBulkUpdateUpdates):
        raise ValueError("updates must be CaseBulkUpdateUpdates")
    data = updates.model_dump(exclude_unset=True)
    if not data:
        return 0

    if "procedure_stage_override" in data:
        val = data["procedure_stage_override"]
        if val is not None and str(val).strip():
            if str(val).strip() not in PROCEDURE_STAGE_OVERRIDE_CODES:
                raise HTTPException(
                    status_code=400,
                    detail=f"procedure_stage_override must be one of {sorted(PROCEDURE_STAGE_OVERRIDE_CODES)} or null",
                )
        else:
            data["procedure_stage_override"] = None

    cases = db.query(Case).filter(Case.id.in_(case_ids)).all()
    for c in cases:
        if "status" in data:
            c.status = CaseStatus(data["status"])
        if "case_type" in data:
            c.case_type = CaseType(data["case_type"])
        if "procedure_stage_override" in data:
            c.procedure_stage_override = data["procedure_stage_override"]
    db.commit()
    return len(cases)


