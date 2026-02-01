from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


