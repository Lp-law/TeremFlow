from datetime import date
from decimal import Decimal

import pytest

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, FeeEventType
from app.services.fees import add_fee_event, apply_credit_to_amounts, compute_fee_amount


def test_compute_fee_amount_court_stage():
    # Gross (כולל מע"מ): Stage 1 is 23,600 not 20,000
    assert compute_fee_amount(FeeEventType.COURT_STAGE_1_DEFENSE) == Decimal("23600.00")


def test_add_fee_event_stage1_stores_gross(db):
    """Single fee event for COURT_STAGE_1_DEFENSE must store 23,600 (gross), not 20,000."""
    c = Case(
        case_reference="F-1",
        case_name="Fee test",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=date(2024, 1, 1),
        retainer_anchor_date=date(2024, 7, 1),
        deductible_ils_gross=Decimal("5000.00"),
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    class Payload:
        event_type = FeeEventType.COURT_STAGE_1_DEFENSE
        event_date = date(2024, 6, 1)
        quantity = 1
        amount_override_ils_gross = None

    e = add_fee_event(db, case_id=c.id, payload=Payload())
    assert e.computed_amount_ils_gross == Decimal("23600.00")


def test_compute_fee_amount_hourly_quantity():
    # Gross: 826 * 3
    assert compute_fee_amount(FeeEventType.DEMAND_HOURLY, quantity=3) == Decimal("2478.00")


def test_compute_fee_amount_appeal():
    assert compute_fee_amount(FeeEventType.APPEAL) == Decimal("17700.00")


def test_compute_fee_amount_stage_billing_raises():
    with pytest.raises(ValueError, match="STAGE_BILLING"):
        compute_fee_amount(FeeEventType.STAGE_BILLING)


def test_small_claims_requires_override():
    with pytest.raises(ValueError):
        compute_fee_amount(FeeEventType.SMALL_CLAIMS_MANUAL)


def test_apply_credit_chronological():
    # credit covers first amount fully and partially covers second
    allocations = apply_credit_to_amounts([Decimal("100.00"), Decimal("80.00")], credit_ils_gross=Decimal("150.00"))
    assert allocations == [(Decimal("100.00"), Decimal("0.00")), (Decimal("50.00"), Decimal("30.00"))]


