from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (
    ClaimsCategory,
    ClaimsFinalOutcomeType,
    ClaimsReportCaseStatus,
    ClaimsReportStatus,
    ClaimsRowLinkageType,
)


class ClaimsReport(Base):
    __tablename__ = "claims_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_name: Mapped[str] = mapped_column(String(160), default="טרם")
    institution_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(220))
    report_cutoff_date: Mapped[dt.date] = mapped_column(Date, index=True)
    updated_to_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True, index=True)
    recommended_reserve_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    intro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    closing_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ClaimsReportStatus] = mapped_column(Enum(ClaimsReportStatus), default=ClaimsReportStatus.DRAFT, index=True)
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    finalized_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    rows = relationship("ClaimsReportRow", back_populates="report", cascade="all, delete-orphan")


class ClaimsReportRow(Base):
    __tablename__ = "claims_report_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("claims_reports.id", ondelete="CASCADE"), index=True)
    linked_case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    linkage_type: Mapped[ClaimsRowLinkageType] = mapped_column(Enum(ClaimsRowLinkageType), default=ClaimsRowLinkageType.MANUAL, index=True)

    case_reference_text: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    case_title: Mapped[str | None] = mapped_column(String(220), nullable=True)
    court_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    proceeding_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    institution_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category_for_report: Mapped[ClaimsCategory] = mapped_column(Enum(ClaimsCategory), default=ClaimsCategory.OTHER, index=True)

    report_case_status: Mapped[ClaimsReportCaseStatus] = mapped_column(
        Enum(ClaimsReportCaseStatus), default=ClaimsReportCaseStatus.OPEN, index=True
    )
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    current_risk_assessment_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    risk_assessment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_assessment_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_assessment_updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    final_outcome_type: Mapped[ClaimsFinalOutcomeType | None] = mapped_column(Enum(ClaimsFinalOutcomeType), nullable=True, index=True)
    final_outcome_amount_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    awarded_costs_to_terem_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    final_outcome_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    final_outcome_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    deductible_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    deductible_ils_gross: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount_already_paid_on_deductible_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    remaining_deductible_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    expenses_total_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    fees_total_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    retainer_charged_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    exposure_for_reserve_ils: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    narrative_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    include_in_report: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    report = relationship("ClaimsReport", back_populates="rows")
