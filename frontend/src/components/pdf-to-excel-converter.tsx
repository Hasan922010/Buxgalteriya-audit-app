"use client";

import React, { useState, useRef } from "react";
import { apiClient } from "@/lib/api-client";
import {
  FileText,
  FileSpreadsheet,
  Download,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye,
  RefreshCw,
  Sparkles,
  ArrowRight,
} from "lucide-react";

export const PDFToExcelConverter: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<any | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const selected = e.dataTransfer.files[0];
      if (selected.name.toLowerCase().endsWith(".pdf")) {
        setFile(selected);
        setPreviewData(null);
        setErrorMessage(null);
      } else {
        setErrorMessage("Faqat PDF formatdagi fayllarni tanlang (.pdf)");
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selected = e.target.files[0];
      if (selected.name.toLowerCase().endsWith(".pdf")) {
        setFile(selected);
        setPreviewData(null);
        setErrorMessage(null);
      } else {
        setErrorMessage("Faqat PDF formatdagi fayllarni tanlang (.pdf)");
      }
    }
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setErrorMessage(null);
    try {
      const data = await apiClient.previewPdfExtraction(file);
      setPreviewData(data);
    } catch (err: any) {
      setErrorMessage(err.message || "PDF tahlilida xatolik yuz berdi");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadExcel = async () => {
    if (!file) return;
    setDownloading(true);
    setErrorMessage(null);
    try {
      const blob = await apiClient.exportPdfToExcel(file);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const cleanName = file.name.replace(/\.pdf$/i, "");
      a.download = `EHF_${cleanName}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setErrorMessage(err.message || "Excel faylini yuklab olishda xatolik yuz berdi");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-xs space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-2xs">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 tracking-tight flex items-center gap-2">
              PDF-dan Excel (.xlsx) ga O'tkazish
              <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                AI / OCR Jadval Yig'uvchi
              </span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Hisob-faktura va yukxatli PDF fayllarni tahlil qilib, Didox-mos toza Excel formatiga yig'ib oling
            </p>
          </div>
        </div>

        {file && (
          <button
            onClick={() => {
              setFile(null);
              setPreviewData(null);
              setErrorMessage(null);
            }}
            className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1 self-start sm:self-auto font-medium"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Tozalash</span>
          </button>
        )}
      </div>

      {/* Dropzone */}
      {!file ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleFileDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
            dragOver
              ? "border-indigo-500 bg-indigo-50/50"
              : "border-slate-200 hover:border-indigo-400 bg-slate-50/40 hover:bg-indigo-50/20"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            className="hidden"
          />
          <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 flex items-center justify-center mx-auto mb-3 text-indigo-600 shadow-2xs">
            <FileText className="w-6 h-6" />
          </div>
          <p className="text-xs font-bold text-slate-800">
            PDF hisob-faktura yoki skaner faylni tashlang yoki tanlang
          </p>
          <p className="text-[11px] text-slate-400 mt-1">
            PyMuPDF va AI orqali jadvallar to'liq ajratilib, .xlsx formatiga o'giriladi
          </p>
        </div>
      ) : (
        <div className="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white border border-indigo-200 flex items-center justify-center text-indigo-700 font-bold text-xs shrink-0 shadow-2xs">
              PDF
            </div>
            <div>
              <p className="text-xs font-bold text-slate-900 truncate max-w-xs sm:max-w-md">
                {file.name}
              </p>
              <p className="text-[11px] text-slate-500">
                {(file.size / 1024).toFixed(1)} KB &bull; PDF hujjat
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <button
              onClick={handlePreview}
              disabled={loading || downloading}
              className="px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition flex items-center gap-1.5 shadow-2xs disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
              ) : (
                <Eye className="w-3.5 h-3.5 text-slate-500" />
              )}
              <span>Oldindan ko'rish</span>
            </button>

            <button
              onClick={handleDownloadExcel}
              disabled={loading || downloading}
              className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition flex items-center gap-1.5 shadow-xs disabled:opacity-50"
            >
              {downloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              <span>Excel (.xlsx) yuklab olish</span>
            </button>
          </div>
        </div>
      )}

      {/* Error message */}
      {errorMessage && (
        <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 flex items-center gap-2.5 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Preview Table Section */}
      {previewData && (
        <div className="space-y-4 pt-2">
          {/* Metadata badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Hujjat Raqami</span>
              <span className="text-xs font-bold text-slate-800">{previewData.doc_number || "—"}</span>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Hujjat Sanasi</span>
              <span className="text-xs font-bold text-slate-800">{previewData.doc_date || "—"}</span>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Yetkazib Beruvchi</span>
              <span className="text-xs font-bold text-slate-800 truncate block">
                {previewData.supplier_name || "—"}
                {previewData.supplier_inn ? ` (${previewData.supplier_inn})` : ""}
              </span>
            </div>
            <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Jami Qatorlar</span>
              <span className="text-xs font-bold text-emerald-700">
                {previewData.total_items} ta tovar &bull; {Number(previewData.total_amount || 0).toLocaleString()} so'm
              </span>
            </div>
          </div>

          {/* Table */}
          <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-2xs">
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold sticky top-0">
                  <tr>
                    <th className="py-2.5 px-3 w-10 text-center">T/r</th>
                    <th className="py-2.5 px-3">Tovar / Xizmat Nomi</th>
                    <th className="py-2.5 px-3">Birligi</th>
                    <th className="py-2.5 px-3 text-right">Miqdori</th>
                    <th className="py-2.5 px-3 text-right">Narxi</th>
                    <th className="py-2.5 px-3 text-right">Jami Summa</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {previewData.line_items?.map((item: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-2 px-3 text-center text-slate-400 font-mono text-[11px]">{idx + 1}</td>
                      <td className="py-2 px-3 font-medium text-slate-800">{item.item_name}</td>
                      <td className="py-2 px-3 text-slate-500 text-[11px]">{item.unit || "dona"}</td>
                      <td className="py-2 px-3 text-right font-mono">{Number(item.quantity || 0).toLocaleString()}</td>
                      <td className="py-2 px-3 text-right font-mono">{Number(item.price || 0).toLocaleString()}</td>
                      <td className="py-2 px-3 text-right font-mono font-bold text-slate-900">
                        {Number(item.total_amount || 0).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-[11px] text-slate-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              Didox EHF formatidagi (.xlsx) fayl tayyor
            </span>
            <button
              onClick={handleDownloadExcel}
              disabled={downloading}
              className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition flex items-center gap-1.5 shadow-xs"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Excel (.xlsx) Yuklab Olish</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
