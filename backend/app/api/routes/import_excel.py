from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.services.import_excel import import_cases_from_excel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/excel")
def import_excel(
    file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_auth)
):
    try:
        data = file.file.read()
        result = import_cases_from_excel(db, data)
        from app.services.activity_log import log_activity
        log_activity(db, action="excel_import", entity_type="import", user_id=user.id, details={"created": result["created"], "error_count": result["error_count"]})
        return result
    except Exception as e:
        logger.exception("Import Excel failed: %s", e)
        raise


