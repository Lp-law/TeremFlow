"""Deductible / excess summary for case."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class DeductibleSummaryOut(BaseModel):
    deductible_total_ils: Decimal = Decimal("0.00")
    deductible_consumed_ils: Decimal = Decimal("0.00")
    deductible_remaining_ils: Decimal = Decimal("0.00")
    excess_remaining_ils: Decimal | None = None
    notes: dict = {"deductible_consumed_only_by_client_deductible_expenses": True}
