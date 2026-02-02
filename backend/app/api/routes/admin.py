"""Admin endpoints for destructive operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.core.config import settings
from app.db.session import get_db
from app.models.case import Case
from app.models.notification import AlertEvent, Notification

router = APIRouter()


@router.post("/wipe-case-data")
def wipe_case_data(
    db: Session = Depends(get_db),
    user=Depends(require_auth),
    x_wipe_token: str | None = Header(default=None),
):
    """
    Delete ALL case-related data. Users and permissions are NOT deleted.
    Requires auth + X-Wipe-Token header matching WIPE_CASE_DATA_SECRET.
    """
    secret = settings.wipe_case_data_secret
    if x_wipe_token != secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid wipe token")

    # Order matters: children first due to FK, then cases.
    # Notification has SET NULL on case delete; we delete them for clean slate.
    deleted_notifications = db.query(Notification).delete()
    deleted_alerts = db.query(AlertEvent).delete()
    deleted_cases = db.query(Case).delete()

    db.commit()

    return {
        "ok": True,
        "deleted": {
            "cases": deleted_cases,
            "alert_events": deleted_alerts,
            "notifications": deleted_notifications,
        },
    }


@router.get("/wipe-case-data-status")
def wipe_case_data_status(db: Session = Depends(get_db), _=Depends(require_auth)):
    """Returns counts of case-related rows. Use to verify DB is clean (all zeros)."""
    case_count = db.query(Case).count()
    return {
        "cases": case_count,
        "clean": case_count == 0,
    }
