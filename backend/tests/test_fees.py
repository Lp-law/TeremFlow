from decimal import Decimal

import pytest

from app.models.enums import FeeEventType
from app.services.fees import apply_credit_to_amounts, compute_fee_amount


def test_compute_fee_amount_court_stage():
    assert compute_fee_amount(FeeEventType.COURT_STAGE_1_DEFENSE) == Decimal("20000.00")


def test_compute_fee_amount_hourly_quantity():
    assert compute_fee_amount(FeeEventType.DEMAND_HOURLY, quantity=3) == Decimal("2100.00")


def test_small_claims_requires_override():
    with pytest.raises(ValueError):
        compute_fee_amount(FeeEventType.SMALL_CLAIMS_MANUAL)


def test_apply_credit_chronological():
    # credit covers first amount fully and partially covers second
    allocations = apply_credit_to_amounts([Decimal("100.00"), Decimal("80.00")], credit_ils_gross=Decimal("150.00"))
    assert allocations == [(Decimal("100.00"), Decimal("0.00")), (Decimal("50.00"), Decimal("30.00"))]


