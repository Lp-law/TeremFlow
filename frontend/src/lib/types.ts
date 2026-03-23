export type CaseType = 'COURT' | 'DEMAND_LETTER' | 'SMALL_CLAIMS'
export type CaseStatus = 'OPEN' | 'CLOSED'

export type ExpenseCategory =
  | 'ATTORNEY_FEE'
  | 'EXPERT'
  | 'MEDICAL_INFO'
  | 'INVESTIGATOR'
  | 'FEES'
  | 'OTHER'

export type ExpensePayer = 'CLIENT_DEDUCTIBLE' | 'INSURER'

export type FeeEventType =
  | 'COURT_STAGE_1_DEFENSE'
  | 'COURT_STAGE_2_DAMAGES'
  | 'COURT_STAGE_3_EVIDENCE'
  | 'COURT_STAGE_4_PROOFS'
  | 'COURT_STAGE_5_SUMMARIES'
  | 'AMENDED_DEFENSE_PARTIAL'
  | 'AMENDED_DEFENSE_FULL'
  | 'THIRD_PARTY_NOTICE'
  | 'ADDITIONAL_PROOF_HEARING'
  | 'DEMAND_FIX'
  | 'DEMAND_HOURLY'
  | 'SMALL_CLAIMS_MANUAL'
  | 'APPEAL'
  | 'STAGE_BILLING'

export type CaseOut = {
  id: number
  case_reference: string
  case_name?: string | null
  case_type: CaseType
  status: CaseStatus
  open_date: string
  retainer_anchor_date: string
  branch_name: string | null
  /** Latest fee event type (procedure stage); override takes precedence over computed. */
  current_procedure_stage?: string | null
  procedure_stage_override?: string | null
  deductible_ils_gross: string | number
  retainer_snapshot_ils_gross: string | number | null
  retainer_snapshot_through_month: string | null
  expenses_snapshot_ils_gross: string | number | null
  historical_fee_stages: string[]
  legacy_fee_text?: string | null
  performed_fee_stage_codes?: string[] | null
  raw_import_fields_json?: Record<string, unknown> | null
  excess_remaining_ils_gross: string | number
  /** Case-level editable expenses total (unified model). */
  expenses_total_ils_gross?: string | number | null
  retainer_is_frozen?: boolean
  retainer_frozen_at?: string | null
  retainer_end_date?: string | null
  retainer_current_start_date?: string | null
  retainer_current_end_date?: string | null
  retainer_legacy_start_date?: string | null
  retainer_legacy_end_date?: string | null
  case_notes?: string | null
  insurer_started: boolean
  insurer_start_date: string | null
  /** Manual overrides for deductible/overview (from GET /cases/{id}). */
  manual_overrides_json?: Record<string, unknown> | null
}

export type ExpenseOut = {
  id: number
  case_id: number
  supplier_name: string
  amount_ils_gross: string | number
  service_description: string
  demand_received_date: string
  expense_date: string
  category: ExpenseCategory
  payer: ExpensePayer
  attachment_url: string | null
  split_group_id: string | null
  is_split_part: boolean
}

export type ExpenseSummary = {
  total_expenses_ils: string | number
  deductible_consumed_by_expenses_ils: string | number
  other_expenses_ils: string | number
}

/** Unified deductible/excess summary (GET /cases/{id}/deductible/summary). */
export type DeductibleSummary = {
  excess_total_ils: string | number
  retainer_charged_to_date_ils: string | number
  expenses_total_ils: string | number
  fees_by_stages_ils: string | number
  excess_remaining_ils: string | number
  fee_diff_ils: string | number
  manual_overrides: Record<string, unknown>
}

/** Unified overview from GET /cases/{id}/overview-summary */
export type CaseOverviewSummary = {
  case_reference: string
  case_name: string | null
  branch_name: string | null
  status: string
  current_procedure_stage: string | null
  fees: {
    fees_by_stages_ils: string | number
    retainer_charged_to_date_ils: string | number
    fee_diff_ils: string | number
    last_fee_event_date: string | null
    last_fee_event_amount: string | number | null
  }
  retainer: {
    retainer_charged_to_date_ils: string | number
    /** Total theoretical from ledger — same as total_theoretical_ils_gross (single source for overview) */
    retainer_theoretical_ils?: string | number
    retainer_regular_theoretical_ils?: string | number
    retainer_legacy_theoretical_ils?: string | number
    charged_months_count: number
    monthly_gross_ils: string | number
    retainer_is_frozen: boolean
    retainer_frozen_at: string | null
  }
  expenses: {
    total_expenses_ils: string | number
  }
  deductible: {
    excess_total_ils: string | number
    excess_remaining_ils: string | number
  }
}

export type CaseWarning = {
  code: string
  severity: 'info' | 'warn' | 'error'
  title: string
  details: string
  action_tab?: string | null
}

export type CaseWarningsResponse = {
  warnings: CaseWarning[]
}

export type RetainerAccrual = {
  id: number
  accrual_month: string
  invoice_date: string
  due_date: string
  amount_ils_gross: string | number
  is_paid: boolean
}

export type RetainerPayment = {
  id: number
  payment_date: string
  amount_ils_gross: string | number
}

export type RetainerSummary = {
  retainer_accrued_total_ils_gross: string | number
  retainer_paid_total_ils_gross: string | number
  retainer_applied_to_fees_total_ils_gross: string | number
  retainer_credit_balance_ils_gross: string | number
  fees_due_total_ils_gross: string | number
}

export type RetainerLedgerConfig = {
  monthly_base_net_ils: string | number
  vat_pct: string
  monthly_gross_ils: string | number
}

export type RetainerLedgerRow = {
  month: string
  accrued_ils: string | number
  paid_ils: string | number
  running_credit_ils: string | number
  row_type: 'snapshot' | 'accrual' | 'payment'
  notes: string | null
}

export type RetainerLedger = {
  config: RetainerLedgerConfig
  anchor_date: string
  snapshot_through_month: string | null
  snapshot_paid_ils: string | number
  current_credit_ils: string | number
  charged_months_count: number
  retainer_paid_total_ils_gross: string | number
  total_accrued_ils?: string | number
  total_retainer_theoretical_ils_gross?: string | number
  total_current_theoretical_ils?: string | number
  total_legacy_theoretical_ils?: string | number
  /** Single source of truth for UI (same aggregation as rows) */
  total_theoretical_ils_gross?: string | number
  total_paid_ils_gross?: string | number
  total_credit_ils_gross?: string | number
  rows: RetainerLedgerRow[]
}

export type FeeEvent = {
  id: number
  event_type: FeeEventType
  event_date: string
  quantity: number
  amount_override_ils_gross: string | number | null
  computed_amount_ils_gross: string | number
  amount_covered_by_credit_ils_gross: string | number
  amount_due_cash_ils_gross: string | number
  breakdown_json?: { codes?: string[]; new_codes?: string[]; base_total?: string; adjustment?: unknown; final_total?: string } | null
}

export type NotificationSeverity = 'info' | 'warning' | 'danger'

export type Notification = {
  id: number
  case_id: number | null
  type: string
  title: string
  message: string
  severity: NotificationSeverity | string
  is_read: boolean
  created_at: string
}

export type ExpensesByCaseRow = {
  case_id: number
  case_reference: string
  case_type: CaseType
  status: CaseStatus
  payer_status: 'client' | 'insurer' | 'closed' | string
  total_expenses_ils_gross: string | number
  attorney_fees_expenses_ils_gross: string | number
  other_expenses_ils_gross: string | number
  deductible_remaining_ils_gross: string | number
}

export type TimeSeriesPoint = {
  period: string
  total_expenses_ils_gross: string | number
}

export type StageDistributionRow = {
  stage: number
  count: number
}

export type AnalyticsOverviewResponse = {
  total_expenses_ils_gross: string | number
  total_on_deductible_ils_gross: string | number
  total_on_insurer_ils_gross: string | number
  average_expenses_per_case_ils_gross: string | number
  cases_switched_to_insurer_count: number
  aggregate_remaining_deductible_open_cases_ils_gross: string | number
  expenses_by_case: ExpensesByCaseRow[]
  expense_split: { attorney: string | number; other: string | number } | Record<string, string | number>
  court_cases_end_stage_distribution: StageDistributionRow[]
  monthly: TimeSeriesPoint[]
  quarterly: TimeSeriesPoint[]
  yearly: TimeSeriesPoint[]
}

/** Analytics v2: case-based filters, unified KPIs */
export type AnalyticsV2Filters = {
  start_date: string
  end_date: string
  case_type: string
  status: string
  branch_name: string
  denominator_cases: number
}

export type AnalyticsV2KPIs = {
  avg_stage_fee_ils: string | number
  avg_retainer_fee_ils: string | number
  avg_expenses_ils: string | number
}

export type ClosingStageRow = {
  code: string
  label: string
  count: number
  pct: number
}

export type BranchCaseTypeRow = {
  branch_name: string | null
  case_type: string
  count: number
}

export type ByBranchRow = { branch_name: string | null; count: number }
export type ByCaseTypeRow = { case_type: string; count: number }

/** Average closing stage index (COURT, CLOSED, stages 1-5 only) */
export type ClosingStageIndexRow = { stage: number; count: number; pct: number }

export type ExtraMetrics = {
  avg_closing_stage_index: number
  closing_stage_index_denominator_cases: number
  closing_stage_index_distribution: ClosingStageIndexRow[]
}

export type BranchFeeAverageRow = {
  branch_name: string
  cases_count: number
  avg_stage_fee_ils: string | number
  avg_retainer_fee_ils: string | number
  avg_expenses_ils: string | number
}

export type BranchCaseTypeFeeAverageRow = {
  branch_name: string
  case_type: string
  cases_count: number
  avg_stage_fee_ils: string | number
  avg_retainer_fee_ils: string | number
  avg_expenses_ils: string | number
}

export type CaseTypeFeeAverageRow = {
  case_type: string
  cases_count: number
  avg_stage_fee_ils: string | number
  avg_retainer_fee_ils: string | number
  avg_expenses_ils: string | number
}

export type AnalyticsV2Response = {
  filters: AnalyticsV2Filters
  kpis: AnalyticsV2KPIs
  distributions: {
    closing_stage: ClosingStageRow[]
    branch_case_type: BranchCaseTypeRow[]
  }
  totals: {
    by_branch: ByBranchRow[]
    by_case_type: ByCaseTypeRow[]
  }
  extra_metrics?: ExtraMetrics | null
  branch_fee_averages?: BranchFeeAverageRow[]
  branch_case_type_fee_averages?: BranchCaseTypeFeeAverageRow[]
  case_type_fee_averages?: CaseTypeFeeAverageRow[]
}

/** Branding for client report (logo base64 preferred; no URL fetch). */
export type ClientReportBrand = {
  logo_base64?: string | null
  primary_hex?: string
  accent_hex?: string
  header_bg_hex?: string | null
  header_text_hex?: string
}

export type ClaimsReportStatus = 'DRAFT' | 'FINAL'
export type ClaimsRowLinkageType = 'LINKED' | 'MANUAL'
export type ClaimsCategory =
  | 'COURT_REPORTED_TO_INSURER'
  | 'REPORTED_WITHOUT_CLAIM'
  | 'NOT_REPORTED_TO_INSURER'
  | 'NON_MEDICAL_MALPRACTICE'
  | 'OTHER'
export type ClaimsReportCaseStatus =
  | 'OPEN'
  | 'CLOSED'
  | 'CANNOT_ASSESS_YET'
  | 'NO_EXPOSURE'
  | 'REJECTED_EXPECTED'
  | 'SETTLED'
  | 'JUDGMENT'
  | 'REJECTED'
  | 'REJECTED_WITH_COSTS'
export type ClaimsFinalOutcomeType =
  | 'SETTLEMENT'
  | 'JUDGMENT_FOR_PLAINTIFF'
  | 'CLAIM_REJECTED'
  | 'CLAIM_REJECTED_WITH_COSTS'
  | 'CLOSED_WITHOUT_PAYMENT'
  | 'OTHER'

export type ClaimsReportOut = {
  id: number
  client_name: string
  institution_name: string | null
  title: string
  report_cutoff_date: string
  updated_to_date: string | null
  recommended_reserve_ils: string | number | null
  intro_text: string | null
  closing_text: string | null
  status: ClaimsReportStatus
  template_key: string | null
  created_by_user_id: number | null
  finalized_at: string | null
  created_at: string
  updated_at: string
  rows_count: number
}

export type ClaimsReportRowOut = {
  id: number
  report_id: number
  linked_case_id: number | null
  linkage_type: ClaimsRowLinkageType
  case_reference_text: string | null
  case_title: string | null
  court_name: string | null
  proceeding_number: string | null
  branch_name: string | null
  institution_name: string | null
  category_for_report: ClaimsCategory
  report_case_status: ClaimsReportCaseStatus
  status_note: string | null
  current_risk_assessment_ils: string | number | null
  risk_assessment_text: string | null
  risk_assessment_updated_at: string | null
  risk_assessment_updated_by_user_id: number | null
  final_outcome_type: ClaimsFinalOutcomeType | null
  final_outcome_amount_ils: string | number | null
  awarded_costs_to_terem_ils: string | number | null
  final_outcome_date: string | null
  final_outcome_text: string | null
  deductible_usd: string | number | null
  deductible_ils_gross: string | number | null
  amount_already_paid_on_deductible_ils: string | number | null
  remaining_deductible_ils: string | number | null
  expenses_total_ils: string | number | null
  fees_total_ils: string | number | null
  retainer_charged_ils: string | number | null
  exposure_for_reserve_ils: string | number | null
  narrative_text: string | null
  legal_summary_text: string | null
  internal_notes: string | null
  include_in_report: boolean
  source_snapshot_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
  narrative_preview: string
}

export type ClaimsReportDetailsOut = {
  report: ClaimsReportOut
  rows: ClaimsReportRowOut[]
}


