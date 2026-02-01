from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ExpenseCategory, ExpensePayer


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    supplier_name: Mapped[str] = mapped_column(String(120))
    amount_ils_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    service_description: Mapped[str] = mapped_column(Text)

    demand_received_date: Mapped[dt.date] = mapped_column(Date)
    expense_date: Mapped[dt.date] = mapped_column(Date, index=True)

    category: Mapped[ExpenseCategory] = mapped_column(Enum(ExpenseCategory), index=True)
    payer: Mapped[ExpensePayer] = mapped_column(Enum(ExpensePayer), index=True)

    attachment_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # Use a portable UUID type so local dev can run on SQLite without Postgres-specific types.
    split_group_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    is_split_part: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="expenses")


