"use client";

import React, { useState, useRef } from "react";
import { apiClient } from "@/lib/api-client";
import { UploadResponse, ColumnMapping, TaskStatusResponse } from "@/types/accounting";
import { useOrg } from "@/lib/org-context";
import { ColumnMapper } from "./column-mapper";
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  SlidersHorizontal,
  Database,
  FileCheck,
  ShieldAlert,
  Activity,
} from "lucide-react";

interface FileUploaderProps {
  organizationId: string;
  operationType?: "INITIAL_BALANCE" | "INFLOW" | "OUTFLOW";
  onSuccess: () => void;
}

export const FileUploader: React.FC<FileUploaderProps> = ({
  organizationId,
  operationType = "INFLOW",
  onSuccess,
}) => {
  const { currentRole } = useOrg();
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [alwaysOpenMapper, setAlwaysOpenMapper] = useState(true);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [mapperOpen, setMapperOpen] = useState(false);
  const [mapperData, setMapperData] = useState<{
    columns: string[];
    mapping: ColumnMapping;
    samples: Record<string, any>[];
    docType: string;
  } | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<TaskStatusResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const isReadOnlyRole = currentRole === "AUDITOR" || currentRole === "DIRECTOR";

  const pollTask = (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const task = await apiClient.getTaskStatus(taskId);
        setActiveTask(task);

        if (task.status === "COMPLETED") {
          clearInterval(interval);
          setLoading(false);
          setStatusMessage(`Muvaffaqiyatli: ${task.step_message}`);
          onSuccess();
          setTimeout(() => {
            setActiveTask(null);
          }, 4000);
        } else if (task.status === "FAILED") {
          clearInterval(interval);
          setLoading(false);
          setStatusMessage(`Xatolik: ${task.error_message || "Fon vazifasi bajarilmadi"}`);
        }
      } catch (err: any) {
        clearInterval(interval);
        setLoading(false);
        setStatusMessage(`Status tekshirishda xatolik: ${err.message}`);
      }
    }, 700);
  };

  const handleFile = async (file: File) => {
    setLoading(true);
    setStatusMessage(null);
    try {
      const res = await apiClient.uploadDocument(file);
      setUploadResult(res);

      // Fetch smart mapping preview
      const preview = await apiClient.previewMapping(res.file_id);

      let defaultDocType = "EHF";
      if (operationType === "INITIAL_BALANCE") {
        defaultDocType = "INITIAL_BALANCE";
      } else if (operationType === "OUTFLOW") {
        defaultDocType = res.detected_format.format_type === "SOLIQ_REGISTRY" ? "SOLIQ_SALES" : "OUTFLOW";
      } else {
        if (res.detected_format.format_type === "DIDOX_EHF") defaultDocType = "EHF";
        else if (res.detected_format.format_type === "BANK_STATEMENT") defaultDocType = "BANK";
        else if (res.detected_format.format_type === "MATERIAL_REPORT") defaultDocType = "INITIAL_STOCK";
        else if (res.detected_format.format_type === "SOLIQ_REGISTRY") defaultDocType = "SOLIQ_SALES";
        else if (file.name.toLowerCase().endsWith(".pdf")) defaultDocType = "EHF";
      }

      setMapperData({
        columns: preview.available_columns,
        mapping: preview.proposed_mapping,
        samples: preview.sample_preview,
        docType: defaultDocType,
      });

      if (alwaysOpenMapper || res.detected_format.format_type === "GENERIC_EXCEL" || res.detected_format.format_type === "UNKNOWN" || file.name.toLowerCase().endsWith(".pdf")) {
        setMapperOpen(true);
      } else {
        setStatusMessage("Fayl tahlil qilindi. Ustunlarni tekshirib tasdiqlashingiz yoki to'g'ridan-to'g'ri yuklashingiz mumkin.");
      }
    } catch (err: any) {
      setStatusMessage(`Xatolik: ${err.message || "Faylni yuklashda xato yuz berdi"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleMapperConfirm = async (mapping: ColumnMapping, docType: string) => {
    if (!uploadResult) return;
    if (isReadOnlyRole) {
      alert("Ruxsat berilmagan: Auditor yoki Rahbar roliga ega foydalanuvchilar ma'lumot import qila olmaydi.");
      return;
    }

    setLoading(true);
    try {
      const res = await apiClient.commitDocumentAsync({
        file_id: uploadResult.file_id,
        organization_id: organizationId,
        format_type: uploadResult.detected_format.format_type,
        mapping,
        doc_type: docType,
        operation_type: operationType,
      });
      setMapperOpen(false);
      setActiveTask({
        id: res.task_id,
        name: "Hujjat importi",
        status: "PROCESSING",
        progress: 10,
        step_message: res.step_message || "Fon jarayoni boshlanmoqda...",
        total_items: 0,
        processed_items: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      pollTask(res.task_id);
    } catch (err: any) {
      setLoading(false);
      alert(`Xatolik: ${err.message}`);
    }
  };

  const handleDirectCommit = async () => {
    if (!uploadResult || !mapperData) return;
    if (isReadOnlyRole) {
      alert("Ruxsat berilmagan: Auditor yoki Rahbar roliga ega foydalanuvchilar ma'lumot import qila olmaydi.");
      return;
    }

    setLoading(true);
    try {
      const res = await apiClient.commitDocumentAsync({
        file_id: uploadResult.file_id,
        organization_id: organizationId,
        format_type: uploadResult.detected_format.format_type,
        mapping: mapperData.mapping,
        doc_type: mapperData.docType,
        operation_type: operationType,
      });
      setActiveTask({
        id: res.task_id,
        name: "Hujjat importi",
        status: "PROCESSING",
        progress: 10,
        step_message: res.step_message || "Fon jarayoni boshlanmoqda...",
        total_items: 0,
        processed_items: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      pollTask(res.task_id);
    } catch (err: any) {
      setLoading(false);
      alert(`Xatolik: ${err.message}`);
    }
  };

  const formatNameMap: Record<string, string> = {
    SOLIQ_REGISTRY: "Soliq.uz / Kassa Realizatsiyasi (Savdo Reyestri)",
    DIDOX_EHF: "Didox.uz EHF Elektron Hisob-Fakturalar",
    BANK_STATEMENT: "Bank-Mijoz Ko'chirmasi (To'lov topshirnomalari)",
    GENERIC_EXCEL: "Nostandart Excel / CSV Jadval",
    UNKNOWN: "Noma'lum Jadval",
  };

  return (
    <div className="space-y-5">
      {/* RBAC Warning Banner for Read-Only roles */}
      {isReadOnlyRole && (
        <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 flex items-center gap-3 text-xs text-amber-800">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0" />
          <div>
            <span className="font-bold">Eslatma: </span>
            Siz hozirda <span className="font-semibold">{currentRole === "AUDITOR" ? "Auditor" : "Rahbar"}</span> rolidasiz (Faqat ko'rish). Ma'lumotlarni bazaga import qilish uchun yuqoridagi menyudan <span className="font-semibold text-blue-700">"Bosh buxgalter"</span> yoki <span className="font-semibold text-emerald-700">"Kassir / Operator"</span> roliga o'ting.
          </div>
        </div>
      )}

      {/* Active Operation Mode Banner */}
      <div className="p-3.5 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs shadow-2xs transition-all bg-white border-slate-200">
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full shrink-0 animate-pulse bg-emerald-500" />
          <div>
            <span className="font-bold text-slate-800">
              {operationType === "INITIAL_BALANCE" && "📦 Boshlang'ich qoldiq yuklash rejimi"}
              {operationType === "INFLOW" && "📥 Kirim hujjatlari yuklash rejimi"}
              {operationType === "OUTFLOW" && "📤 Chiqim hujjatlari yuklash rejimi"}
            </span>
            <span className="text-slate-500 ml-2">
              {operationType === "INITIAL_BALANCE" && "(Debet: 2900 Tovarlar / Kredit: 8300 Ustav kapitali, QQS: 0%)"}
              {operationType === "INFLOW" && "(Debet: 2900 Tovarlar / Kredit: 6000 Yetkazib beruvchilar, QQS: 12%)"}
              {operationType === "OUTFLOW" && "(Realizatsiya: Debet 4000 / Kredit 9000, Chiqim: 9100 / 2900)"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[11px] text-emerald-800 shrink-0 self-start sm:self-auto font-medium">
          <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
          <span>O'ta sezgir AI tovar ajratish faol</span>
        </div>
      </div>

      {/* Upload Toggle Mode */}
      <div className="flex items-center justify-between px-4 py-2.5 rounded-2xl bg-slate-50 border border-slate-200">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-blue-600" />
          <span className="text-xs font-semibold text-slate-700">
            Yuklangan jadval ustunlarini har doim avtomatik tahlil qilib, moslashtirish oynasini ochish:
          </span>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={alwaysOpenMapper}
            onChange={(e) => setAlwaysOpenMapper(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-slate-200 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>

      {/* Drag & Drop Area */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files?.[0]) {
            handleFile(e.dataTransfer.files[0]);
          }
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer transition-all ${
          dragOver
            ? "border-blue-500 bg-blue-50/60"
            : "border-slate-300 hover:border-blue-400 bg-white shadow-xs"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv,.txt,.pdf"
          onChange={(e) => {
            if (e.target.files?.[0]) handleFile(e.target.files[0]);
          }}
          className="hidden"
        />

        <div className="max-w-md mx-auto space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto shadow-inner">
            {loading && !activeTask ? (
              <Loader2 className="w-7 h-7 animate-spin" />
            ) : (
              <UploadCloud className="w-7 h-7" />
            )}
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-800">
              Soliq reyestri, Didox EHF, Skaner qilingan PDF yoki Excel hisobotini yuklang
            </h4>
            <p className="text-xs text-slate-500 mt-1">
              Faylni bu yerga sudrab tashlang yoki kompyuterdan tanlash uchun bosing
            </p>
          </div>
          <div className="flex items-center justify-center gap-2 text-[11px] text-slate-400">
            <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-mono font-semibold">.pdf (Skaner / Faktura)</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 font-mono">.xlsx</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 font-mono">.xls</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 font-mono">.txt (1C)</span>
            <span className="px-2 py-0.5 rounded bg-slate-100 font-mono">.csv</span>
          </div>
        </div>
      </div>

      {/* Asynchronous Background Task Live Progress Bar */}
      {activeTask && (
        <div className="bg-white rounded-3xl p-5 border border-blue-200 shadow-lg space-y-3 animate-in fade-in zoom-in-95">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-600 animate-pulse" />
              <span className="text-xs font-bold text-slate-800">
                Asinxron Fon Jarayoni: {activeTask.name}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {activeTask.total_items > 0 && (
                <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                  {activeTask.processed_items} / {activeTask.total_items} qator
                </span>
              )}
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                  activeTask.status === "COMPLETED"
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                    : activeTask.status === "FAILED"
                    ? "bg-rose-100 text-rose-800 border border-rose-300"
                    : "bg-blue-100 text-blue-800 border border-blue-300"
                }`}
              >
                {activeTask.status}
              </span>
            </div>
          </div>

          {/* Progress bar line */}
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 rounded-full ${
                activeTask.status === "FAILED"
                  ? "bg-rose-600"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600"
              }`}
              style={{ width: `${activeTask.progress}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-600 flex items-center gap-1.5 font-medium">
              {activeTask.status === "PROCESSING" && (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
              )}
              {activeTask.step_message}
            </span>
            <span className="font-mono font-bold text-slate-700">{activeTask.progress}%</span>
          </div>
        </div>
      )}

      {/* Analysis Card after upload */}
      {uploadResult && (
        <div className="bg-white rounded-3xl p-5 border border-slate-200 shadow-md space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-blue-100 text-blue-700 flex items-center justify-center">
                <FileCheck className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900">{uploadResult.filename}</h4>
                <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                  <span className="font-semibold text-blue-700">
                    {formatNameMap[uploadResult.detected_format.format_type] || uploadResult.detected_format.format_type}
                  </span>
                  <span>•</span>
                  <span>{uploadResult.detected_format.total_rows} ta qator topildi</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                disabled={isReadOnlyRole}
                onClick={() => setMapperOpen(true)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors border ${
                  isReadOnlyRole
                    ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                    : "bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-200 cursor-pointer"
                }`}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>Ustunlarni tahlil qilish va tanlash</span>
              </button>
              <button
                disabled={loading || isReadOnlyRole}
                onClick={handleDirectCommit}
                className={`px-4 py-2 rounded-xl font-semibold text-xs flex items-center gap-1.5 shadow-md transition-all ${
                  isReadOnlyRole
                    ? "bg-slate-200 text-slate-400 shadow-none cursor-not-allowed"
                    : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20 cursor-pointer"
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>To'g'ridan-to'g'ri kiritish (Asinxron)</span>
              </button>
            </div>
          </div>

          {/* Detected column chips */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                <span>Jadvaldan aniqlangan ustun nomlari ({uploadResult.detected_format.detected_headers.length} ta):</span>
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {uploadResult.detected_format.detected_headers.map((hdr, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-[11px] font-medium"
                >
                  {hdr}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Status banner */}
      {statusMessage && (
        <div
          className={`p-4 rounded-2xl text-xs font-semibold flex items-center gap-2 ${
            statusMessage.includes("Xatolik")
              ? "bg-rose-50 text-rose-700 border border-rose-200"
              : "bg-emerald-50 text-emerald-800 border border-emerald-200"
          }`}
        >
          {statusMessage.includes("Xatolik") ? (
            <AlertCircle className="w-4 h-4 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          )}
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Smart Column Mapper Modal */}
      {mapperData && (
        <ColumnMapper
          isOpen={mapperOpen}
          onClose={() => setMapperOpen(false)}
          availableColumns={mapperData.columns}
          initialMapping={mapperData.mapping}
          sampleRows={mapperData.samples}
          onConfirm={handleMapperConfirm}
          loading={loading}
          initialDocType={mapperData.docType}
        />
      )}
    </div>
  );
};
