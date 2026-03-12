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


@router.get("/version")
def get_version(
    _=Depends(require_auth),
    db: Session = Depends(get_db),
):
    """
    Build/version fingerprint. Requires auth. Response must not be cached.
    """
    git_sha = (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GIT_SHA")
        or "unknown"
    )
    build_time = os.environ.get("BUILD_TIME_UTC") or BUILD_TIME_UTC or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    environment = os.environ.get("ENVIRONMENT", "development")

    db_revision = "unknown"
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        if row:
            db_revision = str(row[0])
    except Exception:
        pass

    payload = {
        "git_sha": git_sha,
        "build_time_utc": build_time,
        "environment": environment,
        "db_revision": db_revision,
        "service": "teremflow-api",
    }
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
