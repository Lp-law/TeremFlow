from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import FeeEventType


class FeeEvent(Base):
    __tablename__ = "fee_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    event_type: Mapped[FeeEventType] = mapped_column(Enum(FeeEventType), index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount_override_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)

    computed_amount_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    # Applied retainer credit
    amount_covered_by_credit_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    amount_due_cash_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="fee_events")


