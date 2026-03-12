"""Build/version fingerprint for deploy verification. Read-only."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db

router = APIRouter()

# Set at app startup (main.py)
BUILD_TIME_UTC: str = ""


def set_build_time_utc(value: str) -> None:
    global BUILD_TIME_UTC
    BUILD_TIME_UTC = value


_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


def _version_payload(include_db_revision: bool, db: Session | None = None) -> dict:
    git_sha = (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GIT_SHA")
        or "unknown"
    )
    build_time = os.environ.get("BUILD_TIME_UTC") or BUILD_TIME_UTC or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    environment = os.environ.get("ENVIRONMENT", "development")
    payload = {
        "git_sha": git_sha,
        "build_time_utc": build_time,
        "environment": environment,
        "service": "teremflow-api",
    }
    if include_db_revision and db is not None:
        db_revision = "unknown"
        try:
            row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            if row:
                db_revision = str(row[0])
        except Exception:
            pass
        payload["db_revision"] = db_revision
    return payload


@router.get("/version")
def get_version_public():
    """
    Public build fingerprint (no auth). For UI deploy verification.
    """
    return JSONResponse(
        content=_version_payload(include_db_revision=False),
        headers=_NO_CACHE_HEADERS,
    )


@router.get("/version/private")
def get_version_private(
    _=Depends(require_auth),
    db: Session = Depends(get_db),
):
    """
    Full fingerprint including db_revision. Requires auth.
    """
    return JSONResponse(
        content=_version_payload(include_db_revision=True, db=db),
        headers=_NO_CACHE_HEADERS,
    )
