import {
  Organization,
  DashboardKPIs,
  TrialBalanceReport,
  MaterialReport,
  AktSverkaReport,
  UploadResponse,
  ColumnMapping,
  AuditLog,
  TaxRule,
  UserRole,
  TaskStatusResponse,
  AsyncCommitResponse,
  IntegrationStatusResponse,
  SyncResponse,
  BackupItem,
  BackupCreateResponse,
  TaxAuditItemRow,
  TaxPenaltySummary,
  TaxAuditDocument,
  CurrentUser,
  LoginResponse,
} from "../types/accounting";
import { appCache } from "./cache";
import { API_BASE, authFetch, authHeaders, downloadWithAuth } from "./auth";

function getHeaders(custom: Record<string, string> = {}): Record<string, string> {
  return authHeaders(custom);
}

async function errorFrom(res: Response, fallback: string): Promise<Error> {
  const err = await res.json().catch(() => ({}));
  return new Error(err.detail || fallback);
}

export const apiClient = {
  // Authentication
  async login(username: string, password: string): Promise<LoginResponse> {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw await errorFrom(res, "Tizimga kirib bo'lmadi");
    return res.json();
  },

  async getMe(): Promise<CurrentUser> {
    const res = await authFetch(`${API_BASE}/auth/me`);
    if (!res.ok) throw await errorFrom(res, "Foydalanuvchi ma'lumotlarini yuklab bo'lmadi");
    return res.json();
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    const res = await authFetch(`${API_BASE}/auth/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!res.ok) throw await errorFrom(res, "Parolni o'zgartirib bo'lmadi");
  },

  // Protected file downloads (exports, backups)
  async downloadExport(format: "xlsx" | "pdf", reportType: "oborotka" | "material" | "sverka", params: Record<string, string>): Promise<void> {
    await downloadWithAuth(this.getExportUrl(format, reportType, params), `${reportType}.${format}`);
  },

  async downloadBackup(filename: string): Promise<void> {
    await downloadWithAuth(this.getBackupDownloadUrl(filename), filename);
  },

  async getOrganizations(): Promise<Organization[]> {
    const res = await authFetch(`${API_BASE}/organizations`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Tashkilotlarni yuklab bo'lmadi");
    return res.json();
  },

  async createOrganization(data: { name: string; inn: string; mode?: string; vat_payer?: boolean }): Promise<Organization> {
    const res = await authFetch(`${API_BASE}/organizations`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Tashkilot yaratishda xatolik");
    }
    appCache.invalidateTags(["organizations"]);
    return res.json();
  },

  async resetOrganizationData(orgId: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/organizations/${orgId}/reset-data`, {
      method: "POST",
      headers: getHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Tashkilot ma'lumotlarini tozalashda xatolik");
    }
    appCache.invalidateAll();
    return res.json();
  },

  async factoryResetSystem(confirmation: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/system/factory-reset`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ confirmation }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Tizimni noldan tozalashda xatolik");
    }
    appCache.invalidateAll();
    return res.json();
  },

  async toggleOrganizationMode(orgId: string, mode: "SIMPLE" | "BHMS"): Promise<Organization> {
    const res = await authFetch(`${API_BASE}/organizations/${orgId}/mode`, {
      method: "PATCH",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ mode }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Rejimni o'zgartirib bo'lmadi");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  async lockOrganizationPeriod(orgId: string, lockedUntilDate: string | null): Promise<Organization> {
    const res = await authFetch(`${API_BASE}/organizations/${orgId}/lock-period`, {
      method: "PATCH",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ locked_until_date: lockedUntilDate }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Davrni qulflashda xatolik yuz berdi");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  async getAuditLogs(orgId: string, limit: number = 30): Promise<AuditLog[]> {
    const res = await authFetch(`${API_BASE}/organizations/${orgId}/audit-logs?limit=${limit}`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Audit jurnali yuklanmadi");
    return res.json();
  },

  async getTaxRules(): Promise<TaxRule[]> {
    const res = await authFetch(`${API_BASE}/organizations/tax/rules`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Soliq qoidalari yuklanmadi");
    return res.json();
  },

  async stornoTransaction(orgId: string, txId: string, reason: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/organizations/${orgId}/transactions/${txId}/storno`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Storno qilishda xatolik yuz berdi");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  // Dashboard with Caching
  async getDashboardKPIs(orgId: string, forceFresh: boolean = false): Promise<DashboardKPIs> {
    const cacheKey = `kpis:${orgId}`;
    if (!forceFresh) {
      const cached = appCache.get<DashboardKPIs>(cacheKey);
      if (cached) return cached;
    }

    const res = await authFetch(`${API_BASE}/reports/dashboard?organization_id=${orgId}`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("KPI ko'rsatkichlarini yuklab bo'lmadi");
    const data = await res.json();
    appCache.set(cacheKey, data, 30, ["kpis"]);
    return data;
  },

  // Reports with Caching
  async getOborotka(
    orgId: string,
    fromDate: string,
    toDate: string,
    accountFilter?: string,
    forceFresh: boolean = false
  ): Promise<TrialBalanceReport> {
    const cacheKey = `oborotka:${orgId}:${fromDate}:${toDate}:${accountFilter || ""}`;
    if (!forceFresh) {
      const cached = appCache.get<TrialBalanceReport>(cacheKey);
      if (cached) return cached;
    }

    let url = `${API_BASE}/reports/oborotka?organization_id=${orgId}&from_date=${fromDate}&to_date=${toDate}`;
    if (accountFilter) url += `&account_filter=${accountFilter}`;
    const res = await authFetch(url, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Oborotka hisobotini yuklab bo'lmadi");
    const data = await res.json();
    appCache.set(cacheKey, data, 45, ["reports"]);
    return data;
  },

  async getMaterialReport(
    orgId: string,
    fromDate: string,
    toDate: string,
    itemId?: string,
    forceFresh: boolean = false
  ): Promise<MaterialReport> {
    const cacheKey = `material:${orgId}:${fromDate}:${toDate}:${itemId || ""}`;
    if (!forceFresh) {
      const cached = appCache.get<MaterialReport>(cacheKey);
      if (cached) return cached;
    }

    let url = `${API_BASE}/reports/material-report?organization_id=${orgId}&from_date=${fromDate}&to_date=${toDate}`;
    if (itemId) url += `&item_id=${itemId}`;
    const res = await authFetch(url, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Moddiy hisobotni yuklab bo'lmadi");
    const data = await res.json();
    appCache.set(cacheKey, data, 45, ["reports"]);
    return data;
  },

  async getAktSverka(
    orgId: string,
    counterpartyId: string,
    fromDate: string,
    toDate: string,
    forceFresh: boolean = false
  ): Promise<AktSverkaReport> {
    const cacheKey = `sverka:${orgId}:${counterpartyId}:${fromDate}:${toDate}`;
    if (!forceFresh) {
      const cached = appCache.get<AktSverkaReport>(cacheKey);
      if (cached) return cached;
    }

    const url = `${API_BASE}/reports/akt-sverka?organization_id=${orgId}&counterparty_id=${counterpartyId}&from_date=${fromDate}&to_date=${toDate}`;
    const res = await authFetch(url, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Akt sverkani yuklab bo'lmadi");
    const data = await res.json();
    appCache.set(cacheKey, data, 45, ["reports"]);
    return data;
  },

  // Counterparties
  async getCounterparties(orgId: string) {
    const res = await authFetch(`${API_BASE}/counterparties?organization_id=${orgId}`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Kontragentlarni yuklab bo'lmadi");
    return res.json();
  },

  // Documents ETL
  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await authFetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    });
    if (!res.ok) throw new Error("Faylni yuklashda xatolik yuz berdi");
    return res.json();
  },

  async previewMapping(fileId: string) {
    const formData = new FormData();
    formData.append("file_id", fileId);
    const res = await authFetch(`${API_BASE}/documents/preview-mapping`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    });
    if (!res.ok) throw new Error("Ustunlarni tahlil qilishda xatolik");
    return res.json();
  },

  async commitDocument(payload: {
    file_id: string;
    organization_id: string;
    format_type: string;
    mapping?: ColumnMapping;
    doc_type?: string;
    operation_type?: string;
    default_debit_account?: string;
    default_credit_account?: string;
  }) {
    const res = await authFetch(`${API_BASE}/documents/commit`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Amallarni bazaga kiritib bo'lmadi");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  async commitDocumentAsync(payload: {
    file_id: string;
    organization_id: string;
    format_type: string;
    mapping?: ColumnMapping;
    doc_type?: string;
    operation_type?: string;
    default_debit_account?: string;
    default_credit_account?: string;
  }): Promise<AsyncCommitResponse> {
    const res = await authFetch(`${API_BASE}/documents/commit-async`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Asinxron importni boshlab bo'lmadi");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  // PDF Extraction & Excel Export
  async previewPdfExtraction(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await authFetch(`${API_BASE}/documents/pdf-preview`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "PDF tahlilida xatolik yuz berdi");
    }
    return res.json();
  },

  async exportPdfToExcel(file: File): Promise<Blob> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await authFetch(`${API_BASE}/documents/pdf-to-excel`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "PDF dan Excel yaratib bo'lmadi");
    }
    return res.blob();
  },

  // Background Task Management
  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const res = await authFetch(`${API_BASE}/tasks/${taskId}`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Vazifa holatini olib bo'lmadi");
    return res.json();
  },

  // AI Chat
  async askAI(query: string, reportContext: any = {}) {
    const res = await authFetch(`${API_BASE}/ai/chat`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ query, report_context: reportContext }),
    });
    if (!res.ok) throw new Error("AI tahlilchidan javob olib bo'lmadi");
    return res.json();
  },

  // External Integrations (Didox & Soliq)
  async getIntegrationsStatus(): Promise<IntegrationStatusResponse> {
    const res = await authFetch(`${API_BASE}/integrations/status`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Integratsiya holatini yuklab bo'lmadi");
    return res.json();
  },

  async syncDidox(payload: { organization_id: string; api_token?: string; from_date?: string }): Promise<SyncResponse> {
    const res = await authFetch(`${API_BASE}/integrations/didox/sync`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Didox bilan sinxronlashda xatolik");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  async syncSoliq(payload: { organization_id: string; nkm_serial?: string; from_date?: string }): Promise<SyncResponse> {
    const res = await authFetch(`${API_BASE}/integrations/soliq/sync`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Soliq.uz bilan sinxronlashda xatolik");
    }
    appCache.invalidateTags(["reports", "kpis", "organizations"]);
    return res.json();
  },

  // Automated Backup Engine
  async createBackup(organizationId?: string): Promise<BackupCreateResponse> {
    const res = await authFetch(`${API_BASE}/backup/create`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(organizationId ? { organization_id: organizationId } : {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Zaxira nusxasini yaratib bo'lmadi");
    }
    return res.json();
  },

  async listBackups(): Promise<BackupItem[]> {
    const res = await authFetch(`${API_BASE}/backup/list`, {
      headers: getHeaders(),
    });
    if (!res.ok) throw new Error("Zaxira nusxalar ro'yxatini yuklab bo'lmadi");
    return res.json();
  },

  async verifyBackup(filename: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/backup/${filename}/verify`, {
      headers: getHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Zaxira faylini tekshirib bo'lmadi");
    }
    return res.json();
  },

  getBackupDownloadUrl(filename: string): string {
    return `${API_BASE}/backup/${encodeURIComponent(filename)}/download`;
  },

  // Export Download URL
  getExportUrl(format: "xlsx" | "pdf", reportType: "oborotka" | "material" | "sverka", params: Record<string, string>): string {
    const query = new URLSearchParams(params).toString();
    return `${API_BASE}/reports/export/${format}?report_type=${reportType}&${query}`;
  },

  // OCR Excel Export (Aslidek Faktura)
  async exportOCRExcel(doc: any): Promise<Blob> {
    const res = await authFetch(`${API_BASE}/ocr/export-excel`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(doc),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Excel formatiga o'tkazishda xatolik yuz berdi");
    }
    return res.blob();
  },

  // Tax Audit OCR & Formatted Excel Export
  async parseTaxAuditDocument(file: File): Promise<TaxAuditDocument> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await authFetch(`${API_BASE}/ocr/tax-audit/parse`, {
      method: "POST",
      headers: getHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Soliq tahlili hujjatini tahlil qilishda xatolik yuz berdi");
    }
    return res.json();
  },

  async exportTaxAuditExcel(doc: TaxAuditDocument): Promise<Blob> {
    const res = await authFetch(`${API_BASE}/ocr/tax-audit/export-excel`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(doc),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Soliq tahlili Excel faylini yaratishda xatolik yuz berdi");
    }
    return res.blob();
  },
};
