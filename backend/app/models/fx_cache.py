from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FxRateCache(Base):
    __tablename__ = "fx_rate_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rate_date: Mapped[dt.date] = mapped_column(Date, unique=True, index=True)
    rate_usd_ils: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    source: Mapped[str] = mapped_column(String(32), default="BOI")  # BOI | IMPORTED | MANUAL

    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


