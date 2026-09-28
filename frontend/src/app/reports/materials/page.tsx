"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { AuthDownloadLink } from "@/components/auth-download-link";
import { apiClient } from "@/lib/api-client";
import { MaterialReport, MaterialReportItem, MaterialReportMxikGroup } from "@/types/accounting";
import { VirtualDataTable } from "@/components/data-table/virtual-data-table";
import { formatCurrency, formatQuantity } from "@/lib/utils";
import { useOrg } from "@/lib/org-context";
import { FileUploader } from "@/components/file-uploader";
import { ColumnDef } from "@tanstack/react-table";
import {
  FileSpreadsheet,
  FileText,
  Search,
  Calendar,
  Layers,
  Package,
  UploadCloud,
  X,
  Copy,
  Check,
  RefreshCw,
  ArrowUpRight,
  TrendingDown,
  TrendingUp,
  Tag,
  Boxes,
  ExternalLink,
} from "lucide-react";

export default function MaterialsPage() {
  const { currentOrg, setReportContext } = useOrg();
  const [fromDate, setFromDate] = useState("2025-01-01");
  const [toDate, setToDate] = useState("2026-12-31");
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"mxik" | "items">("mxik");
  const [report, setReport] = useState<MaterialReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [filterMxik, setFilterMxik] = useState<string | null>(null);

  const fetchReport = useCallback(
    (forceFresh: boolean = false) => {
      if (!currentOrg) return;
      setLoading(true);
      apiClient
        .getMaterialReport(currentOrg.id, fromDate, toDate, undefined, forceFresh)
        .then((data) => {
          setReport(data);
          setReportContext(data);
        })
        .catch((err) => console.error("Moddiy hisobot xatosi:", err))
        .finally(() => setLoading(false));
    },
    [currentOrg, fromDate, toDate, setReportContext]
  );

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(text);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  // Filtered MXIK groups
  const filteredMxikGroups = useMemo(() => {
    if (!report?.mxik_groups) return [];
    if (!search.trim()) return report.mxik_groups;
    const s = search.toLowerCase();
    return report.mxik_groups.filter(
      (g) =>
        g.ikpu_code.toLowerCase().includes(s) ||
        (g.ikpu_name && g.ikpu_name.toLowerCase().includes(s))
    );
  }, [report?.mxik_groups, search]);

  // Filtered Items
  const filteredItems = useMemo(() => {
    if (!report?.items) return [];
    let items = report.items;
    if (filterMxik) {
      items = items.filter((it) => (it.ikpu_code || "NO_IKPU") === filterMxik);
    }
    if (!search.trim()) return items;
    const s = search.toLowerCase();
    return items.filter(
      (it) =>
        it.item_name.toLowerCase().includes(s) ||
        (it.ikpu_code && it.ikpu_code.toLowerCase().includes(s))
    );
  }, [report?.items, filterMxik, search]);

  // Columns for MXIK Grouped Report
  const mxikColumns = useMemo<ColumnDef<MaterialReportMxikGroup>[]>(
    () => [
      {
        accessorKey: "ikpu_code",
        header: "MXIK (IKPU) Kodi",
        cell: (info) => {
          const row = info.row.original;
          const isCopied = copiedCode === row.ikpu_code;
          return (
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded-md border border-slate-200 transition-colors">
                {row.ikpu_code}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  copyToClipboard(row.ikpu_code);
                }}
                title="MXIK kodini nusxalash"
                className="text-slate-400 hover:text-blue-600 transition-colors p-1"
              >
                {isCopied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          );
        },
      },
      {
        accessorKey: "ikpu_name",
        header: "Mahsulotlar Toifasi / Tovar Namunasi",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div>
              <div className="font-semibold text-slate-900 text-xs">
                {row.ikpu_name || "Nomsiz toifa"}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="inline-flex items-center gap-1 text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.2 rounded-full border border-blue-200">
                  <Package className="w-2.5 h-2.5" />
                  {row.items_count} ta tovar
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  Birlik: {row.unit || "dona"}
                </span>
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "initial_sum",
        header: "Boshlang'ich Qoldiq",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-slate-800 text-xs">
                {formatQuantity(row.initial_qty, row.unit)}
              </div>
              <div className="text-[10px] text-slate-500 font-mono">
                {formatCurrency(row.initial_sum)}
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "inflow_sum",
        header: "Jami Kirim",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-emerald-700 font-semibold text-xs">
                +{formatQuantity(row.inflow_qty, row.unit)}
              </div>
              <div className="text-[10px] text-emerald-600 font-mono font-medium">
                {formatCurrency(row.inflow_sum)}
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "outflow_sum",
        header: "Jami Chiqim",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-rose-700 font-semibold text-xs">
                -{formatQuantity(row.outflow_qty, row.unit)}
              </div>
              <div className="text-[10px] text-rose-600 font-mono font-medium">
                {formatCurrency(row.outflow_sum)}
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "final_sum",
        header: "Jami Yakuniy Qoldiq",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-blue-700 font-bold text-xs">
                {formatQuantity(row.final_qty, row.unit)}
              </div>
              <div className="text-[10px] text-blue-600 font-mono font-semibold">
                {formatCurrency(row.final_sum)}
              </div>
            </div>
          );
        },
      },
      {
        id: "actions",
        header: "",
        cell: (info) => {
          const row = info.row.original;
          return (
            <button
              onClick={() => {
                setFilterMxik(row.ikpu_code);
                setActiveTab("items");
              }}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2 py-1 rounded-lg transition-colors"
            >
              <span>Tovarlar</span>
              <ArrowUpRight className="w-3 h-3" />
            </button>
          );
        },
      },
    ],
    [copiedCode]
  );

  // Columns for Individual Items Report
  const itemColumns = useMemo<ColumnDef<MaterialReportItem>[]>(
    () => [
      {
        accessorKey: "item_name",
        header: "Mahsulot nomi",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div>
              <div className="font-semibold text-slate-900 text-xs">{row.item_name}</div>
              {row.ikpu_code && (
                <div className="text-[10px] text-slate-400 font-mono">
                  MXIK: {row.ikpu_code} ({row.unit})
                </div>
              )}
            </div>
          );
        },
      },
      {
        accessorKey: "initial_qty",
        header: "Boshlang'ich Qoldiq",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-slate-800 text-xs">
                {formatQuantity(row.initial_qty, row.unit)}
              </div>
              <div className="text-[10px] text-slate-500 font-mono">
                {formatCurrency(row.initial_sum)}
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "inflow_qty",
        header: "Kirim",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-emerald-700 font-semibold text-xs">
                +{formatQuantity(row.inflow_qty, row.unit)}
              </div>
              <div className="text-[10px] text-emerald-600 font-mono">
                {formatCurrency(row.inflow_sum)}
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "outflow_qty",
        header: "Chiqim",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className="font-mono text-rose-700 font-semibold text-xs">
                -{formatQuantity(row.outflow_qty, row.unit)}
              </div>
              <div className="text-[10px] text-rose-600 font-mono">
                {formatCurrency(row.outflow_sum)}
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "avg_price",
        header: "O'rtacha Tannarx",
        cell: (info) => (
          <span className="text-right block font-mono font-semibold text-slate-800 text-xs">
            {formatCurrency(info.getValue() as number)}
          </span>
        ),
      },
      {
        accessorKey: "final_qty",
        header: "Oxirgi Qoldiq",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="text-right">
              <div className={`font-mono font-bold text-xs ${row.has_negative_stock ? "text-rose-700" : "text-blue-700"}`}>
                {formatQuantity(row.final_qty, row.unit)}
              </div>
              <div className="text-[10px] text-blue-600 font-mono font-semibold">
                {formatCurrency(row.final_sum)}
              </div>
              {row.has_negative_stock && (
                <div
                  className="text-[10px] font-semibold text-rose-700"
                  title="Chiqim kirimdan oshib ketgan: kirim hujjatlari yetishmayapti bo'lishi mumkin"
                >
                  Manfiy qoldiq
                </div>
              )}
            </div>
          );
        },
      },
    ],
    []
  );

  const totalSummary = report && (
    <div className="grid grid-cols-6 text-right gap-2 items-center text-xs">
      <div className="col-span-1 text-left font-bold text-slate-900 uppercase">
        JAMI TOVARLAR QIYMATI:
      </div>
      <div className="font-mono font-semibold text-slate-800">{formatCurrency(report.total_initial_sum)}</div>
      <div className="font-mono text-emerald-800 font-semibold">{formatCurrency(report.total_inflow_sum)}</div>
      <div className="font-mono text-rose-800 font-semibold">{formatCurrency(report.total_outflow_sum)}</div>
      <div></div>
      <div className="font-mono text-blue-900 font-bold">{formatCurrency(report.total_final_sum)}</div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header and Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Moddiy Hisobot (Ombor va Tovar Harakati)
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              BHMS №4 (O'rtacha tannarx)
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              MXIK Jamlama integratsiyasi
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Har bir MXIK kodi va alohida tovarlar bo'yicha: Boshlang'ich qoldiq, Kirim, Chiqim va Yakuniy Qoldiq hisoboti
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Import Document Button */}
          <button
            onClick={() => setImportModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-xs transition-colors"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Hujjat Import Qilish (Excel / PDF)</span>
          </button>

          {/* Refresh Fresh */}
          <button
            onClick={() => fetchReport(true)}
            disabled={loading}
            title="Hisobotni yangilash"
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors shadow-xs disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          {/* Export Buttons */}
          {currentOrg && (
            <>
              <AuthDownloadLink
                href={apiClient.getExportUrl("xlsx", "material", {
                  organization_id: currentOrg.id,
                  from_date: fromDate,
                  to_date: toDate,
                })}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <FileSpreadsheet className="w-4 h-4" />
                <span>Excel (MXIK bilan)</span>
              </AuthDownloadLink>

              <AuthDownloadLink
                href={apiClient.getExportUrl("pdf", "material", {
                  organization_id: currentOrg.id,
                  from_date: fromDate,
                  to_date: toDate,
                  mode: activeTab === "mxik" ? "mxik" : "items",
                })}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <FileText className="w-4 h-4" />
                <span>PDF ({activeTab === "mxik" ? "MXIK Jamlama" : "Tovarlar"})</span>
              </AuthDownloadLink>
            </>
          )}
        </div>
      </div>

      {/* KPI Cards Overview */}
      {report && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-[11px] font-medium">
              <span>Faol MXIK toifalari</span>
              <Layers className="w-3.5 h-3.5 text-blue-600" />
            </div>
            <div className="text-lg font-bold text-slate-900 mt-1">
              {report.mxik_groups ? report.mxik_groups.length : 0} ta
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Jami {report.items.length} ta mahsulot
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-[11px] font-medium">
              <span>Boshlang'ich qoldiq</span>
              <Boxes className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="text-base font-bold text-slate-800 mt-1 font-mono">
              {formatCurrency(report.total_initial_sum)}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">Davr boshiga zaxira</div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-emerald-100 shadow-xs bg-emerald-50/20">
            <div className="flex items-center justify-between text-emerald-700 text-[11px] font-medium">
              <span>Jami Kirim</span>
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div className="text-base font-bold text-emerald-700 mt-1 font-mono">
              +{formatCurrency(report.total_inflow_sum)}
            </div>
            <div className="text-[10px] text-emerald-600 mt-0.5">EHF & fakturalar</div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-rose-100 shadow-xs bg-rose-50/20">
            <div className="flex items-center justify-between text-rose-700 text-[11px] font-medium">
              <span>Jami Chiqim</span>
              <TrendingDown className="w-3.5 h-3.5 text-rose-600" />
            </div>
            <div className="text-base font-bold text-rose-700 mt-1 font-mono">
              -{formatCurrency(report.total_outflow_sum)}
            </div>
            <div className="text-[10px] text-rose-600 mt-0.5">Sotuv & realizatsiya</div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-blue-200 shadow-xs bg-blue-50/30 col-span-2 md:col-span-1">
            <div className="flex items-center justify-between text-blue-700 text-[11px] font-medium">
              <span>Jami Yakuniy Qoldiq</span>
              <Package className="w-3.5 h-3.5 text-blue-600" />
            </div>
            <div className="text-base font-bold text-blue-700 mt-1 font-mono">
              {formatCurrency(report.total_final_sum)}
            </div>
            <div className="text-[10px] text-blue-600 mt-0.5">Omborda mavjud tovarlar</div>
          </div>
        </div>
      )}

      {/* Tabs and Multi-Criteria Filter Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          {/* Tabs */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => {
                setActiveTab("mxik");
                setFilterMxik(null);
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === "mxik"
                  ? "bg-white text-blue-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Har bir MXIK bo'yicha Jamlama</span>
              {report?.mxik_groups && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 text-blue-700">
                  {report.mxik_groups.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("items")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === "items"
                  ? "bg-white text-blue-700 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Package className="w-3.5 h-3.5" />
              <span>Barcha tovarlar kesimida (Batafsil)</span>
              {report?.items && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-slate-200 text-slate-700">
                  {filteredItems.length}
                </span>
              )}
            </button>
          </div>

          {/* Active MXIK Filter Badge (if any) */}
          {filterMxik && (
            <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 text-blue-700 px-2.5 py-1 rounded-lg text-xs">
              <span className="font-medium">Tanlangan MXIK:</span>
              <span className="font-mono font-bold">{filterMxik}</span>
              <button
                onClick={() => setFilterMxik(null)}
                className="hover:text-rose-600 transition-colors ml-1"
                title="Filtrni tozalash"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Filter inputs */}
        <div className="flex flex-wrap items-center gap-4">
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

          <div className="flex-1 min-w-[220px] relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={
                activeTab === "mxik"
                  ? "MXIK kodi yoki toifa nomi bo'yicha qidirish..."
                  : "Mahsulot nomi yoki MXIK bo'yicha qidirish..."
              }
              className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Table Section */}
      {activeTab === "mxik" ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-500 px-1">
            <span>
              Jami ko'rsatilmoqda: <b>{filteredMxikGroups.length}</b> ta MXIK toifasi
            </span>
            <span className="text-slate-400">
              Tovarlarni ko'rish uchun "Tovarlar" tugmasini bosing
            </span>
          </div>
          <VirtualDataTable
            data={filteredMxikGroups}
            columns={mxikColumns}
            totalSummaryRow={totalSummary}
            height="540px"
          />
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-500 px-1">
            <span>
              Jami ko'rsatilmoqda: <b>{filteredItems.length}</b> ta alohida mahsulot pozitsiyasi
            </span>
            {filterMxik && (
              <button
                onClick={() => setFilterMxik(null)}
                className="text-xs text-blue-600 hover:underline font-medium"
              >
                Barcha MXIK larni ko'rsatish
              </button>
            )}
          </div>
          <VirtualDataTable
            data={filteredItems}
            columns={itemColumns}
            totalSummaryRow={totalSummary}
            height="540px"
          />
        </div>
      )}

      {/* Scanned Document & Excel Import Modal */}
      {importModalOpen && currentOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-3xl w-full border border-slate-200 shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto">
            {/* Close Button */}
            <button
              onClick={() => setImportModalOpen(false)}
              className="absolute top-5 right-5 p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Modal Header */}
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-inner">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Hujjat Import Qilish (Excel & Skaner qilingan PDF)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Skaner qilingan PDF, Didox elektron schyot-faktura yoki Excel tovar hisobotidagi ma'lumotlarni omborga avtomatik yuklash
                </p>
              </div>
            </div>

            {/* Embedded Full Feature File Uploader with Live Progress */}
            <FileUploader
              organizationId={currentOrg.id}
              onSuccess={() => {
                fetchReport(true);
                setTimeout(() => {
                  setImportModalOpen(false);
                }, 1500);
              }}
            />

            <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
              <span>Qo'llab-quvvatlanadi: .pdf (skaner/faktura), .xlsx, .xls, .csv</span>
              <button
                onClick={() => setImportModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Yopish
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
