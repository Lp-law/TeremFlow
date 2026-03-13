from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import CaseStatus, CaseType


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    case_reference: Mapped[str] = mapped_column(String(120), index=True)  # e.g. internal ref / patient / claim no
    case_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # plaintiff / display name (Excel import)
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

    # Historical retainer from import (Excel H). If set, counts against excess. Null for new cases.
    retainer_snapshot_ils_gross: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Last month (YYYY-MM-01) included in retainer snapshot. If set, accruals start from next month.
    retainer_snapshot_through_month: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # Historical non-attorney expenses from import (Excel I). If set (with H), snapshot mode.
    expenses_snapshot_ils_gross: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Historical fee stages from import (Excel historical_fee_stages). List of FeeEventType codes. Read-only.
    historical_fee_stages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Legacy free-text from Excel (e.g. "פירוט חיוב שכ״ט עו״ד"). Read-only.
    legacy_fee_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last selected performed stage codes (for "Create fee event from performed stages"). Updated on submit.
    performed_fee_stage_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Raw Excel columns not mapped to operational fields (display-only; not used in calculations).
    raw_import_fields_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Manual procedure stage override (display only; does not affect fee events). One of FeeEventType code or null.
    procedure_stage_override: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    # Soft delete
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Retainer freeze: when true, charged months and accruals stop at retainer_frozen_at
    retainer_is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    retainer_frozen_at: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # Retainer end date: stop charging after this date (inclusive of month); alias for current period end
    retainer_end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # Two periods: current (ongoing) + legacy (past). Ledger = source of truth for theoretical total.
    retainer_current_start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    retainer_current_end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    retainer_legacy_start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    retainer_legacy_end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    # Free-text case notes (user-editable)
    case_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Single editable expenses total (replaces itemized UX for normal use)
    expenses_total_ils_gross: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Manual overrides for deductible/overview (keys: excess_total_ils_override, retainer_charged_override, etc.)
    manual_overrides_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    expenses = relationship("Expense", back_populates="case", cascade="all, delete-orphan")
    retainer_accruals = relationship("RetainerAccrual", back_populates="case", cascade="all, delete-orphan")
    retainer_payments = relationship("RetainerPayment", back_populates="case", cascade="all, delete-orphan")
    fee_events = relationship("FeeEvent", back_populates="case", cascade="all, delete-orphan")


