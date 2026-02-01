from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.alerts import run_daily_alerts

router = APIRouter()


@router.post("/daily")
def daily_tasks(
    db: Session = Depends(get_db),
    x_tasks_token: str | None = Header(default=None),
):
    if x_tasks_token != settings.tasks_daily_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tasks token")
    return run_daily_alerts(db)


