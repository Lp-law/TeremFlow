from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class BackupLastOut(BaseModel):
    id: int
    created_at: dt.datetime
    created_by_username: str
    file_name: str
    size_bytes: int


