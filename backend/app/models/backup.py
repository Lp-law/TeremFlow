from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BackupRecord(Base):
    """
    A lightweight audit record for "export backup" actions.
    The actual ZIP is returned to the client for safekeeping (we don't persist it server-side).
    """

    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    created_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by = relationship("User")

    file_name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)

    tables_count: Mapped[int] = mapped_column(Integer, default=0)
    rows_total: Mapped[int] = mapped_column(Integer, default=0)


