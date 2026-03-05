"""Deductible / excess summary for case (unified model)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class DeductibleSummaryOut(BaseModel):
    """Unified deductible/excess summary; all values respect manual overrides."""
    excess_total_ils: Decimal = Decimal("0.00")
    retainer_charged_to_date_ils: Decimal = Decimal("0.00")
    expenses_total_ils: Decimal = Decimal("0.00")
    fees_by_stages_ils: Decimal = Decimal("0.00")
    excess_remaining_ils: Decimal = Decimal("0.00")
    fee_diff_ils: Decimal = Decimal("0.00")
    manual_overrides: dict[str, Any] = {}
