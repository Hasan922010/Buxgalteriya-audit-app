"use client";

import React, { useState, useEffect, useMemo } from "react";
import { AuthDownloadLink } from "@/components/auth-download-link";
import { apiClient } from "@/lib/api-client";
import { TrialBalanceReport, TrialBalanceItem } from "@/types/accounting";
import { VirtualDataTable } from "@/components/data-table/virtual-data-table";
import { formatCurrency } from "@/lib/utils";
import { useOrg } from "@/lib/org-context";
import { ColumnDef } from "@tanstack/react-table";
import {
  FileSpreadsheet,
  FileText,
  Search,
  Calendar,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";

export default function OborotkaPage() {
  const { currentOrg, setReportContext } = useOrg();
  const [fromDate, setFromDate] = useState("2025-01-01");
  const [toDate, setToDate] = useState("2025-12-31");
  const [search, setSearch] = useState("");
  const [report, setReport] = useState<TrialBalanceReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    apiClient
      .getOborotka(currentOrg.id, fromDate, toDate)
      .then((data) => {
        setReport(data);
        setReportContext(data);
      })
      .catch((err) => console.error("OSV xatosi:", err))
      .finally(() => setLoading(false));
  }, [currentOrg, fromDate, toDate, setReportContext]);

  const filteredItems = useMemo(() => {
    if (!report?.items) return [];
    if (!search.trim()) return report.items;
    const s = search.toLowerCase();
    return report.items.filter(
      (it) =>
        it.account_code.toLowerCase().includes(s) ||
        it.account_name.toLowerCase().includes(s)
    );
  }, [report, search]);

  const columns = useMemo<ColumnDef<TrialBalanceItem>[]>(
    () => [
      {
        accessorKey: "account_code",
        header: "Schot",
        cell: (info) => (
          <span className="font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
            {info.getValue() as string}
          </span>
        ),
      },
      {
        accessorKey: "account_name",
        header: "Schot nomi",
        cell: (info) => (
          <span className="font-medium text-slate-800">
            {info.getValue() as string}
          </span>
        ),
      },
      {
        accessorKey: "initial_debit",
        header: "Bosh Dt",
        cell: (info) => (
          <span className="text-right block font-mono">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
      {
        accessorKey: "initial_credit",
        header: "Bosh Kt",
        cell: (info) => (
          <span className="text-right block font-mono">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
      {
        accessorKey: "turnover_debit",
        header: "Oborot Dt",
        cell: (info) => (
          <span className="text-right block font-mono text-emerald-700 font-semibold">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
      {
        accessorKey: "turnover_credit",
        header: "Oborot Kt",
        cell: (info) => (
          <span className="text-right block font-mono text-rose-700 font-semibold">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
      {
        accessorKey: "final_debit",
        header: "Oxirgi Dt",
        cell: (info) => (
          <span className="text-right block font-mono font-semibold">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
      {
        accessorKey: "final_credit",
        header: "Oxirgi Kt",
        cell: (info) => (
          <span className="text-right block font-mono font-semibold">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
    ],
    []
  );

  const totalSummary = report && (
    <div className="grid grid-cols-8 text-right gap-2 items-center text-xs">
      <div className="col-span-2 text-left font-bold text-slate-900 uppercase">
        JAMI BALANS YIG'INDISI:
      </div>
      <div className="font-mono">{formatCurrency(report.total_initial_debit)}</div>
      <div className="font-mono">{formatCurrency(report.total_initial_credit)}</div>
      <div className="font-mono text-emerald-800">{formatCurrency(report.total_turnover_debit)}</div>
      <div className="font-mono text-rose-800">{formatCurrency(report.total_turnover_credit)}</div>
      <div className="font-mono">{formatCurrency(report.total_final_debit)}</div>
      <div className="font-mono">{formatCurrency(report.total_final_credit)}</div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header and Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Aylanma Qoldiq Vedomosti (OSV)
            </h2>
            {report && (
              <span
                className={`flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                  report.is_balanced
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-rose-50 text-rose-700 border-rose-200"
                }`}
              >
                {report.is_balanced ? (
                  <>
                    <CheckCircle className="w-3.5 h-3.5" />
                    <span>Balans teng</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Balansda nomutanosiblik</span>
                  </>
                )}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            BHMS ikkiyoqlama yozuv tamoyili asosidagi sintetik schotlar harakati
          </p>
        </div>

        {/* Export Buttons */}
        <div className="flex items-center gap-2">
          {currentOrg && (
            <>
              <AuthDownloadLink
                href={apiClient.getExportUrl("xlsx", "oborotka", {
                  organization_id: currentOrg.id,
                  from_date: fromDate,
                  to_date: toDate,
                })}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <FileSpreadsheet className="w-4 h-4" />
                <span>Excel yuklab olish</span>
              </AuthDownloadLink>

              <AuthDownloadLink
                href={apiClient.getExportUrl("pdf", "oborotka", {
                  organization_id: currentOrg.id,
                  from_date: fromDate,
                  to_date: toDate,
                })}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <FileText className="w-4 h-4" />
                <span>PDF chop etish</span>
              </AuthDownloadLink>
            </>
          )}
        </div>
      </div>

      {/* Multi-Criteria Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center gap-4">
        {/* Date pickers */}
        <div className="flex items-center gap-2 text-xs">
          <Calendar className="w-4 h-4 text-slate-400" />
          <span className="text-slate-500 font-medium">Davr:</span>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
          />
          <span className="text-slate-400">-</span>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
          />
        </div>

        {/* Account search */}
        <div className="flex-1 min-w-[200px] relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Schot kodi yoki nomi bo'yicha qidirish (masalan, 2900)..."
            className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
          />
        </div>
      </div>

      {/* Virtualized TanStack Grid */}
      <VirtualDataTable
        data={filteredItems}
        columns={columns}
        totalSummaryRow={totalSummary}
        height="520px"
      />
    </div>
  );
}
