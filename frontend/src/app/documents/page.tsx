"use client";

import React, { useState } from "react";
import { FileUploader } from "@/components/file-uploader";
import { PDFToExcelConverter } from "@/components/pdf-to-excel-converter";
import { useOrg } from "@/lib/org-context";
import {
  FileSpreadsheet,
  CheckCircle,
  HelpCircle,
  ArrowRight,
  Package,
  ArrowDownLeft,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

type UploadCategory = "INITIAL_BALANCE" | "INFLOW" | "OUTFLOW";

export default function DocumentsPage() {
  const { currentOrg } = useOrg();
  const [refreshKey, setRefreshKey] = useState(0);
  const [uploadCategory, setUploadCategory] = useState<UploadCategory>("INFLOW");

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Title & Description */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">
          Hujjatlarni Import Qilish (ETL Ingestion)
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Boshlang'ich qoldiq, Kirim va Chiqim hujjatlarini alohida yuklang, hamda PDF fayllarni avtomatik Excel (.xlsx) ga o'giring
        </p>
      </div>

      {/* Upload Mode Selector (Tabs) */}
      <div className="bg-slate-100 p-1.5 rounded-2xl border border-slate-200 grid grid-cols-1 sm:grid-cols-3 gap-1.5">
        <button
          onClick={() => setUploadCategory("INITIAL_BALANCE")}
          className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
            uploadCategory === "INITIAL_BALANCE"
              ? "bg-white text-indigo-900 shadow-xs font-bold"
              : "text-slate-600 hover:text-slate-900 hover:bg-white/50 font-medium"
          }`}
        >
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
              uploadCategory === "INITIAL_BALANCE"
                ? "bg-indigo-50 text-indigo-600"
                : "bg-slate-200/60 text-slate-500"
            }`}
          >
            <Package className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs flex items-center gap-1.5">
              <span>Boshlang'ich qoldiq</span>
              <span className="text-[10px] font-normal px-1.5 py-0.2 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                Ixtiyoriy
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-normal">
              Ombor yoki tovar qoldiqlari (2900 / 8300)
            </div>
          </div>
        </button>

        <button
          onClick={() => setUploadCategory("INFLOW")}
          className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
            uploadCategory === "INFLOW"
              ? "bg-white text-blue-900 shadow-xs font-bold"
              : "text-slate-600 hover:text-slate-900 hover:bg-white/50 font-medium"
          }`}
        >
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
              uploadCategory === "INFLOW"
                ? "bg-blue-50 text-blue-600"
                : "bg-slate-200/60 text-slate-500"
            }`}
          >
            <ArrowDownLeft className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs">Kirim hujjatlari</div>
            <div className="text-[11px] text-slate-400 font-normal">
              Didox EHF va yukxatlar (2900 / 6000)
            </div>
          </div>
        </button>

        <button
          onClick={() => setUploadCategory("OUTFLOW")}
          className={`flex items-center gap-3 p-3 rounded-xl text-left transition-all ${
            uploadCategory === "OUTFLOW"
              ? "bg-white text-emerald-900 shadow-xs font-bold"
              : "text-slate-600 hover:text-slate-900 hover:bg-white/50 font-medium"
          }`}
        >
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
              uploadCategory === "OUTFLOW"
                ? "bg-emerald-50 text-emerald-600"
                : "bg-slate-200/60 text-slate-500"
            }`}
          >
            <ArrowUpRight className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs">Chiqim hujjatlari</div>
            <div className="text-[11px] text-slate-400 font-normal">
              Sotuv, Soliq reyestri va cheklar
            </div>
          </div>
        </button>
      </div>

      {/* Main Upload Card */}
      {currentOrg ? (
        <FileUploader
          key={`${refreshKey}-${uploadCategory}`}
          organizationId={currentOrg.id}
          operationType={uploadCategory}
          onSuccess={() => setRefreshKey((prev) => prev + 1)}
        />
      ) : (
        <div className="p-8 bg-white border border-slate-200 rounded-3xl text-center text-slate-400 text-xs">
          Tashkilot yuklanmoqda...
        </div>
      )}

      {/* PDF to Excel Converter Card */}
      <PDFToExcelConverter />

      {/* Supported formats guide */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-2 shadow-2xs">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-xs">
            SLQ
          </div>
          <h4 className="text-xs font-bold text-slate-800">Soliq.uz Savdo Reyestri</h4>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Mahsulot nomi, GTIN shtrix-kod, 17 xonali MXIK, sotilgan va qaytarilgan tovarlar soni va summalari.
          </p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-2 shadow-2xs">
          <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-xs">
            EHF
          </div>
          <h4 className="text-xs font-bold text-slate-800">Didox.uz EHF Fakturalari</h4>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Tovarlar nomi, MXIK kodi, 12% QQS va yetkazib beruvchi kontragent STIR raqamlari avtomatik aniqlanadi.
          </p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-2 shadow-2xs">
          <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold text-xs">
            BNK
          </div>
          <h4 className="text-xs font-bold text-slate-800">Bank Ko'chirmalari</h4>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Agrobank, Kapitalbank, Hamkorbank va boshqa banklarning Excel yoki 1C TXT ko'chirmalari.
          </p>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 space-y-2 shadow-2xs">
          <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center font-bold text-xs">
            AI
          </div>
          <h4 className="text-xs font-bold text-slate-800">O'ta Sezgir Tovar Tahlili</h4>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Tovar nomlaridagi oxirgi o'lcham, model yoki sifat qo'shimchalari bo'yicha tovarlar ajratiladi.
          </p>
        </div>
      </div>

      {/* Quick link to reports */}
      <div className="p-4 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-900 font-medium">
            Fayllarni yuklaganingizdan so'ng, Aylanma qoldiq yoki Moddiy hisobotda yangilangan balansni ko'rishingiz mumkin.
          </p>
        </div>
        <Link
          href="/reports/oborotka"
          className="flex items-center gap-1 text-xs font-bold text-blue-700 hover:text-blue-900 shrink-0 ml-4"
        >
          <span>Hisobotni ko'rish</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
