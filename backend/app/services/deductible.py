from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def q_ils(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def deductible_remaining(*, deductible_ils_gross: Decimal, consumed_on_deductible_ils_gross: Decimal) -> Decimal:
    remaining = q_ils(deductible_ils_gross - consumed_on_deductible_ils_gross)
    if remaining < 0:
        return Decimal("0.00")
    return remaining


def split_amount_over_deductible(*, amount_ils_gross: Decimal, remaining_ils_gross: Decimal) -> tuple[Decimal, Decimal]:
    """
    Returns (part_on_deductible, part_on_insurer).
    """
    amt = q_ils(amount_ils_gross)
    rem = q_ils(remaining_ils_gross)
    if amt <= 0:
        raise ValueError("Amount must be positive")
    if rem <= 0:
        return Decimal("0.00"), amt
    if amt <= rem:
        return amt, Decimal("0.00")
    return rem, q_ils(amt - rem)


