from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.case import Case
from app.models.enums import CaseStatus, NotificationType
from app.models.notification import AlertEvent, Notification
from app.models.retainer import RetainerAccrual
from app.services.deductible import q_ils
from app.services.email import send_email
from app.services.expenses import get_case_excess_remaining


def _has_alert(db: Session, *, type_: NotificationType, key: str) -> bool:
    return db.query(AlertEvent).filter(AlertEvent.type == type_, AlertEvent.key == key).first() is not None


def _mark_alert(db: Session, *, type_: NotificationType, key: str, case_id: int | None = None) -> None:
    db.add(AlertEvent(type=type_, key=key, case_id=case_id))
    db.commit()


def _create_notification(db: Session, *, type_: NotificationType, title: str, message: str, severity: str, case_id: int | None) -> None:
    db.add(Notification(type=type_, title=title, message=message, severity=severity, case_id=case_id))
    db.commit()


def run_daily_alerts(db: Session) -> dict:
    today = dt.date.today()
    due_soon_until = today + dt.timedelta(days=7)

    sent = 0

    # Insurer started paying (once per case)
    insurer_cases = (
        db.query(Case)
        .filter(Case.status == CaseStatus.OPEN, Case.insurer_started.is_(True), Case.insurer_start_date.isnot(None))
        .all()
    )
    for c in insurer_cases:
        key = f"case:{c.id}:insurer_started"
        if _has_alert(db, type_=NotificationType.INSURER_STARTED_PAYING, key=key):
            continue
        title = "המבטח התחיל לשלם"
        msg = f"בתיק '{c.case_reference}' המבטח התחיל לשלם החל מתאריך {c.insurer_start_date}."
        _create_notification(db, type_=NotificationType.INSURER_STARTED_PAYING, title=title, message=msg, severity="info", case_id=c.id)
        send_email(subject=title, body=msg, recipients=settings.alert_email_recipients)
        _mark_alert(db, type_=NotificationType.INSURER_STARTED_PAYING, key=key, case_id=c.id)
        sent += 1

    # Excess near exhaustion (once per case) — Excel P = M - J
    open_cases = db.query(Case).filter(Case.status == CaseStatus.OPEN).all()
    for c in open_cases:
        remaining = get_case_excess_remaining(db, c)
        pct_threshold = q_ils(Decimal(str(c.deductible_ils_gross)) * Decimal(str(settings.deductible_near_pct)))
        abs_threshold = q_ils(Decimal(str(settings.deductible_near_abs_ils)))
        is_near = remaining < pct_threshold or remaining < abs_threshold
        if not is_near:
            continue
        key = f"case:{c.id}:deductible_near"
        if _has_alert(db, type_=NotificationType.DEDUCTIBLE_NEAR_EXHAUSTION, key=key):
            continue
        title = "השתתפות עצמית קרובה לסיום"
        msg = f"בתיק '{c.case_reference}' נותרו {remaining} ₪ (כולל מע\"מ) מתוך {c.deductible_ils_gross} ₪."
        _create_notification(db, type_=NotificationType.DEDUCTIBLE_NEAR_EXHAUSTION, title=title, message=msg, severity="warning", case_id=c.id)
        send_email(subject=title, body=msg, recipients=settings.alert_email_recipients)
        _mark_alert(db, type_=NotificationType.DEDUCTIBLE_NEAR_EXHAUSTION, key=key, case_id=c.id)
        sent += 1

    # Retainer due soon / overdue: per accrual
    accruals = db.query(RetainerAccrual).filter(RetainerAccrual.is_paid.is_(False)).all()
    for a in accruals:
        if today <= a.due_date <= due_soon_until:
            key = f"accrual:{a.id}:due_soon"
            if not _has_alert(db, type_=NotificationType.RETAINER_DUE_SOON, key=key):
                title = "תשלום ריטיינר מתקרב"
                msg = f"ריטיינר לחודש {a.accrual_month:%Y-%m} צפוי לתשלום עד {a.due_date} (נטו 60)."
                _create_notification(db, type_=NotificationType.RETAINER_DUE_SOON, title=title, message=msg, severity="info", case_id=a.case_id)
                send_email(subject=title, body=msg, recipients=settings.alert_email_recipients)
                _mark_alert(db, type_=NotificationType.RETAINER_DUE_SOON, key=key, case_id=a.case_id)
                sent += 1
        if a.due_date < today:
            key = f"accrual:{a.id}:overdue"
            if not _has_alert(db, type_=NotificationType.RETAINER_OVERDUE, key=key):
                title = "תשלום ריטיינר באיחור"
                msg = f"ריטיינר לחודש {a.accrual_month:%Y-%m} היה אמור להיות משולם עד {a.due_date} (נטו 60)."
                _create_notification(db, type_=NotificationType.RETAINER_OVERDUE, title=title, message=msg, severity="danger", case_id=a.case_id)
                send_email(subject=title, body=msg, recipients=settings.alert_email_recipients)
                _mark_alert(db, type_=NotificationType.RETAINER_OVERDUE, key=key, case_id=a.case_id)
                sent += 1

    return {"ok": True, "sent": sent}


