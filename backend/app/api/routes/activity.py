"""Activity log API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.activity_log import ActivityLog
from app.models.user import User

router = APIRouter()

ACTION_LABELS = {
    "case_create": "יצירת תיק",
    "excel_import": "ייבוא מאקסל",
    "data_wipe": "מחיקת נתונים",
    "expense_add": "הוספת הוצאה",
    "fee_event_add": "הוספת שלב שכ״ט",
    "retainer_payment_add": "הוספת תשלום ריטיינר",
    "backup_export": "יצירת גיבוי",
    "login": "התחברות",
    "logout": "התנתקות",
}


@router.get("/latest")
def get_activity_latest(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    items = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    users_by_id = {}
    if items:
        user_ids = {a.user_id for a in items if a.user_id}
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            users_by_id = {u.id: u.username for u in users}
    return [
        {
            "id": a.id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "action": a.action,
            "action_label": ACTION_LABELS.get(a.action, a.action),
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "username": users_by_id.get(a.user_id) if a.user_id else None,
        }
        for a in items
    ]
