"""Request body for POST /analytics/client-report."""
from __future__ import annotations

from pydantic import BaseModel


class ClientReportFilters(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str
    case_type: str | None = None  # COURT | DEMAND_LETTER | SMALL_CLAIMS
    status: str | None = None  # OPEN | CLOSED
    branch_name: str | None = None
    branch_is_null: bool | None = None  # True = filter to "ללא סניף"


class ClientReportBrand(BaseModel):
    logo_url: str | None = None


class ClientReportRequest(BaseModel):
    template_id: str = "T1"  # T1 | T2 | T3
    format: str = "pdf"  # pdf | docx
    filters: ClientReportFilters
    brand: ClientReportBrand | None = None
