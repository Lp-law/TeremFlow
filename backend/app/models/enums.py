from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class CaseType(str, enum.Enum):
    COURT = "COURT"
    DEMAND_LETTER = "DEMAND_LETTER"
    SMALL_CLAIMS = "SMALL_CLAIMS"


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ExpenseCategory(str, enum.Enum):
    ATTORNEY_FEE = "ATTORNEY_FEE"  # שכ"ט עו"ד
    EXPERT = "EXPERT"  # מומחה
    MEDICAL_INFO = "MEDICAL_INFO"  # מידע רפואי
    INVESTIGATOR = "INVESTIGATOR"  # חוקר
    FEES = "FEES"  # אגרות
    OTHER = "OTHER"  # אחר


class ExpensePayer(str, enum.Enum):
    CLIENT_DEDUCTIBLE = "CLIENT_DEDUCTIBLE"  # טר"מ/השתתפות עצמית
    INSURER = "INSURER"


class FeeEventType(str, enum.Enum):
    # Court (stages)
    COURT_STAGE_1_DEFENSE = "COURT_STAGE_1_DEFENSE"
    COURT_STAGE_2_DAMAGES = "COURT_STAGE_2_DAMAGES"
    COURT_STAGE_3_EVIDENCE = "COURT_STAGE_3_EVIDENCE"
    COURT_STAGE_4_PROOFS = "COURT_STAGE_4_PROOFS"
    COURT_STAGE_5_SUMMARIES = "COURT_STAGE_5_SUMMARIES"
    # Court optional
    AMENDED_DEFENSE_PARTIAL = "AMENDED_DEFENSE_PARTIAL"
    AMENDED_DEFENSE_FULL = "AMENDED_DEFENSE_FULL"
    THIRD_PARTY_NOTICE = "THIRD_PARTY_NOTICE"
    ADDITIONAL_PROOF_HEARING = "ADDITIONAL_PROOF_HEARING"  # quantity = hearings
    # Demand letter
    DEMAND_FIX = "DEMAND_FIX"
    DEMAND_HOURLY = "DEMAND_HOURLY"  # quantity = hours
    # Small claims
    SMALL_CLAIMS_MANUAL = "SMALL_CLAIMS_MANUAL"


class NotificationType(str, enum.Enum):
    DEDUCTIBLE_NEAR_EXHAUSTION = "DEDUCTIBLE_NEAR_EXHAUSTION"
    INSURER_STARTED_PAYING = "INSURER_STARTED_PAYING"
    RETAINER_DUE_SOON = "RETAINER_DUE_SOON"
    RETAINER_OVERDUE = "RETAINER_OVERDUE"


