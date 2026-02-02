"""Activity logging for operational visibility."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


def log_activity(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    details: dict | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
