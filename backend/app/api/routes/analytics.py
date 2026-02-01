from __future__ import annotations

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, ExpenseCategory, ExpensePayer, FeeEventType
from app.models.expense import Expense
from app.models.fee_event import FeeEvent
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    ExpensesByCaseRow,
    StageDistributionRow,
    TimeSeriesPoint,
)
from app.services.deductible import q_ils
from app.services.expenses import get_case_deductible_remaining

router = APIRouter()


@router.get("/overview")
def overview(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    case_type: CaseType | None = Query(default=None),
    payer_status: str | None = Query(default=None),  # client|insurer|closed|all
    db: Session = Depends(get_db),
    _=Depends(require_auth),
) -> AnalyticsOverviewResponse:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    cases_q = db.query(Case)
    if case_type:
        cases_q = cases_q.filter(Case.case_type == case_type)
    cases = cases_q.all()

    def compute_payer_status(c: Case) -> str:
        if c.status == CaseStatus.CLOSED:
            return "closed"
        return "insurer" if c.insurer_started else "client"

    if payer_status and payer_status != "all":
        cases = [c for c in cases if compute_payer_status(c) == payer_status]

    case_ids = [c.id for c in cases]
    if not case_ids:
        return AnalyticsOverviewResponse(
            total_expenses_ils_gross=Decimal("0.00"),
            total_on_deductible_ils_gross=Decimal("0.00"),
            total_on_insurer_ils_gross=Decimal("0.00"),
            average_expenses_per_case_ils_gross=Decimal("0.00"),
            cases_switched_to_insurer_count=0,
            aggregate_remaining_deductible_open_cases_ils_gross=Decimal("0.00"),
            expenses_by_case=[],
            expense_split={"attorney": Decimal("0.00"), "other": Decimal("0.00")},
            court_cases_end_stage_distribution=[],
            monthly=[],
            quarterly=[],
            yearly=[],
        )

    expenses = (
        db.query(Expense)
        .filter(Expense.case_id.in_(case_ids), Expense.expense_date >= start_date, Expense.expense_date <= end_date)
        .all()
    )

    total = q_ils(sum((Decimal(str(e.amount_ils_gross)) for e in expenses), Decimal("0.00")))
    total_on_deductible = q_ils(
        sum((Decimal(str(e.amount_ils_gross)) for e in expenses if e.payer == ExpensePayer.CLIENT_DEDUCTIBLE), Decimal("0.00"))
    )
    total_on_insurer = q_ils(
        sum((Decimal(str(e.amount_ils_gross)) for e in expenses if e.payer == ExpensePayer.INSURER), Decimal("0.00"))
    )

    by_case: dict[int, list[Expense]] = {cid: [] for cid in case_ids}
    for e in expenses:
        by_case[e.case_id].append(e)

    expenses_by_case: list[ExpensesByCaseRow] = []
    attorney_total = Decimal("0.00")
    other_total = Decimal("0.00")
    for c in cases:
        exps = by_case.get(c.id, [])
        total_case = q_ils(sum((Decimal(str(e.amount_ils_gross)) for e in exps), Decimal("0.00")))
        attorney_case = q_ils(
            sum((Decimal(str(e.amount_ils_gross)) for e in exps if e.category == ExpenseCategory.ATTORNEY_FEE), Decimal("0.00"))
        )
        other_case = q_ils(total_case - attorney_case)
        attorney_total += attorney_case
        other_total += other_case
        expenses_by_case.append(
            ExpensesByCaseRow(
                case_id=c.id,
                case_reference=c.case_reference,
                case_type=c.case_type,
                status=c.status,
                payer_status=compute_payer_status(c),
                total_expenses_ils_gross=total_case,
                attorney_fees_expenses_ils_gross=attorney_case,
                other_expenses_ils_gross=other_case,
                deductible_remaining_ils_gross=get_case_deductible_remaining(db, c),
            )
        )

    avg = q_ils(total / Decimal(len(cases))) if cases else Decimal("0.00")

    switched = 0
    for c in cases:
        if c.insurer_started and c.insurer_start_date and start_date <= c.insurer_start_date <= end_date:
            switched += 1

    aggregate_remaining = q_ils(
        sum(
            (get_case_deductible_remaining(db, c) for c in cases if c.status == CaseStatus.OPEN),
            Decimal("0.00"),
        )
    )

    # Stage distribution (court only): highest stage event among stages 1..5.
    stage_map: dict[FeeEventType, int] = {
        FeeEventType.COURT_STAGE_1_DEFENSE: 1,
        FeeEventType.COURT_STAGE_2_DAMAGES: 2,
        FeeEventType.COURT_STAGE_3_EVIDENCE: 3,
        FeeEventType.COURT_STAGE_4_PROOFS: 4,
        FeeEventType.COURT_STAGE_5_SUMMARIES: 5,
    }
    court_cases = [c for c in cases if c.case_type == CaseType.COURT]
    stage_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    if court_cases:
        court_ids = [c.id for c in court_cases]
        fee_events = db.query(FeeEvent).filter(FeeEvent.case_id.in_(court_ids)).all()
        highest: dict[int, int] = {}
        for e in fee_events:
            if e.event_type in stage_map:
                stage = stage_map[e.event_type]
                highest[e.case_id] = max(highest.get(e.case_id, 0), stage)
        for cid, stage in highest.items():
            if stage in stage_counts:
                stage_counts[stage] += 1
    stage_dist = [StageDistributionRow(stage=s, count=stage_counts[s]) for s in sorted(stage_counts.keys())]

    # Time series
    def month_key(d: dt.date) -> str:
        return f"{d.year:04d}-{d.month:02d}"

    def quarter_key(d: dt.date) -> str:
        q = (d.month - 1) // 3 + 1
        return f"{d.year:04d}-Q{q}"

    def year_key(d: dt.date) -> str:
        return f"{d.year:04d}"

    monthly_map: dict[str, Decimal] = {}
    quarterly_map: dict[str, Decimal] = {}
    yearly_map: dict[str, Decimal] = {}
    for e in expenses:
        amt = Decimal(str(e.amount_ils_gross))
        monthly_map[month_key(e.expense_date)] = monthly_map.get(month_key(e.expense_date), Decimal("0.00")) + amt
        quarterly_map[quarter_key(e.expense_date)] = quarterly_map.get(quarter_key(e.expense_date), Decimal("0.00")) + amt
        yearly_map[year_key(e.expense_date)] = yearly_map.get(year_key(e.expense_date), Decimal("0.00")) + amt

    monthly = [TimeSeriesPoint(period=k, total_expenses_ils_gross=q_ils(v)) for k, v in sorted(monthly_map.items())]
    quarterly = [TimeSeriesPoint(period=k, total_expenses_ils_gross=q_ils(v)) for k, v in sorted(quarterly_map.items())]
    yearly = [TimeSeriesPoint(period=k, total_expenses_ils_gross=q_ils(v)) for k, v in sorted(yearly_map.items())]

    return AnalyticsOverviewResponse(
        total_expenses_ils_gross=total,
        total_on_deductible_ils_gross=total_on_deductible,
        total_on_insurer_ils_gross=total_on_insurer,
        average_expenses_per_case_ils_gross=avg,
        cases_switched_to_insurer_count=switched,
        aggregate_remaining_deductible_open_cases_ils_gross=aggregate_remaining,
        expenses_by_case=sorted(expenses_by_case, key=lambda r: r.total_expenses_ils_gross, reverse=True),
        expense_split={"attorney": q_ils(attorney_total), "other": q_ils(other_total)},
        court_cases_end_stage_distribution=stage_dist,
        monthly=monthly,
        quarterly=quarterly,
        yearly=yearly,
    )


