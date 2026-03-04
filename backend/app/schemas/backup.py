from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class BackupLastOut(BaseModel):
    id: int
    created_at: dt.datetime
    created_by_username: str
    file_name: str
    size_bytes: int


class MyLastBackupOut(BaseModel):
    """Last backup by current user; for logout policy (allow logout if within backup_fresh_hours)."""
    last_backup_at: str | None  # ISO datetime
    last_backup_id: int | None
    fresh_hours: int = 24  # from settings.backup_fresh_hours; frontend uses this for "recent" check


