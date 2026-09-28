"use client";

import React, { useState, useMemo } from "react";
import { API_BASE, authFetch } from "@/lib/auth";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  RefreshCw,
  Send,
  FileText,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  ShieldAlert,
  X,
  ArrowLeft,
  DollarSign,
  Scale,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useOrg } from "@/lib/org-context";
import {
  TaxAuditDocument,
  TaxAuditItemRow,
  TaxPenaltySummary,
} from "@/types/accounting";

export interface OCRLineItem {
  item_name: string;
  ikpu_code?: string;
  unit: string;
  quantity: number;
  price: number;
  vat_rate: number;
  vat_amount: number;
  total_amount: number;
  confidence: number;
  status: "VALID" | "WARNING" | "ERROR";
  errors: string[];
  warnings: string[];
}

export interface OCRDocumentData {
  doc_number?: string;
  doc_date?: string;
  doc_type: string;
  supplier_name?: string;
  supplier_inn?: string;
  buyer_name?: string;
  buyer_inn?: string;
  contract_number?: string;
  contract_date?: string;
  overall_status: "VALID" | "WARNING" | "ERROR";
  errors: string[];
  warnings: string[];
  line_items: OCRLineItem[];
}

export interface VerificationWorkspaceProps {
  initialDocument?: OCRDocumentData | null;
  initialTaxAuditDoc?: TaxAuditDocument | null;
  previewImageBase64?: string;
  onCommitSuccess?: () => void;
  onReset?: () => void;
}

// Penalty calculation helper matching backend TaxAuditExtractor
function calculatePenalties(items: TaxAuditItemRow[]): TaxPenaltySummary {
  const total_discrepancy_amount = items.reduce(
    (acc, it) => acc + (Number(it.diff_amount) || 0),
    0
  );
  const vat_amount =
    Math.round(((total_discrepancy_amount * 0.12) / 1.12) * 100) / 100;
  const net_tax_base = Math.round((total_discrepancy_amount - vat_amount) * 100) / 100;
  const profit_tax_addition = Math.round(net_tax_base * 0.15 * 100) / 100;
  const financial_penalty = Math.round(total_discrepancy_amount * 0.2 * 100) / 100;
  const total_budget_liability =
    Math.round((vat_amount + profit_tax_addition + financial_penalty) * 100) / 100;

  return {
    total_discrepancy_amount,
    vat_amount,
    net_tax_base,
    profit_tax_addition,
    financial_penalty,
    total_budget_liability,
  };
}

export const VerificationWorkspace: React.FC<VerificationWorkspaceProps> = ({
  initialDocument,
  initialTaxAuditDoc,
  previewImageBase64,
  onCommitSuccess,
  onReset,
}) => {
  const { currentOrg } = useOrg();

  // Mode detection: Tax Audit vs Standard EHF
  const isTaxAudit = Boolean(initialTaxAuditDoc);

  // States for Standard EHF
  const [ehfDoc, setEhfDoc] = useState<OCRDocumentData | null>(
    initialDocument || null
  );

  // States for Tax Audit
  const [taxDoc, setTaxDoc] = useState<TaxAuditDocument | null>(
    initialTaxAuditDoc || null
  );

  // Common UI states
  const [zoom, setZoom] = useState<number>(100);
  const [page, setPage] = useState<number>(1);
  const [committing, setCommitting] = useState<boolean>(false);
  const [exportingExcel, setExportingExcel] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showPenaltyModal, setShowPenaltyModal] = useState<boolean>(false);

  // Zoom controls
  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 20, 250));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 20, 50));
  const handleZoomReset = () => setZoom(100);

  // ----------------------------------------------------
  // TAX AUDIT LOGIC
  // ----------------------------------------------------
  const discrepancyItemsCount = useMemo(() => {
    if (!taxDoc) return 0;
    return taxDoc.items.filter((i) => Number(i.diff_qty) > 0).length;
  }, [taxDoc]);

  const handleTaxAuditRecalculate = () => {
    if (!taxDoc) return;
    const updatedItems = taxDoc.items.map((item) => {
      let avg = Number(item.avg_price) || 0;
      const soldQ = Number(item.sold_qty) || 0;
      const soldAmt = Number(item.sold_amount) || 0;
      if (avg <= 0 && soldQ > 0 && soldAmt > 0) {
        avg = Math.round((soldAmt / soldQ) * 100) / 100;
      }

      const available =
        (Number(item.opening_qty) || 0) + (Number(item.inflow_qty) || 0);
      const calcDiffQty = Math.max(0, soldQ - available);
      const diffQty = item.diff_qty > 0 ? Number(item.diff_qty) : calcDiffQty;
      const expectedDiffAmt = Math.round(diffQty * avg * 100) / 100;
      const diffAmt =
        item.diff_amount > 0 ? Number(item.diff_amount) : expectedDiffAmt;
      const mathVerified = Math.abs(diffQty - calcDiffQty) < 0.05;

      return {
        ...item,
        avg_price: avg,
        diff_qty: diffQty,
        diff_amount: diffAmt,
        math_verified: mathVerified,
      };
    });

    const summary = calculatePenalties(updatedItems);
    setTaxDoc({
      ...taxDoc,
      items: updatedItems,
      summary,
    });
    setSuccessMessage("✅ Qatorlar matematikasi va soliq xatarlari qayta hisoblandi!");
  };

  const handleTaxItemChange = (
    index: number,
    field: keyof TaxAuditItemRow,
    value: any
  ) => {
    if (!taxDoc) return;
    const updated = [...taxDoc.items];
    const target = { ...updated[index], [field]: value };

    // Auto recalculate row discrepancy if quantities or prices changed
    if (
      field === "opening_qty" ||
      field === "inflow_qty" ||
      field === "sold_qty" ||
      field === "avg_price" ||
      field === "sold_amount"
    ) {
      const openQ = field === "opening_qty" ? Number(value) : Number(target.opening_qty) || 0;
      const infQ = field === "inflow_qty" ? Number(value) : Number(target.inflow_qty) || 0;
      const soldQ = field === "sold_qty" ? Number(value) : Number(target.sold_qty) || 0;
      let avgP = field === "avg_price" ? Number(value) : Number(target.avg_price) || 0;
      const soldA = field === "sold_amount" ? Number(value) : Number(target.sold_amount) || 0;

      if (avgP <= 0 && soldQ > 0 && soldA > 0) {
        avgP = Math.round((soldA / soldQ) * 100) / 100;
        target.avg_price = avgP;
      }

      const available = openQ + infQ;
      const calcDiffQ = Math.max(0, soldQ - available);
      target.diff_qty = calcDiffQ;
      target.diff_amount = Math.round(calcDiffQ * avgP * 100) / 100;
      target.math_verified = true;
    }

    updated[index] = target;
    const summary = calculatePenalties(updated);
    setTaxDoc({ ...taxDoc, items: updated, summary });
  };

  const handleDownloadTaxAuditExcel = async () => {
    if (!taxDoc) return;
    setExportingExcel(true);
    try {
      const blob = await apiClient.exportTaxAuditExcel(taxDoc);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeName = (taxDoc.company_name || "soliq_tahlili").replace(/[/\\?%*:|"<>]/g, "_");
      a.download = `Soliq_tahlili_${safeName}_${taxDoc.audit_year}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccessMessage(
        "✅ Formatlangan Soliq Tahlili Excel (.xlsx) fayli muvaffaqiyatli yuklab olindi! Unda =SUM(), =AVERAGE() faol formulalari va qizil xatar belgilari mavjud."
      );
    } catch (err: any) {
      alert(err.message || "Excel faylni yuklab olishda xatolik yuz berdi");
    } finally {
      setExportingExcel(false);
    }
  };

  // ----------------------------------------------------
  // STANDARD EHF LOGIC
  // ----------------------------------------------------
  const handleEHFRecalculate = () => {
    if (!ehfDoc) return;
    let hasError = false;
    let hasWarning = false;

    const isSupplierValid =
      ehfDoc.supplier_inn && /^\d{9}$/.test(ehfDoc.supplier_inn.trim());
    const isBuyerValid =
      !ehfDoc.buyer_inn || /^\d{9}$/.test(ehfDoc.buyer_inn.trim());

    const docErrors: string[] = [];
    if (!isSupplierValid) {
      docErrors.push("Yetkazib beruvchi STIR noto'g'ri (9 ta raqam bo'lishi lozim).");
      hasError = true;
    }
    if (!isBuyerValid) {
      docErrors.push("Xaridor STIR noto'g'ri (9 ta raqam bo'lishi lozim).");
      hasError = true;
    }

    const updatedLines = ehfDoc.line_items.map((item, idx) => {
      const lineErrors: string[] = [];
      const lineWarnings: string[] = [];
      let itemStatus: "VALID" | "WARNING" | "ERROR" = "VALID";

      const expectedTotal = item.quantity * item.price + item.vat_amount;
      const diff = Math.abs(expectedTotal - item.total_amount);

      if (diff >= 0.05) {
        lineErrors.push(
          `Qator ${idx + 1}: Matematik nomuvofiqlik (kutilgan: ${expectedTotal.toFixed(2)}, amalda: ${item.total_amount.toFixed(2)})`
        );
        itemStatus = "ERROR";
        hasError = true;
      }

      if (item.confidence < 0.85) {
        lineWarnings.push(`Ishonchlilik past: ${(item.confidence * 100).toFixed(0)}%`);
        if (itemStatus === "VALID") {
          itemStatus = "WARNING";
          hasWarning = true;
        }
      }

      return {
        ...item,
        status: itemStatus,
        errors: lineErrors,
        warnings: lineWarnings,
      };
    });

    setEhfDoc({
      ...ehfDoc,
      line_items: updatedLines,
      errors: docErrors,
      overall_status: hasError ? "ERROR" : hasWarning ? "WARNING" : "VALID",
    });
  };

  const handleEHFItemChange = (
    index: number,
    field: keyof OCRLineItem,
    value: any
  ) => {
    if (!ehfDoc) return;
    const updated = [...ehfDoc.line_items];
    const target = { ...updated[index], [field]: value };

    if (field === "quantity" || field === "price" || field === "vat_rate") {
      const q = field === "quantity" ? Number(value) : target.quantity;
      const p = field === "price" ? Number(value) : target.price;
      const r = field === "vat_rate" ? Number(value) : target.vat_rate;
      const vat = (q * p * r) / 100;
      target.vat_amount = Number(vat.toFixed(2));
      target.total_amount = Number((q * p + vat).toFixed(2));
    }

    updated[index] = target;
    setEhfDoc({ ...ehfDoc, line_items: updated });
  };

  const handleDownloadEHFExcel = async () => {
    if (!ehfDoc) return;
    setExportingExcel(true);
    try {
      const payload = {
        doc_number: ehfDoc.doc_number,
        doc_date: ehfDoc.doc_date,
        doc_type: ehfDoc.doc_type,
        supplier_name: ehfDoc.supplier_name,
        supplier_inn: ehfDoc.supplier_inn,
        buyer_name: ehfDoc.buyer_name,
        buyer_inn: ehfDoc.buyer_inn,
        contract_number: ehfDoc.contract_number,
        contract_date: ehfDoc.contract_date,
        line_items: ehfDoc.line_items.map((i) => ({
          item_name: i.item_name,
          ikpu_code: i.ikpu_code,
          unit: i.unit,
          quantity: i.quantity,
          price: i.price,
          vat_rate: i.vat_rate,
          vat_amount: i.vat_amount,
          total_amount: i.total_amount,
          confidence: i.confidence,
        })),
      };

      const blob = await apiClient.exportOCRExcel(payload);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeDocNum = (ehfDoc.doc_number || "faktura").replace(/[/\\?%*:|"<>]/g, "_");
      a.download = `faktura_${safeDocNum}_aslidek.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccessMessage("✅ Hujjat aslidek ko'rinishda Excel (.xlsx) formatida saqlandi!");
    } catch (err: any) {
      alert(err.message || "Excel faylni yuklab olishda xatolik yuz berdi");
    } finally {
      setExportingExcel(false);
    }
  };

  const handleEHFCommit = async () => {
    if (!currentOrg || !ehfDoc) {
      alert("Iltimos, avval tashkilotni tanlang.");
      return;
    }

    setCommitting(true);
    setSuccessMessage(null);
    try {
      const res = await authFetch(`${API_BASE}/ocr/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: currentOrg.id,
          document: {
            doc_number: ehfDoc.doc_number,
            doc_date: ehfDoc.doc_date,
            doc_type: ehfDoc.doc_type,
            supplier_name: ehfDoc.supplier_name,
            supplier_inn: ehfDoc.supplier_inn,
            buyer_name: ehfDoc.buyer_name,
            buyer_inn: ehfDoc.buyer_inn,
            contract_number: ehfDoc.contract_number,
            line_items: ehfDoc.line_items.map((i) => ({
              item_name: i.item_name,
              ikpu_code: i.ikpu_code,
              unit: i.unit,
              quantity: i.quantity,
              price: i.price,
              vat_rate: i.vat_rate,
              vat_amount: i.vat_amount,
              total_amount: i.total_amount,
              confidence: i.confidence,
            })),
          },
          debit_account: currentOrg.mode === "BHMS" ? "2900" : "1000",
          credit_account: "6000",
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Kiritishda xatolik yuz berdi");

      setSuccessMessage(data.message || "Hujjat buxgalteriya balansiga muvaffaqiyatli kiritildi!");
      if (onCommitSuccess) onCommitSuccess();
    } catch (err: any) {
      alert(err.message || "Xatolik yuz berdi");
    } finally {
      setCommitting(false);
    }
  };

  // ----------------------------------------------------
  // RENDER: TAX AUDIT WORKSPACE
  // ----------------------------------------------------
  if (isTaxAudit && taxDoc) {
    const penalty = taxDoc.summary || calculatePenalties(taxDoc.items);
    const totalSoldAmount = taxDoc.items.reduce(
      (sum, i) => sum + (Number(i.sold_amount) || 0),
      0
    );

    return (
      <div className="flex flex-col h-[calc(100vh-5rem)] bg-slate-950 text-slate-100 rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
        {/* Top Action Toolbar */}
        <div className="flex items-center justify-between px-6 py-3.5 bg-slate-900 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            {onReset && (
              <button
                onClick={onReset}
                className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition"
                title="Boshqa hujjat yuklash"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}

            <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg">
              <ShieldAlert className="w-5 h-5" />
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  TAX AUDIT REPORT
                </span>
                <h2 className="text-sm font-bold text-white">
                  Киримсиз сотилган товарлар таҳлили ({taxDoc.audit_year}-йил)
                </h2>
                {discrepancyItemsCount > 0 ? (
                  <span className="flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">
                    <AlertOctagon className="w-3 h-3" />
                    {discrepancyItemsCount} ta kirimsiz nomuvofiqlik
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 className="w-3 h-3" /> Qoldiqlar mos
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Tashkilot: <span className="text-slate-200 font-medium">{taxDoc.company_name}</span> (СТИР: {taxDoc.company_inn}) • Chapda skaner tasviri, o&apos;ngda 13 ustunli tahlil jadvali
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleTaxAuditRecalculate}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition cursor-pointer"
              title="Qatorlar matematikasi va soliq summalarini qayta hisoblash"
            >
              <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
              <span>Qayta hisoblash</span>
            </button>

            {/* Soliq xatarlari modal trigger */}
            <button
              onClick={() => setShowPenaltyModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800/60 rounded-lg text-xs font-bold transition shadow-sm cursor-pointer"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              <span>Soliq xatarlarini tahlil qilish</span>
            </button>

            {/* Publication-Grade Formatted Excel Export (.xlsx) */}
            <button
              onClick={handleDownloadTaxAuditExcel}
              disabled={exportingExcel}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold shadow-md shadow-emerald-600/20 transition cursor-pointer"
              title="Formulali va rangli formatlangan Soliq Tahlili Excel (.xlsx) faylini yuklab olish"
            >
              <FileSpreadsheet className={`w-3.5 h-3.5 ${exportingExcel ? "animate-bounce" : ""}`} />
              <span>{exportingExcel ? "Eksport qilinmoqda..." : "Excelga yuklab olish (.xlsx)"}</span>
            </button>
          </div>
        </div>

        {/* Guidance banner */}
        <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-2 text-[11px] text-slate-300 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-bold text-[10px]">
              TAX FORMULA ENGINE
            </span>
            <span>
              Hisob-kitob qoidasi: <strong>Фарқи = MAX(0, Сотилган - (Қолдиқ + Кирим))</strong>. Qizil rang bilan belgilangan qatorlar kirimsiz sotilgan tovarlar hisoblanadi. Qiymatlarni to&apos;g&apos;ridan-to&apos;g&apos;ri jadval ichida tahrirlashingiz mumkin.
            </span>
          </div>
        </div>

        {successMessage && (
          <div className="bg-emerald-500/15 border-b border-emerald-500/30 px-6 py-2 text-xs text-emerald-300 flex items-center justify-between shrink-0">
            <span>{successMessage}</span>
            <button onClick={() => setSuccessMessage(null)} className="underline hover:text-white">
              Yopish
            </button>
          </div>
        )}

        {/* Split-Screen 50% / 50% */}
        <div className="flex flex-1 overflow-hidden divide-x divide-slate-800">
          {/* Left Side (50%): Image / PDF Preview */}
          <div className="w-1/2 flex flex-col bg-slate-900/60 overflow-hidden relative">
            <div className="absolute top-4 right-4 z-10 flex items-center gap-1 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-1 shadow-lg">
              <button
                onClick={handleZoomOut}
                className="p-1.5 hover:bg-slate-800 text-slate-300 rounded"
                title="Kichraytirish"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-[11px] font-mono px-2 text-slate-300">{zoom}%</span>
              <button
                onClick={handleZoomIn}
                className="p-1.5 hover:bg-slate-800 text-slate-300 rounded"
                title="Kattalashtirish"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={handleZoomReset}
                className="p-1.5 hover:bg-slate-800 text-slate-300 rounded"
                title="Asl holat"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg px-2.5 py-1 shadow-lg text-xs text-slate-300">
              <button
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1}
                className="p-1 hover:bg-slate-800 disabled:opacity-30 rounded"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span>Sahifa {page}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                className="p-1 hover:bg-slate-800 rounded"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-6 flex items-center justify-center">
              {taxDoc.preview_image_base64 || previewImageBase64 ? (
                <img
                  src={taxDoc.preview_image_base64 || previewImageBase64}
                  alt="Tax audit scan preview"
                  style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
                  className="max-w-full rounded shadow-xl border border-slate-700 transition-transform duration-100"
                />
              ) : (
                <div className="text-center p-8 border-2 border-dashed border-slate-800 rounded-xl max-w-sm">
                  <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-xs text-slate-400">Tasvir yuklanmoqda yoki mavjud emas</p>
                </div>
              )}
            </div>
          </div>

          {/* Right Side (50%): 13-Column Tax Audit Table */}
          <div className="w-1/2 flex flex-col bg-slate-950 overflow-hidden">
            {/* Header info strip */}
            <div className="p-3 bg-slate-900/50 border-b border-slate-800 grid grid-cols-3 gap-3 text-xs">
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400">Kompaniya nomi</label>
                <input
                  type="text"
                  value={taxDoc.company_name}
                  onChange={(e) => setTaxDoc({ ...taxDoc, company_name: e.target.value })}
                  className="w-full mt-0.5 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-100 text-xs font-semibold"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400">СТИР (ИНН)</label>
                <input
                  type="text"
                  maxLength={9}
                  value={taxDoc.company_inn}
                  onChange={(e) => setTaxDoc({ ...taxDoc, company_inn: e.target.value })}
                  className="w-full mt-0.5 px-2 py-1 bg-slate-900 border border-slate-700 rounded font-mono text-slate-100 text-xs"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400">Audit Yili</label>
                <input
                  type="number"
                  value={taxDoc.audit_year}
                  onChange={(e) => setTaxDoc({ ...taxDoc, audit_year: Number(e.target.value) })}
                  className="w-full mt-0.5 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-100 text-xs"
                />
              </div>
            </div>

            {/* Hierarchical 13-Column Table */}
            <div className="flex-1 overflow-auto">
              <table className="w-full text-left border-collapse text-[11px]">
                <thead className="sticky top-0 bg-slate-900 text-slate-200 border-b border-slate-800 z-10 select-none">
                  {/* Top Level Headers */}
                  <tr className="border-b border-slate-800 text-[10px] font-bold text-center uppercase tracking-wider">
                    <th rowSpan={2} className="py-2 px-2 bg-blue-950/40 text-blue-300 border-r border-slate-800 w-8">
                      №
                    </th>
                    <th rowSpan={2} className="py-2 px-3 bg-blue-950/40 text-blue-300 border-r border-slate-800 min-w-[180px] text-left">
                      Товар номи
                    </th>
                    <th colSpan={2} className="py-1 px-2 bg-slate-900 text-slate-300 border-r border-slate-800">
                      {taxDoc.audit_year} й. 1 январ қолдиқ
                    </th>
                    <th colSpan={2} className="py-1 px-2 bg-slate-900 text-slate-300 border-r border-slate-800">
                      Давр кирими
                    </th>
                    <th colSpan={3} className="py-1 px-2 bg-slate-900 text-slate-300 border-r border-slate-800">
                      Сотилган (чиқим)
                    </th>
                    <th colSpan={2} className="py-1 px-2 bg-slate-900 text-slate-300 border-r border-slate-800">
                      Давр охири қолдиқ
                    </th>
                    <th colSpan={2} className="py-1 px-2 bg-rose-950/60 text-rose-300 border-r border-slate-800">
                      Фарқи (Киримсиз сотув)
                    </th>
                  </tr>

                  {/* Sub Headers */}
                  <tr className="border-b border-slate-800 text-[10px] font-semibold text-slate-400 text-center">
                    <th className="py-1 px-2 border-r border-slate-800 text-right">Сони</th>
                    <th className="py-1 px-2 border-r border-slate-800 text-right">Суммаси</th>

                    <th className="py-1 px-2 border-r border-slate-800 text-right">Сони</th>
                    <th className="py-1 px-2 border-r border-slate-800 text-right">Суммаси</th>

                    <th className="py-1 px-2 border-r border-slate-800 text-right">Сони</th>
                    <th className="py-1 px-2 border-r border-slate-800 text-right">Ўрт. нархи</th>
                    <th className="py-1 px-2 border-r border-slate-800 text-right">Суммаси</th>

                    <th className="py-1 px-2 border-r border-slate-800 text-right">Сони</th>
                    <th className="py-1 px-2 border-r border-slate-800 text-right">Суммаси</th>

                    <th className="py-1 px-2 bg-rose-950/40 text-rose-300 border-r border-slate-800 text-right font-bold">
                      Сони
                    </th>
                    <th className="py-1 px-2 bg-rose-950/40 text-rose-300 text-right font-bold">
                      Киримсиз сумма
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {taxDoc.items.map((item, index) => {
                    const hasDiscrepancy = Number(item.diff_qty) > 0;
                    const rowClass = hasDiscrepancy
                      ? "bg-rose-950/20 hover:bg-rose-950/30 text-rose-100 border-l-4 border-l-rose-500 font-medium"
                      : index % 2 === 0
                      ? "bg-slate-900/30 hover:bg-slate-900/50 text-slate-200"
                      : "bg-slate-950 hover:bg-slate-900/40 text-slate-200";

                    return (
                      <tr key={index} className={`transition ${rowClass}`}>
                        {/* 1. Item No */}
                        <td className="py-1.5 px-2 text-center text-slate-400 border-r border-slate-800/60">
                          {hasDiscrepancy ? (
                            <span className="text-rose-400 font-bold" title="Киримсиз сотув аниқланган!">
                              {item.item_no}
                            </span>
                          ) : (
                            item.item_no
                          )}
                        </td>

                        {/* 2. Item Name */}
                        <td className="py-1.5 px-2 border-r border-slate-800/60 font-sans">
                          <input
                            type="text"
                            value={item.item_name}
                            onChange={(e) => handleTaxItemChange(index, "item_name", e.target.value)}
                            className="w-full bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-[11px] text-slate-100"
                          />
                        </td>

                        {/* 3. Opening Qty */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.opening_qty}
                            onChange={(e) => handleTaxItemChange(index, "opening_qty", e.target.value)}
                            className="w-16 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 4. Opening Amount */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.opening_amount}
                            onChange={(e) => handleTaxItemChange(index, "opening_amount", e.target.value)}
                            className="w-20 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 5. Inflow Qty */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.inflow_qty}
                            onChange={(e) => handleTaxItemChange(index, "inflow_qty", e.target.value)}
                            className="w-16 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 6. Inflow Amount */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.inflow_amount}
                            onChange={(e) => handleTaxItemChange(index, "inflow_amount", e.target.value)}
                            className="w-20 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 7. Sold Qty */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.sold_qty}
                            onChange={(e) => handleTaxItemChange(index, "sold_qty", e.target.value)}
                            className="w-16 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px] font-semibold"
                          />
                        </td>

                        {/* 8. Avg Price */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.avg_price}
                            onChange={(e) => handleTaxItemChange(index, "avg_price", e.target.value)}
                            className="w-18 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 9. Sold Amount */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.sold_amount}
                            onChange={(e) => handleTaxItemChange(index, "sold_amount", e.target.value)}
                            className="w-22 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 10. Closing Qty */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.closing_qty}
                            onChange={(e) => handleTaxItemChange(index, "closing_qty", e.target.value)}
                            className="w-16 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 11. Closing Amount */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60">
                          <input
                            type="number"
                            step="any"
                            value={item.closing_amount}
                            onChange={(e) => handleTaxItemChange(index, "closing_amount", e.target.value)}
                            className="w-20 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-right text-[11px]"
                          />
                        </td>

                        {/* 12. Diff Qty (Discrepancy) */}
                        <td className="py-1.5 px-1 text-right border-r border-slate-800/60 bg-rose-950/30">
                          <input
                            type="number"
                            step="any"
                            value={item.diff_qty}
                            onChange={(e) => handleTaxItemChange(index, "diff_qty", e.target.value)}
                            className={`w-16 bg-transparent border-0 focus:ring-1 focus:ring-rose-400 rounded px-1 text-right text-[11px] font-bold ${
                              hasDiscrepancy ? "text-rose-400" : "text-slate-400"
                            }`}
                          />
                        </td>

                        {/* 13. Diff Amount (Discrepancy Amount) */}
                        <td className="py-1.5 px-1 text-right bg-rose-950/30">
                          <input
                            type="number"
                            step="any"
                            value={item.diff_amount}
                            onChange={(e) => handleTaxItemChange(index, "diff_amount", e.target.value)}
                            className={`w-24 bg-transparent border-0 focus:ring-1 focus:ring-rose-400 rounded px-1 text-right text-[11px] font-bold ${
                              hasDiscrepancy ? "text-rose-300" : "text-slate-400"
                            }`}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Bottom Summary Bar */}
            <div className="p-3 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
              <div className="flex items-center gap-4">
                <span>
                  Satrlar: <strong className="text-white">{taxDoc.items.length}</strong>
                </span>
                <span>
                  Kirimsiz tovarlar:{" "}
                  <strong className={discrepancyItemsCount > 0 ? "text-rose-400" : "text-emerald-400"}>
                    {discrepancyItemsCount} ta
                  </strong>
                </span>
              </div>

              <div className="flex items-center gap-6">
                <div>
                  Jami Sotuv:{" "}
                  <span className="text-slate-100 font-mono">
                    {totalSoldAmount.toLocaleString("ru-RU", { minimumFractionDigits: 2 })}{" "}
                    UZS
                  </span>
                </div>

                <div className="p-1 px-3 bg-rose-950/60 border border-rose-800/60 rounded-lg flex items-center gap-2">
                  <span className="text-rose-300 text-[11px]">Kirimsiz sotuv summasi:</span>
                  <span className="text-rose-400 font-bold font-mono text-sm">
                    {Number(penalty.total_discrepancy_amount).toLocaleString("ru-RU", {
                      minimumFractionDigits: 2,
                    })}{" "}
                    UZS
                  </span>
                </div>

                <button
                  onClick={() => setShowPenaltyModal(true)}
                  className="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-bold transition flex items-center gap-1.5 shadow"
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Xatarlar tahlili</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ---------------------------------------------------- */}
        {/* SOLIQ XATARLARI & JARIMALAR MODAL                     */}
        {/* ---------------------------------------------------- */}
        {showPenaltyModal && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative text-slate-100 animate-in fade-in zoom-in-95">
              <button
                onClick={() => setShowPenaltyModal(false)}
                className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex items-center gap-3 mb-4">
                <div className="p-2.5 bg-rose-600/20 text-rose-400 border border-rose-500/20 rounded-xl">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">
                    Soliq Xatarlari va Jarimalar Tahlili
                  </h3>
                  <p className="text-xs text-slate-400">
                    &quot;{taxDoc.company_name}&quot; (СТИР: {taxDoc.company_inn}) • Камерал солиқ текшируви
                  </p>
                </div>
              </div>

              <div className="space-y-3 mb-6">
                {/* 1. Total Discrepancy Amount */}
                <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  <div className="flex items-center gap-2">
                    <Scale className="w-4 h-4 text-amber-400" />
                    <span>Jami kirimsiz sotilgan tovarlar summasi:</span>
                  </div>
                  <span className="font-mono font-bold text-amber-300">
                    {Number(penalty.total_discrepancy_amount).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} UZS
                  </span>
                </div>

                {/* 2. VAT (12%) */}
                <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-blue-400" />
                    <span>Qo&apos;shilgan qiymat solig&apos;i (QQS 12%):</span>
                  </div>
                  <span className="font-mono font-bold text-blue-300">
                    {Number(penalty.vat_amount).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} UZS
                  </span>
                </div>

                {/* 3. Net Tax Base */}
                <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  <span className="text-slate-400">QQSsiz soliq solinadigan sof baza:</span>
                  <span className="font-mono text-slate-300">
                    {Number(penalty.net_tax_base).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} UZS
                  </span>
                </div>

                {/* 4. Profit Tax Addition (15%) */}
                <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  <span>Foyda solig&apos;iga qo&apos;shimcha hisob (15%):</span>
                  <span className="font-mono font-semibold text-rose-300">
                    {Number(penalty.profit_tax_addition).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} UZS
                  </span>
                </div>

                {/* 5. Financial Penalty (20%) */}
                <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  <span>Moliyaviy jarima (SK 227-1, 20%):</span>
                  <span className="font-mono font-semibold text-rose-400">
                    {Number(penalty.financial_penalty).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} UZS
                  </span>
                </div>

                {/* Grand Total Budget Liability Card */}
                <div className="p-4 bg-gradient-to-r from-rose-950/80 to-rose-900/60 border border-rose-700/60 rounded-xl flex items-center justify-between shadow-lg">
                  <div>
                    <span className="text-[11px] uppercase tracking-wider font-bold text-rose-300 block">
                      Давлат бюджетига жами тўлов:
                    </span>
                    <span className="text-[10px] text-rose-300/80">
                      (QQS + Foyda solig&apos;i + Moliyaviy jarima)
                    </span>
                  </div>
                  <span className="text-xl font-mono font-black text-rose-200">
                    {Number(penalty.total_budget_liability).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} UZS
                  </span>
                </div>
              </div>

              {/* Modal footer actions */}
              <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
                <button
                  onClick={() => setShowPenaltyModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition"
                >
                  Yopish
                </button>

                <button
                  onClick={() => {
                    setShowPenaltyModal(false);
                    handleDownloadTaxAuditExcel();
                  }}
                  className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold shadow-md shadow-emerald-600/20 transition cursor-pointer"
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>Excel (.xlsx) yuklab olish</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ----------------------------------------------------
  // RENDER: STANDARD EHF WORKSPACE
  // ----------------------------------------------------
  if (!ehfDoc) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-slate-400 text-sm">
        Hujjat ma&apos;lumotlari mavjud emas.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] bg-slate-950 text-slate-100 rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
      {/* Top Action Toolbar */}
      <div className="flex items-center justify-between px-6 py-3.5 bg-slate-900 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          {onReset && (
            <button
              onClick={onReset}
              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition"
              title="Boshqa hujjat yuklash"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}

          <div className="p-2 bg-blue-600/20 text-blue-400 rounded-lg">
            <FileText className="w-5 h-5" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-blue-500/20 text-blue-300 border border-blue-500/30">
                EHF FAKTURA
              </span>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                Hujjat Verifikatsiyasi (OCR Workspace)
                {ehfDoc.overall_status === "VALID" ? (
                  <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                    <CheckCircle2 className="w-3 h-3" /> To&apos;g&apos;ri
                  </span>
                ) : ehfDoc.overall_status === "WARNING" ? (
                  <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                    <AlertTriangle className="w-3 h-3" /> Tekshirish talab
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 font-medium">
                    <AlertOctagon className="w-3 h-3" /> Xatolik mavjud
                  </span>
                )}
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Chap panelda tasvir, o&apos;ng panelda interaktiv tahrirlash jadvali
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleEHFRecalculate}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
            <span>Qayta hisoblash</span>
          </button>

          <button
            onClick={handleDownloadEHFExcel}
            disabled={exportingExcel}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold shadow-md shadow-emerald-600/20 transition cursor-pointer"
            title="Tiklangan fakturani aslidek qilib Excel (.xlsx) formatida saqlash"
          >
            <FileSpreadsheet className={`w-3.5 h-3.5 ${exportingExcel ? "animate-bounce" : ""}`} />
            <span>{exportingExcel ? "Eksport qilinmoqda..." : "Aslidek Excel (.xlsx) saqlash"}</span>
          </button>

          <button
            onClick={handleEHFCommit}
            disabled={committing}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold shadow-md shadow-blue-500/20 transition cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{committing ? "Kiritilmoqda..." : "Balansga kiritish"}</span>
          </button>
        </div>
      </div>

      {/* Informative Guidance Banner */}
      <div className="bg-slate-900/80 border-b border-slate-800 px-6 py-2 text-[11px] text-slate-300 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">
            ASLIDEK XLSX
          </span>
          <span>
            Hujjatni avval <strong>&quot;Aslidek Excel (.xlsx) saqlash&quot;</strong> tugmasi orqali yuklab olib, o&apos;zingiz tekshirishingiz mumkin. Tekshiruvdan so&apos;ng xohlasangiz &quot;Hujjatlar&quot; bo&apos;limi orqali import qilasiz yoki bevosita &quot;Balansga kiritish&quot; tugmasini bosasiz.
          </span>
        </div>
      </div>

      {successMessage && (
        <div className="bg-emerald-500/15 border-b border-emerald-500/30 px-6 py-2 text-xs text-emerald-300 flex items-center justify-between shrink-0">
          <span>{successMessage}</span>
          <button onClick={() => setSuccessMessage(null)} className="underline hover:text-white">
            Yopish
          </button>
        </div>
      )}

      {/* Split-Screen 50% / 50% */}
      <div className="flex flex-1 overflow-hidden divide-x divide-slate-800">
        {/* Left Side (50%): Image / PDF Preview */}
        <div className="w-1/2 flex flex-col bg-slate-900/60 overflow-hidden relative">
          <div className="absolute top-4 right-4 z-10 flex items-center gap-1 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg p-1 shadow-lg">
            <button
              onClick={handleZoomOut}
              className="p-1.5 hover:bg-slate-800 text-slate-300 rounded"
              title="Kichraytirish"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-[11px] font-mono px-2 text-slate-300">{zoom}%</span>
            <button
              onClick={handleZoomIn}
              className="p-1.5 hover:bg-slate-800 text-slate-300 rounded"
              title="Kattalashtirish"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomReset}
              className="p-1.5 hover:bg-slate-800 text-slate-300 rounded"
              title="Asl holat"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="absolute bottom-4 left-4 z-10 flex items-center gap-2 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg px-2.5 py-1 shadow-lg text-xs text-slate-300">
            <button
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page <= 1}
              className="p-1 hover:bg-slate-800 disabled:opacity-30 rounded"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>Sahifa {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              className="p-1 hover:bg-slate-800 rounded"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-auto p-6 flex items-center justify-center">
            {previewImageBase64 ? (
              <img
                src={previewImageBase64}
                alt="Degraded scan preview"
                style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
                className="max-w-full rounded shadow-xl border border-slate-700 transition-transform duration-100"
              />
            ) : (
              <div className="text-center p-8 border-2 border-dashed border-slate-800 rounded-xl max-w-sm">
                <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <p className="text-xs text-slate-400">Tasvir mavjud emas yoki yuklanmoqda...</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Side (50%): Editable Data Table */}
        <div className="w-1/2 flex flex-col bg-slate-950 overflow-hidden">
          {/* Header Metadata Summary */}
          <div className="p-4 bg-slate-900/40 border-b border-slate-800 grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="text-[10px] uppercase font-bold text-slate-400">Yetkazib beruvchi</label>
              <input
                type="text"
                value={ehfDoc.supplier_name || ""}
                onChange={(e) => setEhfDoc({ ...ehfDoc, supplier_name: e.target.value })}
                className="w-full mt-0.5 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded text-slate-100 font-medium text-xs focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold text-slate-400">Yetkazib beruvchi STIR</label>
              <input
                type="text"
                maxLength={9}
                value={ehfDoc.supplier_inn || ""}
                onChange={(e) => setEhfDoc({ ...ehfDoc, supplier_inn: e.target.value })}
                className={`w-full mt-0.5 px-2.5 py-1.5 bg-slate-900 border rounded font-mono text-xs focus:ring-1 ${
                  ehfDoc.supplier_inn && /^\d{9}$/.test(ehfDoc.supplier_inn)
                    ? "border-slate-700 text-slate-100"
                    : "border-rose-500 bg-rose-950/20 text-rose-300"
                }`}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold text-slate-400">Hujjat Raqami</label>
              <input
                type="text"
                value={ehfDoc.doc_number || ""}
                onChange={(e) => setEhfDoc({ ...ehfDoc, doc_number: e.target.value })}
                className="w-full mt-0.5 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded text-slate-100 text-xs"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold text-slate-400">Hujjat Sanasi</label>
              <input
                type="date"
                value={ehfDoc.doc_date || ""}
                onChange={(e) => setEhfDoc({ ...ehfDoc, doc_date: e.target.value })}
                className="w-full mt-0.5 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded text-slate-100 text-xs"
              />
            </div>
          </div>

          {/* Table Container */}
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 bg-slate-900 text-slate-300 border-b border-slate-800 text-[11px] font-semibold uppercase">
                <tr>
                  <th className="py-2.5 px-3">Holat</th>
                  <th className="py-2.5 px-3">Tovar / Xizmat nomi</th>
                  <th className="py-2.5 px-3">MXIK (IKPU)</th>
                  <th className="py-2.5 px-2">Birlik</th>
                  <th className="py-2.5 px-2 text-right">Miqdor</th>
                  <th className="py-2.5 px-2 text-right">Narxi</th>
                  <th className="py-2.5 px-2 text-right">QQS %</th>
                  <th className="py-2.5 px-2 text-right">QQS summasi</th>
                  <th className="py-2.5 px-3 text-right">Jami summa</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {ehfDoc.line_items.map((item, index) => {
                  const isLowConf = item.confidence < 0.85;
                  const isError = item.status === "ERROR";

                  let rowClasses = "hover:bg-slate-900/50 transition";
                  if (isError) {
                    rowClasses = "bg-rose-50 text-rose-900 border-rose-400 font-semibold";
                  } else if (isLowConf) {
                    rowClasses = "bg-amber-50 text-amber-900 border-amber-300 font-semibold";
                  }

                  return (
                    <tr key={index} className={rowClasses}>
                      <td className="py-2 px-3 whitespace-nowrap">
                        {isError ? (
                          <span title={item.errors.join("\n")} className="flex items-center gap-1 text-rose-600">
                            <AlertOctagon className="w-4 h-4" />
                          </span>
                        ) : isLowConf ? (
                          <span title={item.warnings.join("\n")} className="flex items-center gap-1 text-amber-600">
                            <AlertTriangle className="w-4 h-4" />
                          </span>
                        ) : (
                          <span className="text-emerald-500">
                            <CheckCircle2 className="w-4 h-4" />
                          </span>
                        )}
                      </td>

                      <td className="py-2 px-3">
                        <input
                          type="text"
                          value={item.item_name}
                          onChange={(e) => handleEHFItemChange(index, "item_name", e.target.value)}
                          className="w-full bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>

                      <td className="py-2 px-3">
                        <input
                          type="text"
                          maxLength={17}
                          value={item.ikpu_code || ""}
                          onChange={(e) => handleEHFItemChange(index, "ikpu_code", e.target.value)}
                          className="w-28 font-mono bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>

                      <td className="py-2 px-2">
                        <input
                          type="text"
                          value={item.unit}
                          onChange={(e) => handleEHFItemChange(index, "unit", e.target.value)}
                          className="w-12 bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs text-center"
                        />
                      </td>

                      <td className="py-2 px-2 text-right">
                        <input
                          type="number"
                          step="0.001"
                          value={item.quantity}
                          onChange={(e) => handleEHFItemChange(index, "quantity", e.target.value)}
                          className="w-16 text-right font-mono bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>

                      <td className="py-2 px-2 text-right">
                        <input
                          type="number"
                          step="0.01"
                          value={item.price}
                          onChange={(e) => handleEHFItemChange(index, "price", e.target.value)}
                          className="w-24 text-right font-mono bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>

                      <td className="py-2 px-2 text-right">
                        <input
                          type="number"
                          step="1"
                          value={item.vat_rate}
                          onChange={(e) => handleEHFItemChange(index, "vat_rate", e.target.value)}
                          className="w-12 text-right font-mono bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>

                      <td className="py-2 px-2 text-right">
                        <input
                          type="number"
                          step="0.01"
                          value={item.vat_amount}
                          onChange={(e) => handleEHFItemChange(index, "vat_amount", e.target.value)}
                          className="w-24 text-right font-mono bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>

                      <td className="py-2 px-3 text-right">
                        <input
                          type="number"
                          step="0.01"
                          value={item.total_amount}
                          onChange={(e) => handleEHFItemChange(index, "total_amount", e.target.value)}
                          className="w-28 text-right font-bold font-mono bg-transparent border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 text-xs"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Bottom Summary Bar */}
          <div className="p-3 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
            <div>
              Satrlar soni: <span className="text-white">{ehfDoc.line_items.length}</span>
            </div>
            <div className="flex items-center gap-6">
              <div>
                Jami QQS:{" "}
                <span className="text-white font-mono">
                  {ehfDoc.line_items
                    .reduce((acc, curr) => acc + curr.vat_amount, 0)
                    .toLocaleString("ru-RU", { minimumFractionDigits: 2 })}{" "}
                  UZS
                </span>
              </div>
              <div>
                Jami Summa:{" "}
                <span className="text-blue-400 font-bold font-mono text-sm">
                  {ehfDoc.line_items
                    .reduce((acc, curr) => acc + curr.total_amount, 0)
                    .toLocaleString("ru-RU", { minimumFractionDigits: 2 })}{" "}
                  UZS
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VerificationWorkspace;
