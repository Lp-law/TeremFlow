from __future__ import annotations

import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, FeeEventType
from app.models.fee_event import FeeEvent
from app.services.boi_fx import FxLookupError, get_usd_ils_rate
from app.services.retainer import ensure_accruals_up_to, get_retainer_anchor_date
from app.services.unified import (
    _parse_override_to_decimal,
    excess_remaining_ils as unified_excess_remaining_ils,
    get_unified_summary,
)


def q_ils(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def list_cases(db: Session) -> list[Case]:
    return (
        db.query(Case)
        .filter(Case.deleted_at.is_(None))
        .order_by(Case.open_date.desc(), Case.id.desc())
        .all()
    )


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
    if c.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    c.status = status_value
    db.commit()
    db.refresh(c)
    return c


def get_case_if_not_deleted(db: Session, case_id: int) -> Case | None:
    """Return case if it exists and is not soft-deleted; else None."""
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c or c.deleted_at is not None:
        return None
    return c


def set_retainer_freeze(db: Session, *, case_id: int, freeze: bool) -> Case:
    """Set retainer_is_frozen and retainer_frozen_at. When freeze=True, set frozen_at=today; else clear."""
    c = get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    c.retainer_is_frozen = freeze
    c.retainer_frozen_at = dt.date.today() if freeze else None
    db.commit()
    db.refresh(c)
    return c


def update_case_retainer_dates(
    db: Session,
    *,
    case_id: int,
    retainer_anchor_date: dt.date | None = None,
    retainer_snapshot_through_month: dt.date | None = None,
    retainer_end_date: dt.date | None = None,
    retainer_end_date_sent: bool = False,
) -> Case:
    """Update retainer_anchor_date, retainer_snapshot_through_month, and/or retainer_end_date. Set retainer_end_date_sent=True with retainer_end_date=None to clear."""
    from app.services.unified import get_effective_end_date

    c = get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if retainer_anchor_date is not None:
        c.retainer_anchor_date = retainer_anchor_date
    if retainer_snapshot_through_month is not None:
        first = dt.date(
            retainer_snapshot_through_month.year,
            retainer_snapshot_through_month.month,
            1,
        )
        c.retainer_snapshot_through_month = first
    if retainer_end_date_sent:
        c.retainer_end_date = retainer_end_date
    db.commit()
    db.refresh(c)
    # Ensure accruals exist up to effective end (respects freeze)
    if c.retainer_snapshot_ils_gross is None:
        ensure_accruals_up_to(db, case_id=c.id, retainer_anchor_date=c.retainer_anchor_date, up_to=get_effective_end_date(c))
    elif c.retainer_snapshot_through_month is not None:
        ensure_accruals_up_to(
            db,
            case_id=c.id,
            retainer_anchor_date=c.retainer_anchor_date,
            snapshot_through_month=c.retainer_snapshot_through_month,
            up_to=get_effective_end_date(c),
        )
    return c


def update_case_identity(
    db: Session,
    *,
    case_id: int,
    case_reference: str | None = None,
    case_name: str | None = None,
) -> Case:
    """Update case_reference and/or case_name. Admin-only. Validates case_reference non-empty and no duplicate."""
    c = get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case_reference is not None:
        ref = str(case_reference).strip()
        if not ref:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="case_reference cannot be empty")
        existing = db.query(Case).filter(Case.case_reference == ref, Case.id != case_id, Case.deleted_at.is_(None)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="case_reference already in use")
        c.case_reference = ref
    if case_name is not None:
        c.case_name = str(case_name).strip() or None
    db.commit()
    db.refresh(c)
    return c


def update_case_notes(db: Session, *, case_id: int, case_notes: str | None) -> Case:
    """Update case_notes. Pass empty string to clear; None leaves unchanged if using PATCH with omit."""
    c = get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    c.case_notes = case_notes if case_notes is not None else c.case_notes
    db.commit()
    db.refresh(c)
    return c


def update_case_expenses_total(db: Session, *, case_id: int, expenses_total_ils_gross: Decimal) -> Case:
    """Set case-level expenses total (single editable number for UX)."""
    c = get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    c.expenses_total_ils_gross = expenses_total_ils_gross
    db.commit()
    db.refresh(c)
    return c


# Override keys that hold money amounts; we store them as decimal strings to preserve precision.
_MONEY_OVERRIDE_KEYS = frozenset({
    "excess_total_ils_override",
    "retainer_charged_override",
    "expenses_total_override",
    "fees_by_stages_override",
    "excess_remaining_override",
    "fee_diff_override",
})
# Only this key may be negative (fee_diff_ils = fees_by_stages - retainer_charged).
_FEE_DIFF_OVERRIDE_KEY = "fee_diff_override"


def _override_value_to_storage(v: Any) -> Any:
    """Store money overrides as decimal strings; preserve precision (no float)."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if isinstance(v, (int, float)):
        return str(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return v


def update_case_manual_overrides(db: Session, *, case_id: int, overrides: dict[str, Any]) -> Case:
    """Merge overrides into case.manual_overrides_json. Keys with None remove the override.
    Money values are stored as decimal strings (e.g. "1234.56") to preserve precision.
    Rejects negative values for all money overrides except fee_diff_override; rejects invalid numbers.
    """
    c = get_case_if_not_deleted(db, case_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    current = dict(getattr(c, "manual_overrides_json", None) or {})
    for k, v in overrides.items():
        if v is None:
            current.pop(k, None)
            continue
        if k in _MONEY_OVERRIDE_KEYS:
            parsed = _parse_override_to_decimal(v)
            if parsed is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid number for {k}",
                )
            if k != _FEE_DIFF_OVERRIDE_KEY and parsed < Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Negative value not allowed for {k}",
                )
            current[k] = _override_value_to_storage(parsed)
        else:
            current[k] = v
    c.manual_overrides_json = current if current else None
    db.commit()
    db.refresh(c)
    return c


def soft_delete_case(db: Session, *, case_id: int, user_id: int, delete_reason: str | None = None) -> Case:
    """Soft delete: set deleted_at, deleted_by_user_id, delete_reason. Case is excluded from list/details."""
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if c.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case already deleted")
    from datetime import datetime, timezone

    c.deleted_at = datetime.now(timezone.utc)
    c.deleted_by_user_id = user_id
    c.delete_reason = (delete_reason or "").strip() or None
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
        .filter(FeeEvent.case_id.in_(case_ids), FeeEvent.deleted_at.is_(None))
        .order_by(FeeEvent.event_date.desc(), FeeEvent.id.desc())
        .all()
    )
    result: dict[int, str] = {}
    for case_id, event_type, breakdown_json in rows:
        if case_id not in result:
            if event_type == FeeEventType.STAGE_BILLING:
                bj = breakdown_json if isinstance(breakdown_json, dict) else None
                new_codes = (bj or {}).get("new_codes") if bj else None
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
    """Override takes precedence; else computed from fee events. Never raises."""
    try:
        ov = getattr(case, "procedure_stage_override", None)
        if ov is not None and str(ov).strip():
            return str(ov).strip()
    except Exception:
        pass
    return computed_stage


def to_case_out(
    db: Session, case: Case, *, current_procedure_stage: str | None = None
) -> dict:
    excess = unified_excess_remaining_ils(db, case)
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
        "retainer_is_frozen": getattr(case, "retainer_is_frozen", False),
        "retainer_frozen_at": getattr(case, "retainer_frozen_at", None),
        "retainer_end_date": getattr(case, "retainer_end_date", None),
        "case_notes": getattr(case, "case_notes", None),
        "expenses_total_ils_gross": getattr(case, "expenses_total_ils_gross", None),
        "manual_overrides_json": getattr(case, "manual_overrides_json", None) or {},
    }
    return out


def build_case_overview_summary(db: Session, case_id: int) -> dict | None:
    """
    Build aggregated overview for GET /cases/{id}/overview-summary. Uses unified model.
    """
    import datetime as dt

    from app.models.fee_event import FeeEvent
    from app.services import retainer as retainer_service
    from app.services import unified as unified_service

    case = get_case_if_not_deleted(db, case_id)
    if not case:
        return None

    stages = get_latest_fee_stage_by_case_ids(db, [case.id])
    computed_stage = stages.get(case.id)
    current_stage = _effective_procedure_stage(case, computed_stage)

    u = unified_service.get_unified_summary(db, case)
    today = dt.date.today()
    monthly = retainer_service.retainer_gross_for_month(today)

    last_fee = (
        db.query(FeeEvent)
        .filter(FeeEvent.case_id == case_id, FeeEvent.deleted_at.is_(None))
        .order_by(FeeEvent.event_date.desc(), FeeEvent.id.desc())
        .first()
    )

    # Safe field access for legacy/incomplete data
    status_val = getattr(case, "status", None)
    status_str = status_val.value if status_val is not None else "OPEN"
    ref = getattr(case, "case_reference", None)
    case_ref = (str(ref).strip() or "") if ref is not None else ""
    frozen_at = getattr(case, "retainer_frozen_at", None)
    frozen_at_str = None
    if frozen_at is not None and hasattr(frozen_at, "isoformat"):
        try:
            frozen_at_str = frozen_at.isoformat()
        except Exception:
            pass
    last_fee_date = None
    last_fee_amount = None
    if last_fee:
        ed = getattr(last_fee, "event_date", None)
        if ed is not None and hasattr(ed, "isoformat"):
            try:
                last_fee_date = ed.isoformat()
            except Exception:
                pass
        amt = getattr(last_fee, "computed_amount_ils_gross", None)
        if amt is not None:
            try:
                last_fee_amount = q_ils(Decimal(str(amt)))
            except Exception:
                pass

    return {
        "case_reference": case_ref,
        "case_name": getattr(case, "case_name", None),
        "branch_name": getattr(case, "branch_name", None),
        "status": status_str,
        "current_procedure_stage": current_stage,
        "fees": {
            "fees_by_stages_ils": u["fees_by_stages_ils"],
            "retainer_charged_to_date_ils": u["retainer_charged_to_date_ils"],
            "fee_diff_ils": u["fee_diff_ils"],
            "last_fee_event_date": last_fee_date,
            "last_fee_event_amount": last_fee_amount,
        },
        "retainer": {
            "retainer_charged_to_date_ils": u["retainer_charged_to_date_ils"],
            "retainer_regular_theoretical_ils": u["retainer_regular_theoretical_ils"],
            "retainer_legacy_theoretical_ils": u["retainer_legacy_theoretical_ils"],
            "charged_months_count": u["charged_months_count"],
            "monthly_gross_ils": monthly,
            "retainer_is_frozen": getattr(case, "retainer_is_frozen", False),
            "retainer_frozen_at": frozen_at_str,
        },
        "expenses": {
            "total_expenses_ils": u["expenses_total_ils"],
        },
        "deductible": {
            "excess_total_ils": u["excess_total_ils"],
            "excess_remaining_ils": u["excess_remaining_ils"],
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
    def _safe_positive(val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, Decimal):
            return val > 0
        try:
            return float(val) > 0
        except (TypeError, ValueError):
            return False

    d_ils = getattr(case, "deductible_ils_gross", None)
    d_usd = getattr(case, "deductible_usd", None)
    d_ils_ok = _safe_positive(d_ils)
    d_usd_ok = _safe_positive(d_usd)
    if not d_ils_ok and not d_usd_ok:
        warnings.append({
            "code": "MISSING_DEDUCTIBLE",
            "severity": "error",
            "title": "חסר אקסס",
            "details": "לא הוגדר אקסס (ש״ח או USD).",
            "action_tab": "deductible",
        })
    else:
        try:
            u = get_unified_summary(db, case)
            total_ils = u.get("excess_total_ils") or Decimal("0")
        except Exception:
            total_ils = Decimal("0")
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
    try:
        snap_paid_set = snap_paid is not None and (float(snap_paid or 0) != 0)
    except (TypeError, ValueError):
        snap_paid_set = False
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
    raw_raw = getattr(case, "raw_import_fields_json", None)
    raw = raw_raw if isinstance(raw_raw, dict) else {}
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
    try:
        exp_snap_set = exp_snap is not None and (float(exp_snap or 0) != 0)
    except (TypeError, ValueError):
        exp_snap_set = False
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

    cases = db.query(Case).filter(Case.id.in_(case_ids), Case.deleted_at.is_(None)).all()
    for c in cases:
        if "status" in data:
            c.status = CaseStatus(data["status"])
        if "case_type" in data:
            c.case_type = CaseType(data["case_type"])
        if "procedure_stage_override" in data:
            c.procedure_stage_override = data["procedure_stage_override"]
    db.commit()
    return len(cases)


