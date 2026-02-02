from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import CaseStatus, CaseType


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    case_reference: Mapped[str] = mapped_column(String(120), index=True)  # e.g. internal ref / patient / claim no
    case_type: Mapped[CaseType] = mapped_column(Enum(CaseType), index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.OPEN, index=True)

    open_date: Mapped[dt.date] = mapped_column(Date, index=True)
    retainer_anchor_date: Mapped[dt.date] = mapped_column(Date, index=True)  # July same year or Jan next year
    branch_name: Mapped[str | None] = mapped_column(String(120), nullable=True)  # Excel column B

    # Deductible/excess (gross in ILS; stored as computed at open)
    deductible_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    fx_rate_usd_ils: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=True)
    fx_date_used: Mapped[dt.date] = mapped_column(Date, nullable=True)
    fx_source: Mapped[str] = mapped_column(String(32), default="BOI")  # BOI | IMPORTED | MANUAL

    deductible_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    insurer_started: Mapped[bool] = mapped_column(Boolean, default=False)
    insurer_start_date: Mapped[dt.date] = mapped_column(Date, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    expenses = relationship("Expense", back_populates="case", cascade="all, delete-orphan")
    retainer_accruals = relationship("RetainerAccrual", back_populates="case", cascade="all, delete-orphan")
    retainer_payments = relationship("RetainerPayment", back_populates="case", cascade="all, delete-orphan")
    fee_events = relationship("FeeEvent", back_populates="case", cascade="all, delete-orphan")


