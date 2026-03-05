from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, ExpenseCategory, ExpensePayer, FeeEventType
from app.models.expense import Expense
from app.models.fee_event import FeeEvent
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsV2Distributions,
    AnalyticsV2Filters,
    AnalyticsV2KPIs,
    AnalyticsV2Response,
    AnalyticsV2Totals,
    BranchCaseTypeRow,
    BranchCaseTypeFeeAverageRow,
    BranchFeeAverageRow,
    ByBranchRow,
    ByCaseTypeRow,
    ClosingStageIndexRow,
    ClosingStageRow,
    ExpensesByCaseRow,
    ExtraMetrics,
    StageDistributionRow,
    TimeSeriesPoint,
)
from app.schemas.client_report import ClientReportRequest
from app.services import cases as case_service
from app.services.analytics_report import build_client_report
from app.services.deductible import q_ils
from app.services.unified import excess_remaining_ils as unified_excess_remaining_ils
from app.services.unified import get_unified_summary

router = APIRouter()

# Hebrew labels for procedure stage codes (closing_stage distribution)
STAGE_CODE_LABELS: dict[str, str] = {
    "COURT_STAGE_1_DEFENSE": "שלב 1 — כתב הגנה",
    "COURT_STAGE_2_DAMAGES": "שלב 2 — חישובי נזק",
    "COURT_STAGE_3_EVIDENCE": "שלב 3 — הגשת ראיות",
    "COURT_STAGE_4_PROOFS": "שלב 4 — ראיות",
    "COURT_STAGE_5_SUMMARIES": "שלב 5 — סיכומים",
    "AMENDED_DEFENSE_PARTIAL": "הגנה מתוקנת חלקית",
    "AMENDED_DEFENSE_FULL": "הגנה מתוקנת מלאה",
    "THIRD_PARTY_NOTICE": "הודעה לצד שלישי",
    "ADDITIONAL_PROOF_HEARING": "שמיעת ראיות נוספת",
    "DEMAND_FIX": "מכתב דרישה — תיקון",
    "DEMAND_HOURLY": "מכתב דרישה — שעתי",
    "SMALL_CLAIMS_MANUAL": "תביעות קטנות",
    "APPEAL": "ערעור",
    "STAGE_BILLING:0": "חיוב שלבים (ללא קודים)",
}
DEFAULT_STAGE_LABEL = "—"

# Map court stage codes to numeric index 1-5 for "average closing stage" (only these count).
COURT_STAGE_CODE_TO_INDEX: dict[str, int] = {
    "COURT_STAGE_1_DEFENSE": 1,
    "COURT_STAGE_2_DAMAGES": 2,
    "COURT_STAGE_3_EVIDENCE": 3,
    "COURT_STAGE_4_PROOFS": 4,
    "COURT_STAGE_5_SUMMARIES": 5,
}
BRANCH_NULL_LABEL = "ללא סניף"


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

    cases_q = db.query(Case).filter(Case.deleted_at.is_(None))
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
                deductible_remaining_ils_gross=unified_excess_remaining_ils(db, c),
            )
        )

    avg = q_ils(total / Decimal(len(cases))) if cases else Decimal("0.00")

    switched = 0
    for c in cases:
        if c.insurer_started and c.insurer_start_date and start_date <= c.insurer_start_date <= end_date:
            switched += 1

    aggregate_remaining = q_ils(
        sum(
            (unified_excess_remaining_ils(db, c) for c in cases if c.status == CaseStatus.OPEN),
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


@router.get("/v2/branches")
def analytics_v2_branches(
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    """Distinct branch_name values (excluding soft-deleted cases) for filter dropdown."""
    from sqlalchemy import distinct, select

    rows = db.query(distinct(Case.branch_name)).filter(Case.deleted_at.is_(None)).order_by(Case.branch_name).all()
    return [r[0] for r in rows]


def compute_analytics_v2_response(
    db: Session,
    start_date: dt.date,
    end_date: dt.date,
    case_type: str | None = None,
    status: str | None = None,
    branch_name: str | None = None,
) -> AnalyticsV2Response:
    """
    Compute analytics v2 data (same as GET /analytics/v2). Used by both the endpoint and client-report.
    Excludes soft-deleted cases and uses only non-deleted fee events.
    """
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    # Filter cases: deleted_at IS NULL, open_date in [start_date, end_date]
    q = (
        db.query(Case)
        .filter(Case.deleted_at.is_(None))
        .filter(Case.open_date >= start_date, Case.open_date <= end_date)
    )
    if case_type and str(case_type).strip().upper() not in ("ALL", ""):
        try:
            q = q.filter(Case.case_type == CaseType(case_type.strip()))
        except ValueError:
            pass
    if status and str(status).strip().upper() not in ("ALL", ""):
        try:
            q = q.filter(Case.status == CaseStatus(status.strip()))
        except ValueError:
            pass
    if branch_name is not None and str(branch_name).strip().upper() != "ALL":
        bn = str(branch_name).strip()
        if bn.upper() == "__NULL__":
            q = q.filter(Case.branch_name.is_(None))
        elif bn:
            q = q.filter(Case.branch_name == bn)

    cases = q.all()
    denominator = len(cases)

    def _zero_kpis():
        return AnalyticsV2Response(
            filters=AnalyticsV2Filters(
                start_date=start_date,
                end_date=end_date,
                case_type=case_type or "ALL",
                status=status or "ALL",
                branch_name=branch_name or "ALL",
                denominator_cases=0,
            ),
            kpis=AnalyticsV2KPIs(
                avg_stage_fee_ils=Decimal("0.00"),
                avg_retainer_fee_ils=Decimal("0.00"),
                avg_expenses_ils=Decimal("0.00"),
            ),
            distributions=AnalyticsV2Distributions(closing_stage=[], branch_case_type=[]),
            totals=AnalyticsV2Totals(by_branch=[], by_case_type=[]),
            extra_metrics=ExtraMetrics(
                avg_closing_stage_index=0.0,
                closing_stage_index_denominator_cases=0,
                closing_stage_index_distribution=[],
            ),
            branch_fee_averages=[],
            branch_case_type_fee_averages=[],
        )

    if not cases:
        return _zero_kpis()

    # Single pass: build (case, unified) for reuse in KPIs and branch averages
    case_unified: list[tuple[Case, dict]] = []
    for c in cases:
        u = get_unified_summary(db, c)
        case_unified.append((c, u))

    n = Decimal(denominator)
    sum_stage = sum(Decimal(str(u["fees_by_stages_ils"])) for _, u in case_unified)
    sum_retainer = sum(Decimal(str(u["retainer_charged_to_date_ils"])) for _, u in case_unified)
    sum_expenses = sum(Decimal(str(u["expenses_total_ils"])) for _, u in case_unified)
    kpis = AnalyticsV2KPIs(
        avg_stage_fee_ils=q_ils(sum_stage / n),
        avg_retainer_fee_ils=q_ils(sum_retainer / n),
        avg_expenses_ils=q_ils(sum_expenses / n),
    )

    # Closing stage distribution (CLOSED cases only; override or computed; exclude deleted fee events)
    closed_cases = [c for c in cases if c.status == CaseStatus.CLOSED]
    closing_stage_rows: list[ClosingStageRow] = []
    computed_stages_for_closed: dict[int, str] = {}
    if closed_cases:
        closed_ids = [c.id for c in closed_cases]
        computed_stages_for_closed = case_service.get_latest_fee_stage_by_case_ids(db, closed_ids)
        code_counts: dict[str, int] = defaultdict(int)
        for c in closed_cases:
            override = (c.procedure_stage_override or "").strip()
            code = override or computed_stages_for_closed.get(c.id) or "—"
            code_counts[code] += 1
        total_closed = len(closed_cases)
        for code in sorted(code_counts.keys()):
            count = code_counts[code]
            pct = round(100.0 * count / total_closed, 1) if total_closed else 0.0
            label = STAGE_CODE_LABELS.get(code, code if code != "—" else "ללא שלב")
            closing_stage_rows.append(ClosingStageRow(code=code, label=label, count=count, pct=pct))

    # Extra metrics: average closing stage index (COURT, CLOSED only; stage code in 1-5)
    stage_index_values: list[int] = []
    court_closed_cases = [c for c in closed_cases if c.case_type == CaseType.COURT]
    for c in court_closed_cases:
        override = (c.procedure_stage_override or "").strip()
        code = override or computed_stages_for_closed.get(c.id) or ""
        idx = COURT_STAGE_CODE_TO_INDEX.get(code)
        if idx is not None:
            stage_index_values.append(idx)
    index_denom = len(stage_index_values)
    avg_index = round(sum(stage_index_values) / index_denom, 2) if index_denom else 0.0
    index_distribution: list[ClosingStageIndexRow] = []
    if index_denom:
        stage_counts_1_5: dict[int, int] = {i: 0 for i in range(1, 6)}
        for idx in stage_index_values:
            stage_counts_1_5[idx] = stage_counts_1_5.get(idx, 0) + 1
        for stage in range(1, 6):
            count = stage_counts_1_5.get(stage, 0)
            pct = round(100.0 * count / index_denom, 1)
            index_distribution.append(ClosingStageIndexRow(stage=stage, count=count, pct=pct))
    extra_metrics = ExtraMetrics(
        avg_closing_stage_index=avg_index,
        closing_stage_index_denominator_cases=index_denom,
        closing_stage_index_distribution=index_distribution,
    )

    # Branch fee averages (group by branch_display; use "ללא סניף" for null)
    def _branch_display(c: Case) -> str:
        return c.branch_name if c.branch_name else BRANCH_NULL_LABEL

    branch_to_data: dict[str, list[tuple[Case, dict]]] = defaultdict(list)
    for c, u in case_unified:
        branch_to_data[_branch_display(c)].append((c, u))
    branch_fee_rows: list[BranchFeeAverageRow] = []
    for bn in sorted(branch_to_data.keys(), key=(lambda x: (x == BRANCH_NULL_LABEL, x))):
        group = branch_to_data[bn]
        cnt = len(group)
        s_stage = sum(Decimal(str(u["fees_by_stages_ils"])) for _, u in group)
        s_ret = sum(Decimal(str(u["retainer_charged_to_date_ils"])) for _, u in group)
        s_exp = sum(Decimal(str(u["expenses_total_ils"])) for _, u in group)
        branch_fee_rows.append(
            BranchFeeAverageRow(
                branch_name=bn,
                cases_count=cnt,
                avg_stage_fee_ils=q_ils(s_stage / cnt) if cnt else Decimal("0.00"),
                avg_retainer_fee_ils=q_ils(s_ret / cnt) if cnt else Decimal("0.00"),
                avg_expenses_ils=q_ils(s_exp / cnt) if cnt else Decimal("0.00"),
            )
        )

    # Branch × case_type fee averages
    key_to_data: dict[tuple[str, str], list[tuple[Case, dict]]] = defaultdict(list)
    for c, u in case_unified:
        ct_val = c.case_type.value if hasattr(c.case_type, "value") else str(c.case_type)
        key_to_data[(_branch_display(c), ct_val)].append((c, u))
    branch_case_type_fee_rows: list[BranchCaseTypeFeeAverageRow] = []
    for (bn, ct), group in sorted(key_to_data.items(), key=lambda x: (-len(x[1]), x[0][0], x[0][1])):
        cnt = len(group)
        s_stage = sum(Decimal(str(u["fees_by_stages_ils"])) for _, u in group)
        s_ret = sum(Decimal(str(u["retainer_charged_to_date_ils"])) for _, u in group)
        s_exp = sum(Decimal(str(u["expenses_total_ils"])) for _, u in group)
        branch_case_type_fee_rows.append(
            BranchCaseTypeFeeAverageRow(
                branch_name=bn,
                case_type=ct,
                cases_count=cnt,
                avg_stage_fee_ils=q_ils(s_stage / cnt) if cnt else Decimal("0.00"),
                avg_retainer_fee_ils=q_ils(s_ret / cnt) if cnt else Decimal("0.00"),
                avg_expenses_ils=q_ils(s_exp / cnt) if cnt else Decimal("0.00"),
            )
        )

    # Branch × case_type volume
    branch_case_type_map: dict[tuple[str | None, str], int] = defaultdict(int)
    for c in cases:
        key = (c.branch_name if c.branch_name else None, c.case_type.value if hasattr(c.case_type, "value") else str(c.case_type))
        branch_case_type_map[key] += 1
    branch_case_type_rows = [
        BranchCaseTypeRow(branch_name=bn, case_type=ct, count=count)
        for (bn, ct), count in sorted(branch_case_type_map.items(), key=lambda x: (-x[1], str(x[0][0] or ""), x[0][1]))
    ]

    # Totals by_branch and by_case_type
    by_branch_map: dict[str | None, int] = defaultdict(int)
    by_case_type_map: dict[str, int] = defaultdict(int)
    for c in cases:
        by_branch_map[c.branch_name if c.branch_name else None] += 1
        ct_val = c.case_type.value if hasattr(c.case_type, "value") else str(c.case_type)
        by_case_type_map[ct_val] += 1
    by_branch_rows = [ByBranchRow(branch_name=bn, count=count) for bn, count in sorted(by_branch_map.items(), key=lambda x: (-x[1], str(x[0] or "")))]
    by_case_type_rows = [ByCaseTypeRow(case_type=ct, count=count) for ct, count in sorted(by_case_type_map.items(), key=lambda x: (-x[1], x[0]))]

    return AnalyticsV2Response(
        filters=AnalyticsV2Filters(
            start_date=start_date,
            end_date=end_date,
            case_type=case_type or "ALL",
            status=status or "ALL",
            branch_name=branch_name or "ALL",
            denominator_cases=denominator,
        ),
        kpis=kpis,
        distributions=AnalyticsV2Distributions(
            closing_stage=closing_stage_rows,
            branch_case_type=branch_case_type_rows,
        ),
        totals=AnalyticsV2Totals(by_branch=by_branch_rows, by_case_type=by_case_type_rows),
        extra_metrics=extra_metrics,
        branch_fee_averages=branch_fee_rows,
        branch_case_type_fee_averages=branch_case_type_fee_rows,
    )


@router.get("/v2", response_model=AnalyticsV2Response)
def analytics_v2(
    start_date: dt.date = Query(..., description="Case open_date from (inclusive)"),
    end_date: dt.date = Query(..., description="Case open_date to (inclusive)"),
    case_type: str | None = Query(default=None, description="ALL or COURT, DEMAND_LETTER, SMALL_CLAIMS"),
    status: str | None = Query(default=None, description="ALL or OPEN, CLOSED"),
    branch_name: str | None = Query(default=None, description="ALL or specific branch name"),
    db: Session = Depends(get_db),
    _=Depends(require_auth),
) -> AnalyticsV2Response:
    """Analytics v2: case-based filters, unified KPIs, closing stage, branch volume."""
    return compute_analytics_v2_response(db, start_date, end_date, case_type, status, branch_name)


@router.post("/client-report")
def analytics_client_report(
    body: ClientReportRequest,
    db: Session = Depends(get_db),
    _=Depends(require_auth),
) -> Response:
    """
    Generate client-facing report (PDF or DOCX) from Analytics v2 data.
    Uses same aggregation as GET /analytics/v2; no case identifiers in output.
    """
    f = body.filters
    start_date = dt.datetime.strptime(f.start_date, "%Y-%m-%d").date()
    end_date = dt.datetime.strptime(f.end_date, "%Y-%m-%d").date()
    if end_date < start_date:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    branch_name: str | None = None
    if f.branch_is_null is True:
        branch_name = "__NULL__"
    elif f.branch_name and str(f.branch_name).strip():
        branch_name = f.branch_name.strip()

    response = compute_analytics_v2_response(
        db,
        start_date=start_date,
        end_date=end_date,
        case_type=f.case_type,
        status=f.status,
        branch_name=branch_name,
    )
    data_dict = response.model_dump(mode="json")
    brand = body.brand.model_dump() if body.brand else None
    content, filename = build_client_report(
        data_dict,
        template_id=body.template_id or "T1",
        report_format=body.format or "pdf",
        brand=brand,
    )
    media_type = "application/pdf" if (body.format or "pdf").lower() == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


