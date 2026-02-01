from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter()

def _to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        case_id=n.case_id,
        type=n.type,
        title=n.title,
        message=n.message,
        severity=n.severity,
        is_read=n.is_read,
        created_at=n.created_at,
    )


@router.get("/", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), _=Depends(require_auth)):
    items = db.query(Notification).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(200).all()
    return [_to_out(n) for n in items]


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), _=Depends(require_auth)):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    n.is_read = True
    db.commit()
    return {"ok": True}


