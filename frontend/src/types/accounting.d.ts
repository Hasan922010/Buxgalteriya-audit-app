export type AccountingMode = 'SIMPLE' | 'BHMS';

export interface Organization {
  id: string;
  name: string;
  inn: string;
  mode: AccountingMode;
  vat_payer: boolean;
  created_at: string;
  locked_until_date?: string | null;
}

export interface DashboardKPIs {
  monthly_inflow: string | number;
  monthly_outflow: string | number;
  net_cash_balance: string | number;
  inventory_valuation: string | number;
  total_receivables: string | number;
  total_payables: string | number;
  mode: AccountingMode;
}

export interface Counterparty {
  id: string;
  organization_id: string;
  name: string;
  inn?: string | null;
  mfo?: string | null;
  bank_account?: string | null;
  phone?: string | null;
  is_supplier: boolean;
  is_client: boolean;
}

export interface TrialBalanceItem {
  account_code: string;
  account_name: string;
  account_type: string;
  initial_debit: number;
  initial_credit: number;
  turnover_debit?: number;
  period_debit?: number;
  turnover_credit?: number;
  period_credit?: number;
  final_debit: number;
  final_credit: number;
}

export interface TrialBalanceReport {
  organization_id: string;
  organization_name: string;
  from_date: string;
  to_date: string;
  items: TrialBalanceItem[];
  total_initial_debit: number;
  total_initial_credit: number;
  total_turnover_debit?: number;
  total_period_debit?: number;
  total_turnover_credit?: number;
  total_period_credit?: number;
  total_final_debit: number;
  total_final_credit: number;
  is_balanced: boolean;
}

export interface MaterialReportItem {
  item_id: string;
  item_name: string;
  ikpu_code?: string;
  unit: string;
  initial_qty?: number;
  opening_qty?: number;
  initial_sum?: number;
  opening_sum?: number;
  inflow_qty: number;
  inflow_sum: number;
  outflow_qty: number;
  outflow_sum: number;
  avg_price?: number;
  final_qty?: number;
  closing_qty?: number;
  final_sum?: number;
  closing_sum?: number;
  has_negative_stock?: boolean;
}

export interface MaterialReportMxikGroup {
  ikpu_code: string;
  ikpu_name?: string;
  items_count: number;
  unit?: string;
  initial_qty?: number;
  opening_qty?: number;
  initial_sum?: number;
  opening_sum?: number;
  inflow_qty: number;
  inflow_sum: number;
  outflow_qty: number;
  outflow_sum: number;
  final_qty?: number;
  closing_qty?: number;
  final_sum?: number;
  closing_sum?: number;
}

export interface MaterialReport {
  organization_id: string;
  organization_name: string;
  from_date: string;
  to_date: string;
  items: MaterialReportItem[];
  mxik_groups?: MaterialReportMxikGroup[];
  total_initial_sum?: number;
  total_opening_sum?: number;
  total_inflow_sum: number;
  total_outflow_sum: number;
  total_final_sum?: number;
  total_closing_sum?: number;
}

export interface AktSverkaItem {
  date?: string;
  doc_date?: string;
  doc_number: string;
  doc_type: string;
  description?: string;
  debit: number;
  credit: number;
  running_balance: number;
}

export interface AktSverkaReport {
  organization_id: string;
  organization_name: string;
  counterparty_id: string;
  counterparty_name: string;
  counterparty_inn?: string;
  from_date: string;
  to_date: string;
  initial_debt: number;
  initial_balance?: number;
  total_debit: number;
  total_credit: number;
  final_debt: number;
  final_balance?: number;
  status_uz?: string;
  items: AktSverkaItem[];
}

export interface ColumnMapping {
  date_col?: string;
  doc_num_col?: string;
  item_name_col?: string;
  counterparty_col?: string;
  counterparty_inn_col?: string;
  ikpu_col?: string;
  barcode_col?: string;
  qty_col?: string;
  price_col?: string;
  total_col?: string;
  vat_rate_col?: string;
  vat_amount_col?: string;
  inflow_qty_col?: string;
  inflow_sum_col?: string;
  outflow_qty_col?: string;
  outflow_sum_col?: string;
  return_qty_col?: string;
  return_sum_col?: string;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  detected_format: {
    format_type: 'DIDOX_EHF' | 'BANK_STATEMENT' | 'SOLIQ_REGISTRY' | 'MATERIAL_REPORT' | 'GENERIC_EXCEL' | 'GENERIC_PDF' | 'UNKNOWN';
    confidence: number;
    detected_headers: string[];
    total_rows: number;
    sample_rows: Record<string, any>[];
  };
  message: string;
}

export interface AuditLog {
  id: string;
  organization_id: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  performed_by: string;
  details?: string | null;
  created_at: string;
}

export interface TaxRule {
  rate: number;
  percentage: string;
  name: string;
  legal_basis: string;
  start_date: string;
  end_date: string | null;
}

export type UserRole = 'CHIEF_ACCOUNTANT' | 'OPERATOR' | 'AUDITOR' | 'DIRECTOR';

export interface CurrentUser {
  id: string;
  username: string;
  full_name: string;
  role: UserRole;
  is_superuser: boolean;
  is_active: boolean;
  organization_ids: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: CurrentUser;
}

export interface TaskStatusResponse {
  id: string;
  name: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress: number;
  step_message: string;
  total_items: number;
  processed_items: number;
  error_message?: string | null;
  result?: any;
  created_at: string;
  updated_at: string;
}

export interface AsyncCommitResponse {
  task_id: string;
  status: string;
  step_message?: string;
  message: string;
}

export interface IntegrationProviderStatus {
  success: boolean;
  provider: string;
  status: string;
  message: string;
  server_time: string;
  authenticated?: boolean;
  device_registered?: boolean;
}

export interface IntegrationStatusResponse {
  didox: IntegrationProviderStatus;
  soliq: IntegrationProviderStatus;
}

export interface SyncResponse {
  success: boolean;
  provider: string;
  synced_count: number;
  total_amount: number;
  documents: string[];
  message: string;
}

export interface BackupItem {
  filename: string;
  backup_id: string;
  created_at: string;
  created_by: string;
  size_bytes: number;
  size_kb: number;
  checksum_sha256: string;
  stats: {
    organizations?: number;
    accounts?: number;
    counterparties?: number;
    inventory_items?: number;
    transactions?: number;
    audit_logs?: number;
  };
}

export interface BackupCreateResponse {
  backup_id: string;
  filename: string;
  file_path: string;
  size_bytes: number;
  size_kb: number;
  checksum_sha256: string;
  transactions_count: number;
  created_at: string;
  message: string;
}

export interface TaxAuditItemRow {
  item_no: number;
  item_name: string;
  opening_qty: number;
  opening_amount: number;
  inflow_qty: number;
  inflow_amount: number;
  sold_qty: number;
  avg_price: number;
  sold_amount: number;
  closing_qty: number;
  closing_amount: number;
  diff_qty: number;
  diff_amount: number;
  math_verified?: boolean;
  confidence?: number;
}

export interface TaxPenaltySummary {
  total_discrepancy_amount: number;
  vat_amount: number;
  net_tax_base: number;
  profit_tax_addition: number;
  financial_penalty: number;
  total_budget_liability: number;
}

export interface TaxAuditDocument {
  company_name: string;
  company_inn: string;
  audit_year: number;
  title: string;
  items: TaxAuditItemRow[];
  summary?: TaxPenaltySummary | null;
  preview_image_base64?: string | null;
}



