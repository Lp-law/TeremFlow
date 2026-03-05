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
    """Branding for client report. logo_base64 preferred (no external URL fetch = no SSRF)."""
    logo_base64: str | None = None  # data URL or raw base64 image
    primary_hex: str = "#1F4E79"
    accent_hex: str = "#2E75B6"
    header_bg_hex: str | None = None  # default: primary_hex
    header_text_hex: str = "#FFFFFF"


class ClientReportRequest(BaseModel):
    template_id: str = "T1"  # T1 | T2 | T3
    format: str = "pdf"  # pdf | docx
    filters: ClientReportFilters
    brand: ClientReportBrand | None = None
