from decimal import Decimal

from app.services.deductible import deductible_remaining, split_amount_over_deductible


def test_deductible_remaining_never_negative():
    assert deductible_remaining(deductible_ils_gross=Decimal("100.00"), consumed_on_deductible_ils_gross=Decimal("150.00")) == Decimal(
        "0.00"
    )


def test_split_amount_within_deductible():
    on_deductible, on_insurer = split_amount_over_deductible(amount_ils_gross=Decimal("100.00"), remaining_ils_gross=Decimal("200.00"))
    assert on_deductible == Decimal("100.00")
    assert on_insurer == Decimal("0.00")


def test_split_amount_crosses_deductible():
    on_deductible, on_insurer = split_amount_over_deductible(amount_ils_gross=Decimal("250.00"), remaining_ils_gross=Decimal("200.00"))
    assert on_deductible == Decimal("200.00")
    assert on_insurer == Decimal("50.00")


