from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Response
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, require_auth
from app.core.config import settings
from app.core.security import create_access_token, create_csrf_token
from app.db.session import get_db
from app.models.backup import BackupRecord
from app.models.user import User
from app.schemas.auth import LoginRequest, UserOut
from app.services.users import authenticate_user

router = APIRouter()


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    token = create_access_token(subject=str(user.id))
    csrf = create_csrf_token()
    # SameSite=None so cookie is sent on cross-origin requests (frontend.onrender.com -> api.onrender.com).
    samesite = "none" if settings.environment == "production" else "lax"
    response.set_cookie(
        settings.jwt_cookie_name,
        token,
        httponly=True,
        secure=settings.environment == "production",
        samesite=samesite,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )
    # CSRF token cookie (readable by JS, must be echoed in X-CSRF-Token header for unsafe methods in production).
    response.set_cookie(
        "teremflow_csrf",
        csrf,
        httponly=False,
        secure=settings.environment == "production",
        samesite=samesite,
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )
    return UserOut(id=user.id, username=user.username, role=str(user.role))


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    backup_id: str | None = Header(None, alias="X-Backup-Id"),
):
    # If the request is authenticated, enforce "backup required before logout".
    if user is not None:
        if not backup_id:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="לפני התנתקות חובה לבצע גיבוי (Backup).",
            )
        try:
            bid = int(backup_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="Backup ID לא תקין.")

        rec = db.query(BackupRecord).filter(BackupRecord.id == bid, BackupRecord.created_by_user_id == user.id).first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="לא נמצא גיבוי מתאים למשתמש. יש לבצע גיבוי מחדש לפני התנתקות.",
            )

        # Require this backup to be fresh (avoids reusing an old backup forever).
        created_at = rec.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=dt.timezone.utc)
        if created_at < dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30):
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="הגיבוי ישן מדי. לפני התנתקות חובה לבצע גיבוי מחדש.",
            )

    response.delete_cookie(settings.jwt_cookie_name, path="/")
    response.delete_cookie("teremflow_csrf", path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user=Depends(require_auth)):
    return UserOut(id=user.id, username=user.username, role=str(user.role))


