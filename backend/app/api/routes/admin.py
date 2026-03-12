"""Admin endpoints for destructive operations and export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_auth
from app.api.routes.backups import build_backup_zip
from app.core.config import settings
from app.db.session import get_db
from app.models.case import Case
from app.models.notification import AlertEvent, Notification
from app.models.user import User
from app.schemas.case import CaseOut
from app.services import cases as case_service

router = APIRouter()


class CaseIdentityUpdate(BaseModel):
    """Admin-only: update case_reference and/or case_name."""
    case_reference: str | None = None
    case_name: str | None = None


@router.patch("/cases/{case_id}/identity", response_model=CaseOut)
def update_case_identity(
    case_id: int,
    payload: CaseIdentityUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Update case_reference and/or case_name. Prevents duplicate case_reference."""
    updates = payload.model_dump(exclude_unset=True)
    c = case_service.update_case_identity(
        db,
        case_id=case_id,
        case_reference=updates.get("case_reference"),
        case_name=updates.get("case_name") if "case_name" in updates else None,
    )
    stages = case_service.get_latest_fee_stage_by_case_ids(db, [c.id])
    return CaseOut(**case_service.to_case_out(db, c, current_procedure_stage=stages.get(c.id)))


@router.post("/wipe-case-data")
def wipe_case_data(
    db: Session = Depends(get_db),
    user=Depends(require_admin),
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

    from app.services.activity_log import log_activity
    log_activity(db, action="data_wipe", entity_type="admin", user_id=user.id, details={"cases": deleted_cases, "alerts": deleted_alerts, "notifications": deleted_notifications})

    return {
        "ok": True,
        "deleted": {
            "cases": deleted_cases,
            "alert_events": deleted_alerts,
            "notifications": deleted_notifications,
        },
    }


@router.get("/wipe-case-data-status")
def wipe_case_data_status(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Returns counts of case-related rows. Use to verify DB is clean (all zeros)."""
    case_count = db.query(Case).count()
    return {
        "cases": case_count,
        "clean": case_count == 0,
    }


@router.get("/export-backup")
def admin_export_backup(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """GET backup (same content as POST /backups/export). Auth required. Returns ZIP with all tables as CSV."""
    data, filename, rec = build_backup_zip(db, user)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Backup-Id": str(rec.id),
        "X-Backup-Sha256": rec.sha256,
    }
    return Response(content=data, media_type="application/zip", headers=headers)
