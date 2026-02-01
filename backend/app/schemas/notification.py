from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    id: int
    case_id: int | None
    type: NotificationType
    title: str
    message: str
    severity: str
    is_read: bool
    created_at: dt.datetime


