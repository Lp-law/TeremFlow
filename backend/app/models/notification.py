from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)

    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info|warning|danger

    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AlertEvent(Base):
    """
    Used to dedupe email alerts (e.g., insurer started paying should notify once).
    """

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)

    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), index=True)
    key: Mapped[str] = mapped_column(String(200), index=True)  # e.g. accrual:{id} / case:{id}
    last_sent_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


