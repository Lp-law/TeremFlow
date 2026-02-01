from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RetainerAccrual(Base):
    """
    Fixed monthly retainer accrual (945 ILS gross).

    Payments are tracked separately (cash basis) and then allocated to accruals oldest-first.
    """

    __tablename__ = "retainer_accruals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    accrual_month: Mapped[dt.date] = mapped_column(Date, index=True)  # first day of month
    invoice_date: Mapped[dt.date] = mapped_column(Date)
    due_date: Mapped[dt.date] = mapped_column(Date, index=True)

    amount_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="retainer_accruals")


class RetainerPayment(Base):
    __tablename__ = "retainer_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    payment_date: Mapped[dt.date] = mapped_column(Date, index=True)
    amount_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="retainer_payments")


