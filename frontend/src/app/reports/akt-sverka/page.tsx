"use client";

import React, { useState, useEffect } from "react";
import { AuthDownloadLink } from "@/components/auth-download-link";
import { apiClient } from "@/lib/api-client";
import { AktSverkaReport } from "@/types/accounting";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useOrg } from "@/lib/org-context";
import {
  FileCheck2,
  FileText,
  Calendar,
  Building2,
  CheckCircle2,
} from "lucide-react";

export default function AktSverkaPage() {
  const { currentOrg, setReportContext } = useOrg();
  const [fromDate, setFromDate] = useState("2025-01-01");
  const [toDate, setToDate] = useState("2025-12-31");
  const [counterparties, setCounterparties] = useState<any[]>([]);
  const [selectedCpId, setSelectedCpId] = useState<string>("");
  const [report, setReport] = useState<AktSverkaReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (currentOrg) {
      apiClient.getCounterparties(currentOrg.id).then((cps) => {
        setCounterparties(cps);
        if (cps.length > 0) setSelectedCpId(cps[0].id);
      });
    }
  }, [currentOrg]);

  useEffect(() => {
    if (!currentOrg || !selectedCpId) return;
    setLoading(true);
    apiClient
      .getAktSverka(currentOrg.id, selectedCpId, fromDate, toDate)
      .then((data) => {
        setReport(data);
        setReportContext(data);
      })
      .catch((err) => console.error("Akt sverka xatosi:", err))
      .finally(() => setLoading(false));
  }, [currentOrg, selectedCpId, fromDate, toDate, setReportContext]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            O'zaro Hisob-Kitoblar Solishtirma Dalolatnomasi (Akt Sverka)
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Hamkorlar bilan yetkazib berilgan tovarlar va o'tkazilgan to'lovlar balansi
          </p>
        </div>

        {/* PDF Export */}
        {currentOrg && selectedCpId && (
          <AuthDownloadLink
            href={apiClient.getExportUrl("pdf", "sverka", {
              organization_id: currentOrg.id,
              counterparty_id: selectedCpId,
              from_date: fromDate,
              to_date: toDate,
            })}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <FileText className="w-4 h-4" />
            <span>PDF chop etish</span>
          </AuthDownloadLink>
        )}
      </div>

      {/* Filter and Counterparty selector */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 text-xs">
          <Building2 className="w-4 h-4 text-slate-400" />
          <span className="text-slate-500 font-medium">Kontragent:</span>
          <select
            value={selectedCpId}
            onChange={(e) => setSelectedCpId(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 bg-slate-50 focus:outline-hidden focus:border-blue-500 font-medium"
          >
            {counterparties.map((cp) => (
              <option key={cp.id} value={cp.id}>
                {cp.name} (STIR: {cp.inn || "Mavjud emas"})
              </option>
            ))}
          </select>
        </div>

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
      </div>

      {/* Uzbek Legal Conclusion Banner */}
      {report && (
        <div
          className={`p-4 rounded-2xl text-xs font-semibold flex items-center justify-between border ${
            report.final_debt > 0
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : report.final_debt < 0
              ? "bg-amber-50 text-amber-800 border-amber-200"
              : "bg-blue-50 text-blue-800 border-blue-200"
          }`}
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Yakuniy xulosa: {report.status_uz}</span>
          </div>
          <div className="font-mono font-bold text-sm">
            {formatCurrency(Math.abs(report.final_debt))}
          </div>
        </div>
      )}

      {/* Table of operations */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-slate-900 text-white">
            <tr>
              <th className="p-3">Sana</th>
              <th className="p-3">Hujjat #</th>
              <th className="p-3">Amal mazmuni</th>
              <th className="p-3 text-right">Debet (Bizning haqimiz)</th>
              <th className="p-3 text-right">Kredit (To'lov/Kirim)</th>
              <th className="p-3 text-right">Joriy Qoldiq</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {/* Opening row */}
            {report && (
              <tr className="bg-slate-50/80 font-semibold">
                <td className="p-3 font-mono">{formatDate(report.from_date)}</td>
                <td className="p-3">-</td>
                <td className="p-3 text-slate-500">Boshlang'ich qoldiq</td>
                <td className="p-3 text-right font-mono">-</td>
                <td className="p-3 text-right font-mono">-</td>
                <td className="p-3 text-right font-mono">
                  {formatCurrency(report.initial_debt)}
                </td>
              </tr>
            )}

            {/* In-period rows */}
            {report?.items.map((it, idx) => (
              <tr key={idx} className="hover:bg-blue-50/40 transition-colors">
                <td className="p-3 font-mono text-slate-500">{formatDate(it.date)}</td>
                <td className="p-3 font-medium text-slate-800">{it.doc_number}</td>
                <td className="p-3 text-slate-600">{it.description}</td>
                <td className="p-3 text-right font-mono text-emerald-700 font-medium">
                  {it.debit > 0 ? formatCurrency(it.debit) : "-"}
                </td>
                <td className="p-3 text-right font-mono text-rose-700 font-medium">
                  {it.credit > 0 ? formatCurrency(it.credit) : "-"}
                </td>
                <td className="p-3 text-right font-mono font-semibold">
                  {formatCurrency(it.running_balance)}
                </td>
              </tr>
            ))}

            {(!report || report.items.length === 0) && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-400">
                  Ushbu davrda o'zaro amallar mavjud emas.
                </td>
              </tr>
            )}
          </tbody>

          {/* Footer Total */}
          {report && (
            <tfoot className="bg-slate-100 border-t-2 border-slate-300 font-bold text-slate-900">
              <tr>
                <td colSpan={3} className="p-3 uppercase">
                  JAMI DAVR OBOROTI:
                </td>
                <td className="p-3 text-right font-mono text-emerald-800">
                  {formatCurrency(report.total_debit)}
                </td>
                <td className="p-3 text-right font-mono text-rose-800">
                  {formatCurrency(report.total_credit)}
                </td>
                <td className="p-3 text-right font-mono text-blue-900 font-bold">
                  {formatCurrency(report.final_debt)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
