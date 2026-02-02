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

export type CaseOut = {
  id: number
  case_reference: string
  case_name?: string | null
  case_type: CaseType
  status: CaseStatus
  open_date: string
  retainer_anchor_date: string
  branch_name: string | null
  deductible_ils_gross: string | number
  retainer_snapshot_ils_gross: string | number | null
  retainer_snapshot_through_month: string | null
  expenses_snapshot_ils_gross: string | number | null
  excess_remaining_ils_gross: string | number
  insurer_started: boolean
  insurer_start_date: string | null
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

export type FeeEvent = {
  id: number
  event_type: FeeEventType
  event_date: string
  quantity: number
  amount_override_ils_gross: string | number | null
  computed_amount_ils_gross: string | number
  amount_covered_by_credit_ils_gross: string | number
  amount_due_cash_ils_gross: string | number
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


