from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.jwt_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user = db.query(User).filter(User.id == int(payload.sub)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_auth(user: User = Depends(get_current_user)) -> User:
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """
    Best-effort auth: returns User if cookie is present & valid, otherwise None.
    Useful for endpoints like logout that should be idempotent but may want to apply extra rules when authenticated.
    """
    token = request.cookies.get(settings.jwt_cookie_name)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    user = db.query(User).filter(User.id == int(payload.sub)).first()
    if not user or not user.is_active:
        return None
    return user


