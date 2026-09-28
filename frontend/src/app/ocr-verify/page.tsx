"use client";

import React, { useState } from "react";
import { API_BASE, authFetch } from "@/lib/auth";
import {
  UploadCloud,
  FileScan,
  Sparkles,
  ShieldAlert,
  FileText,
  FileSpreadsheet,
} from "lucide-react";
import {
  VerificationWorkspace,
  OCRDocumentData,
} from "@/components/ocr/VerificationWorkspace";
import { TaxAuditDocument } from "@/types/accounting";
import { apiClient } from "@/lib/api-client";

type OCRMode = "tax-audit" | "ehf";

export default function OCRVerifyPage() {
  const [mode, setMode] = useState<OCRMode>("tax-audit");
  const [loading, setLoading] = useState(false);
  const [docData, setDocData] = useState<OCRDocumentData | null>(null);
  const [taxAuditData, setTaxAuditData] = useState<TaxAuditDocument | null>(null);
  const [previewImage, setPreviewImage] = useState<string | undefined>(undefined);

  const handleReset = () => {
    setDocData(null);
    setTaxAuditData(null);
    setPreviewImage(undefined);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);

    // Auto-detect mode if filename strongly hints at tax audit or user selected it
    const lowerName = file.name.toLowerCase();
    const isTaxAuditDoc =
      mode === "tax-audit" ||
      lowerName.includes("soliq") ||
      lowerName.includes("tax") ||
      lowerName.includes("audit") ||
      lowerName.includes("kirimsiz") ||
      lowerName.includes("киримсиз") ||
      lowerName.includes("kameral");

    try {
      if (isTaxAuditDoc) {
        // Tax Audit OCR Pipeline
        const result = await apiClient.parseTaxAuditDocument(file);
        setTaxAuditData(result);
        if (result.preview_image_base64) {
          setPreviewImage(result.preview_image_base64);
        }
      } else {
        // Standard EHF / Chek OCR Pipeline
        const formData = new FormData();
        formData.append("file", file);

        const res = await authFetch(`${API_BASE}/ocr/upload-and-parse`, {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Faylni tahlil qilishda xatolik yuz berdi");
        }

        const data = await res.json();
        setPreviewImage(data.preview_image_base64);
        setDocData(data.validation);
      }
    } catch (err: any) {
      alert(err.message || "Hujjatni tahlil qilishda xatolik yuz berdi");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  };

  const hasActiveDoc = Boolean(docData || taxAuditData);

  return (
    <div className="flex-1 flex flex-col p-6 overflow-hidden">
      {!hasActiveDoc ? (
        <div className="flex-1 flex flex-col items-center justify-center">
          <div className="max-w-xl w-full p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl text-center">
            {/* Mode Switcher Tabs */}
            <div className="flex items-center justify-center p-1 bg-slate-950/80 border border-slate-800 rounded-xl mb-6 max-w-md mx-auto">
              <button
                type="button"
                onClick={() => setMode("tax-audit")}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-bold transition cursor-pointer ${
                  mode === "tax-audit"
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <ShieldAlert className="w-4 h-4 text-amber-300" />
                <span>Soliq Tahlili (Киримсиз сотув)</span>
              </button>

              <button
                type="button"
                onClick={() => setMode("ehf")}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-bold transition cursor-pointer ${
                  mode === "ehf"
                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>Faktura & Cheklar (EHF)</span>
              </button>
            </div>

            {/* Header Description based on Mode */}
            {mode === "tax-audit" ? (
              <>
                <div className="w-16 h-16 bg-indigo-600/10 text-indigo-400 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-indigo-500/20 shadow-inner">
                  <ShieldAlert className="w-8 h-8 text-indigo-400" />
                </div>
                <h1 className="text-lg font-bold text-white mb-2">
                  Soliq Kameral Tahlili: Kirimsiz Sotilgan Tovarlar
                </h1>
                <p className="text-xs text-slate-400 mb-6 leading-relaxed">
                  Skanerlangan yoki PDF formatdagi murakkab soliq tahlili jadvallarini
                  (&quot;Киримсиз сотилган товарлар таҳлили&quot;) avtomatik tanib olish,
                  inventar qoldiqlarini matematik tekshirish va bir bosishda
                  <strong> formatlangan Excel (.xlsx)</strong> fayliga eksport qilish.
                </p>
              </>
            ) : (
              <>
                <div className="w-16 h-16 bg-blue-600/10 text-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-blue-500/20 shadow-inner">
                  <FileScan className="w-8 h-8" />
                </div>
                <h1 className="text-lg font-bold text-white mb-2">
                  Xira & Skanerlangan Fakturalar Tekshiruvi
                </h1>
                <p className="text-xs text-slate-400 mb-6 leading-relaxed">
                  Buralgan, xira yoki sifati past hisobvaraq-faktura va cheklarni yuklang.
                  AI tasvirni ravshanlashtiradi (Denoise, Deskew, CLAHE) va rekvizitlarni aniqlaydi.
                  Tiklangan hujjatni <strong>aslidek qilib Excel (.xlsx)</strong> formatida saqlab olib, keyin o&apos;zingiz tekshirishingiz mumkin.
                </p>
              </>
            )}

            {/* Upload Zone */}
            <label className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-slate-700 hover:border-indigo-500 bg-slate-950/60 hover:bg-slate-950 rounded-xl cursor-pointer transition group">
              <UploadCloud className="w-10 h-10 text-slate-400 group-hover:text-indigo-400 transition mb-3" />
              <span className="text-xs font-semibold text-slate-300 group-hover:text-white">
                {loading
                  ? "AI hujjatni tahlil qilmoqda..."
                  : "Faylni tanlang yoki shu yerga tashlang"}
              </span>
              <span className="text-[11px] text-slate-500 mt-1">
                {mode === "tax-audit"
                  ? "Soliq tahlili PDF yoki rasm (PDF, JPG, PNG)"
                  : "Hisobvaraq-faktura / Chek (PDF, JPG, PNG)"}
              </span>
              <input
                type="file"
                accept=".pdf,image/png,image/jpeg"
                onChange={handleFileUpload}
                disabled={loading}
                className="hidden"
              />
            </label>

            {loading && (
              <div className="mt-4 flex items-center justify-center gap-2 text-xs text-indigo-400 font-medium">
                <Sparkles className="w-4 h-4 animate-spin text-amber-400" />
                Tasvir tozalanmoqda, jadvallar va soliq xatarlari hisoblanmoqda...
              </div>
            )}

            {/* Feature Pills */}
            <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-center gap-4 text-[11px] text-slate-400">
              <span className="flex items-center gap-1">
                <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                Formulali Excel (.xlsx)
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                QQS 12% & SK 227-1 Jarima
              </span>
              <span>•</span>
              <span>Matematik Tekshiruv</span>
            </div>
          </div>
        </div>
      ) : (
        <VerificationWorkspace
          initialDocument={docData}
          initialTaxAuditDoc={taxAuditData}
          previewImageBase64={previewImage}
          onReset={handleReset}
          onCommitSuccess={() => {
            // Document committed
          }}
        />
      )}
    </div>
  );
}
