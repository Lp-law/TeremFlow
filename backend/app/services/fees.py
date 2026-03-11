from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import FeeEventType
from app.models.fee_event import FeeEvent
from app.models.fee_stage_rate import FeeStageRate
from app.models.retainer import RetainerPayment
from app.services.deductible import q_ils


# All fee amounts are gross (including VAT, כולל מע"מ). 18% VAT applied to net base.
def compute_fee_amount(event_type: FeeEventType, *, quantity: int = 1, amount_override_ils_gross: Decimal | None = None) -> Decimal:
    if amount_override_ils_gross is not None:
        return q_ils(amount_override_ils_gross)
    if quantity < 1:
        raise ValueError("quantity must be >= 1")

    # Gross (כולל מע"מ) defaults; used when no FeeStageRate or single fee event.
    mapping: dict[FeeEventType, Decimal] = {
        FeeEventType.COURT_STAGE_1_DEFENSE: Decimal("23600.00"),   # 20000 + 18%
        FeeEventType.COURT_STAGE_2_DAMAGES: Decimal("17700.00"),
        FeeEventType.COURT_STAGE_3_EVIDENCE: Decimal("17700.00"),
        FeeEventType.COURT_STAGE_4_PROOFS: Decimal("17700.00"),
        FeeEventType.COURT_STAGE_5_SUMMARIES: Decimal("11800.00"),
        FeeEventType.AMENDED_DEFENSE_PARTIAL: Decimal("11800.00"),
        FeeEventType.AMENDED_DEFENSE_FULL: Decimal("23600.00"),
        FeeEventType.THIRD_PARTY_NOTICE: Decimal("11800.00"),
        FeeEventType.ADDITIONAL_PROOF_HEARING: Decimal("1770.00"),
        FeeEventType.DEMAND_FIX: Decimal("5900.00"),
        FeeEventType.DEMAND_HOURLY: Decimal("826.00"),
        FeeEventType.SMALL_CLAIMS_MANUAL: Decimal("0.00"),  # must override
        FeeEventType.APPEAL: Decimal("17700.00"),
        # STAGE_BILLING: amount comes from breakdown; do not use compute_fee_amount
    }
    if event_type == FeeEventType.STAGE_BILLING:
        raise ValueError("STAGE_BILLING amount must be set from breakdown; use stage-billing endpoint")
    base = mapping.get(event_type)
    if base is None:
        raise ValueError(f"Unknown fee event type: {event_type}")
    if event_type == FeeEventType.SMALL_CLAIMS_MANUAL:
        raise ValueError("SMALL_CLAIMS_MANUAL requires amount_override_ils_gross")
    if event_type in (FeeEventType.DEMAND_HOURLY, FeeEventType.ADDITIONAL_PROOF_HEARING):
        return q_ils(base * Decimal(quantity))
    return base


def apply_credit_to_amounts(amounts_ils_gross: list[Decimal], *, credit_ils_gross: Decimal) -> list[tuple[Decimal, Decimal]]:
    """
    Apply available credit to a chronological list of amounts.

    Returns list of (covered_by_credit, due_cash) per amount, in the same order.
    """
    credit = q_ils(credit_ils_gross)
    out: list[tuple[Decimal, Decimal]] = []
    for amt in amounts_ils_gross:
        total = q_ils(amt)
        covered = q_ils(min(credit, total))
        due = q_ils(total - covered)
        out.append((covered, due))
        credit = q_ils(credit - covered)
    return out


def _retainer_paid_total(db: Session, case_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(RetainerPayment.amount_ils_gross), 0))
        .filter(RetainerPayment.case_id == case_id)
        .scalar()
    )
    return q_ils(Decimal(str(total)))


def apply_retainer_credit(db: Session, *, case_id: int) -> None:
    paid_total = _retainer_paid_total(db, case_id)

    events = (
        db.query(FeeEvent)
        .filter(FeeEvent.case_id == case_id)
        .order_by(FeeEvent.event_date.asc(), FeeEvent.id.asc())
        .all()
    )

    allocations = apply_credit_to_amounts(
        [Decimal(str(e.computed_amount_ils_gross)) for e in events],
        credit_ils_gross=paid_total,
    )
    for e, (covered, due) in zip(events, allocations, strict=False):
        e.amount_covered_by_credit_ils_gross = covered
        e.amount_due_cash_ils_gross = due
    db.commit()


def add_fee_event(db: Session, *, case_id: int, payload) -> FeeEvent:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    amt = compute_fee_amount(payload.event_type, quantity=payload.quantity, amount_override_ils_gross=payload.amount_override_ils_gross)
    e = FeeEvent(
        case_id=case_id,
        event_type=payload.event_type,
        event_date=payload.event_date,
        quantity=payload.quantity,
        amount_override_ils_gross=payload.amount_override_ils_gross,
        computed_amount_ils_gross=amt,
        amount_covered_by_credit_ils_gross=Decimal("0.00"),
        amount_due_cash_ils_gross=amt,
    )
    db.add(e)
    db.commit()
    db.refresh(e)

    apply_retainer_credit(db, case_id=case_id)
    db.refresh(e)
    return e


def list_fee_events(db: Session, case_id: int, *, include_deleted: bool = False) -> list[FeeEvent]:
    q = db.query(FeeEvent).filter(FeeEvent.case_id == case_id)
    if not include_deleted:
        q = q.filter(FeeEvent.deleted_at.is_(None))
    return q.order_by(FeeEvent.event_date.desc(), FeeEvent.id.desc()).all()


def soft_delete_fee_event(db: Session, *, case_id: int, event_id: int, user_id: int, delete_reason: str) -> FeeEvent:
    """Soft delete: set deleted_at, deleted_by_user_id, delete_reason. Excluded from totals and list."""
    e = db.query(FeeEvent).filter(FeeEvent.id == event_id, FeeEvent.case_id == case_id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee event not found")
    if e.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fee event already deleted")
    e.deleted_at = datetime.now(timezone.utc)
    e.deleted_by_user_id = user_id
    e.delete_reason = (delete_reason or "").strip()[:500]
    db.commit()
    db.refresh(e)
    return e


def get_fee_stage_rates(db: Session) -> list[FeeStageRate]:
    return db.query(FeeStageRate).filter(FeeStageRate.is_active).order_by(FeeStageRate.code).all()


def get_billed_codes_for_case(db: Session, case_id: int) -> list[str]:
    """Codes already billed in any non-deleted STAGE_BILLING event."""
    events = (
        db.query(FeeEvent)
        .filter(
            FeeEvent.case_id == case_id,
            FeeEvent.event_type == FeeEventType.STAGE_BILLING,
            FeeEvent.deleted_at.is_(None),
        )
        .all()
    )
    seen: set[str] = set()
    for e in events:
        if not e.breakdown_json:
            continue
        # New format has new_codes; legacy has codes (the charged set)
        charged = e.breakdown_json.get("new_codes") or e.breakdown_json.get("codes") or []
        for c in charged:
            if c and c not in seen:
                seen.add(c)
    return sorted(seen)


def create_stage_billing_event(db: Session, *, case_id: int, payload, user_id: int) -> FeeEvent:
    """
    Cumulative stage billing: charge only for NEW codes (codes_selected - codes_already_billed).
    Create one FeeEvent with amount = delta_total (+ adjustment); store full breakdown.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    codes_selected = sorted(set(payload.codes))
    if not codes_selected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one code required")

    codes_already_billed = get_billed_codes_for_case(db, case_id)
    already_set = set(codes_already_billed)
    new_codes = sorted([c for c in codes_selected if c not in already_set])

    # Resolve rates for all selected (so we can show base_total_selected and delta_total)
    all_codes = sorted(set(codes_selected) | set(new_codes))
    rates_rows = db.query(FeeStageRate).filter(FeeStageRate.code.in_(all_codes), FeeStageRate.is_active).all()
    rates_map = {r.code: Decimal(str(r.amount_ils)) for r in rates_rows}
    missing = [c for c in codes_selected if c not in rates_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown or inactive rate for: {missing}")

    base_total_selected = q_ils(sum(rates_map[c] for c in codes_selected))
    delta_total = q_ils(sum(rates_map[c] for c in new_codes))

    confirm_zero = getattr(payload, "confirm_zero_new_codes", False)
    if not new_codes and not confirm_zero:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No new codes to bill",
        )

    # Adjustment (amount_ils only) applied to delta_total
    final_delta_total = delta_total
    adjustment_payload: dict | None = None
    if payload.adjustment is not None:
        adj = payload.adjustment
        adj_val = q_ils(adj.amount_ils)
        if adj.kind == "DISCOUNT":
            final_delta_total = q_ils(delta_total - adj_val)
            if final_delta_total < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Discount exceeds new charges",
                )
        else:
            final_delta_total = q_ils(delta_total + adj_val)
        adjustment_payload = {
            "kind": adj.kind,
            "amount_ils": str(adj.amount_ils),
            "reason": adj.reason,
        }

    breakdown = {
        "codes_selected": codes_selected,
        "codes_already_billed": codes_already_billed,
        "new_codes": new_codes,
        "rates": {c: str(rates_map[c]) for c in codes_selected},
        "base_total_selected": str(base_total_selected),
        "delta_total": str(delta_total),
        "adjustment": adjustment_payload,
        "final_delta_total": str(final_delta_total),
    }

    case.performed_fee_stage_codes = codes_selected
    e = FeeEvent(
        case_id=case_id,
        event_type=FeeEventType.STAGE_BILLING,
        event_date=payload.event_date,
        quantity=1,
        amount_override_ils_gross=None,
        computed_amount_ils_gross=final_delta_total,
        amount_covered_by_credit_ils_gross=Decimal("0.00"),
        amount_due_cash_ils_gross=final_delta_total,
        breakdown_json=breakdown,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    db.refresh(case)
    apply_retainer_credit(db, case_id=case_id)
    db.refresh(e)
    return e


