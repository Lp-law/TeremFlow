"""Data quality warnings for a case (read-only; no formula or data changes)."""

from __future__ import annotations

from pydantic import BaseModel


class CaseWarningOut(BaseModel):
    code: str
    severity: str  # "info" | "warn" | "error"
    title: str
    details: str
    action_tab: str | None = None  # e.g. "retainer", "expenses", "deductible", "fees", "overview"


class CaseWarningsOut(BaseModel):
    warnings: list[CaseWarningOut]
