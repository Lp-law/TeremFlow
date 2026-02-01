from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import secrets

import bcrypt
from jose import jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    # Local app accounts: allow 7+ characters (e.g. "lior123").
    if not plain or len(plain) < 7:
        raise ValueError("Password too short")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_csrf_token() -> str:
    # URL-safe random token suitable for cookie/header use.
    return secrets.token_urlsafe(32)


def constant_time_equals(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    try:
        return secrets.compare_digest(a, b)
    except Exception:
        return False


@dataclass(frozen=True)
class JwtPayload:
    sub: str
    exp: int


def create_access_token(*, subject: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> JwtPayload:
    data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return JwtPayload(sub=str(data["sub"]), exp=int(data["exp"]))


