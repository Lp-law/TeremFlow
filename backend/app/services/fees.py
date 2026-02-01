from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import FeeEventType
from app.models.fee_event import FeeEvent
from app.models.retainer import RetainerPayment
from app.services.deductible import q_ils


def compute_fee_amount(event_type: FeeEventType, *, quantity: int = 1, amount_override_ils_gross: Decimal | None = None) -> Decimal:
    if amount_override_ils_gross is not None:
        return q_ils(amount_override_ils_gross)
    if quantity < 1:
        raise ValueError("quantity must be >= 1")

    mapping: dict[FeeEventType, Decimal] = {
        FeeEventType.COURT_STAGE_1_DEFENSE: Decimal("20000.00"),
        FeeEventType.COURT_STAGE_2_DAMAGES: Decimal("15000.00"),
        FeeEventType.COURT_STAGE_3_EVIDENCE: Decimal("15000.00"),
        FeeEventType.COURT_STAGE_4_PROOFS: Decimal("15000.00"),
        FeeEventType.COURT_STAGE_5_SUMMARIES: Decimal("10000.00"),
        FeeEventType.AMENDED_DEFENSE_PARTIAL: Decimal("10000.00"),
        FeeEventType.AMENDED_DEFENSE_FULL: Decimal("20000.00"),
        FeeEventType.THIRD_PARTY_NOTICE: Decimal("10000.00"),
        FeeEventType.ADDITIONAL_PROOF_HEARING: Decimal("1500.00"),
        FeeEventType.DEMAND_FIX: Decimal("5000.00"),
        FeeEventType.DEMAND_HOURLY: Decimal("700.00"),
        FeeEventType.SMALL_CLAIMS_MANUAL: Decimal("0.00"),  # must override
    }
    base = mapping[event_type]
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


def list_fee_events(db: Session, case_id: int) -> list[FeeEvent]:
    return db.query(FeeEvent).filter(FeeEvent.case_id == case_id).order_by(FeeEvent.event_date.desc(), FeeEvent.id.desc()).all()


