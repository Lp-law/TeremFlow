from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.services.import_excel import import_cases_from_excel

router = APIRouter()


@router.post("/excel")
def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db), _=Depends(require_auth)):
    data = file.file.read()
    return import_cases_from_excel(db, data)


