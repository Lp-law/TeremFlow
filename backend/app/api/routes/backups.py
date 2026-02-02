from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import Base, get_db
from app.models.backup import BackupRecord
from app.models.user import User
from app.schemas.backup import BackupLastOut

# Ensure all models are imported so Base.metadata includes all tables.
import app.models  # noqa: F401

router = APIRouter()


def _as_cell_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    # Decimal, UUID, enums, etc.
    return str(v)


@router.post("/export")
def export_backup(user: User = Depends(require_auth), db: Session = Depends(get_db)) -> Response:
    """
    Exports a ZIP with one CSV per DB table (Excel-friendly).
    The ZIP is NOT stored server-side; we only store a BackupRecord (who/when/hash).
    """
    now = dt.datetime.now(dt.timezone.utc)
    safe_username = "".join(ch for ch in user.username if ch.isalnum() or ch in ("-", "_")) or "user"
    filename = f"teremflow-backup-{now:%Y%m%d-%H%M%S}-{safe_username}.zip"

    manifest: dict[str, Any] = {
        "app": "TeremFlow",
        "created_at": now.isoformat(),
        "created_by": {"id": user.id, "username": user.username},
        "format": "zip+csv",
        "tables": [],
    }

    out = io.BytesIO()
    tables_count = 0
    rows_total = 0

    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for table in Base.metadata.sorted_tables:
            cols = [c.name for c in table.columns]
            res = db.execute(select(table)).mappings().all()
            row_count = len(res)

            csv_buf = io.StringIO()
            w = csv.writer(csv_buf, lineterminator="\n")
            w.writerow(cols)
            for row in res:
                w.writerow([_as_cell_value(row.get(c)) for c in cols])

            zf.writestr(f"tables/{table.name}.csv", csv_buf.getvalue().encode("utf-8-sig"))

            manifest["tables"].append(
                {
                    "name": table.name,
                    "row_count": row_count,
                    "columns": cols,
                }
            )
            tables_count += 1
            rows_total += row_count

        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))

    data = out.getvalue()
    sha256 = hashlib.sha256(data).hexdigest()

    rec = BackupRecord(
        created_by_user_id=user.id,
        file_name=filename,
        sha256=sha256,
        size_bytes=len(data),
        tables_count=tables_count,
        rows_total=rows_total,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    from app.services.activity_log import log_activity
    log_activity(db, action="backup_export", entity_type="backup", entity_id=rec.id, user_id=user.id, details={"file_name": filename, "size_bytes": len(data)})

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Backup-Id": str(rec.id),
        "X-Backup-Sha256": sha256,
    }
    return Response(content=data, media_type="application/zip", headers=headers)


@router.get("/last", response_model=BackupLastOut)
def last_backup(db: Session = Depends(get_db), user: User = Depends(require_auth)) -> BackupLastOut:
    rec = db.query(BackupRecord).order_by(BackupRecord.id.desc()).first()
    if not rec:
        # Keep API simple for UI (no 404 handling). "id=0" means none.
        return BackupLastOut(
            id=0,
            created_at=dt.datetime.fromtimestamp(0, tz=dt.timezone.utc),
            created_by_username="",
            file_name="",
            size_bytes=0,
        )
    created_by = db.query(User).filter(User.id == rec.created_by_user_id).first()
    return BackupLastOut(
        id=rec.id,
        created_at=rec.created_at,
        created_by_username=created_by.username if created_by else "",
        file_name=rec.file_name,
        size_bytes=rec.size_bytes,
    )


