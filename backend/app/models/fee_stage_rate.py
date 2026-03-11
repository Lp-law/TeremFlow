"""Configurable rate per fee stage code (used for stage-billing modal). All amounts are gross (כולל מע\"מ)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FeeStageRate(Base):
    __tablename__ = "fee_stage_rates"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount_ils: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # Gross ILS (including VAT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
