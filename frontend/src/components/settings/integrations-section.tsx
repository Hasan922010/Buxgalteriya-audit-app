"use client";

import React, { useEffect, useState } from "react";
import {
  Radio,
  RefreshCw,
  Zap,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useOrg } from "@/lib/org-context";

type Props = {
  /** Called after an action that writes to the audit log, so the page can refresh it. */
  onActivity: () => Promise<void> | void;
};

/** Didox / Soliq.uz integration cards (sync is disabled server-side unless demo mode). */
export function IntegrationsSection({ onActivity }: Props) {
  const { currentOrg, currentRole } = useOrg();
  const isChief = currentRole === "CHIEF_ACCOUNTANT";

  // Integrations state (Didox & Soliq)
  const [didoxToken, setDidoxToken] = useState<string>("");
  const [soliqNkm, setSoliqNkm] = useState<string>("");
  const [didoxLoading, setDidoxLoading] = useState(false);
  const [soliqLoading, setSoliqLoading] = useState(false);
  const [syncStatusMsg, setSyncStatusMsg] = useState<string | null>(null);

  // Stage 3 Handlers: Didox & Soliq Sync
  const handleSyncDidox = async () => {
    if (!currentOrg) return;
    setDidoxLoading(true);
    setSyncStatusMsg(null);
    try {
      const res = await apiClient.syncDidox({
        organization_id: currentOrg.id,
        api_token: didoxToken || undefined,
      });
      setSyncStatusMsg(`Didox sinxronlandi: ${res.synced_count} ta faktura (${res.total_amount.toLocaleString()} so'm) bazaga kiritildi.`);
      await onActivity();
    } catch (err: any) {
      setSyncStatusMsg(`Didox xatosi: ${err.message}`);
    } finally {
      setDidoxLoading(false);
    }
  };

  const handleSyncSoliq = async () => {
    if (!currentOrg) return;
    setSoliqLoading(true);
    setSyncStatusMsg(null);
    try {
      const res = await apiClient.syncSoliq({
        organization_id: currentOrg.id,
        nkm_serial: soliqNkm || undefined,
      });
      setSyncStatusMsg(`Soliq.uz OFD sinxronlandi: ${res.synced_count} ta kassa reyestri (${res.total_amount.toLocaleString()} so'm) kiritildi.`);
      await onActivity();
    } catch (err: any) {
      setSyncStatusMsg(`Soliq.uz xatosi: ${err.message}`);
    } finally {
      setSoliqLoading(false);
    }
  };

  return (
    <>
      {/* STAGE 3 FEATURE: External API Integrations (Didox & Soliq) */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-5">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
          <div className="w-10 h-10 rounded-2xl bg-cyan-50 text-cyan-600 flex items-center justify-center font-bold shrink-0">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Tashqi Tizim Integratsiyalari (Didox.uz & Soliq.uz Direct API)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Fayllarni qo&apos;lda yuklamasdan, to&apos;g&apos;ridan-to&apos;g&apos;ri Didox va Soliq.uz OFD bilan avtomatlashtirilgan sinxronizatsiya
            </p>
          </div>
        </div>

        {syncStatusMsg && (
          <div className="p-3.5 rounded-2xl bg-blue-50 border border-blue-200 text-xs text-blue-900 font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-600 shrink-0" />
            <span>{syncStatusMsg}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Didox Card */}
          <div className="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">Didox.uz EHF Shlyuzi</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                ULANDI (v2.0)
              </span>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              Elektron hisob-fakturalar va ishonchnomalarni avtomatik qabul qilib, schotlar rejasiga (2900/6000) o&apos;tkazadi.
            </p>
            <input
              type="password"
              placeholder="Didox API Kalit / Token (ixtiyoriy)..."
              value={didoxToken}
              onChange={(e) => setDidoxToken(e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
            <button
              onClick={handleSyncDidox}
              disabled={didoxLoading}
              className="w-full py-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-xs flex items-center justify-center gap-1.5 transition-all disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${didoxLoading ? "animate-spin" : ""}`} />
              <span>{didoxLoading ? "Didox sinxronlanmoqda..." : "Didox Fakturalarini Sinxronlash"}</span>
            </button>
          </div>

          {/* Soliq.uz Card */}
          <div className="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">Soliq.uz Fiskal Operator (OFD)</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                ONLAYN (NKM)
              </span>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              Onlayn kassa cheklari va virtual kassa Z-hisobotlarini tushum daromadlariga (5000/9000) yozadi.
            </p>
            <input
              type="text"
              placeholder="Onlayn-NKM seriya raqami..."
              value={soliqNkm}
              onChange={(e) => setSoliqNkm(e.target.value)}
              className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
            />
            <button
              onClick={handleSyncSoliq}
              disabled={soliqLoading}
              className="w-full py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-xs flex items-center justify-center gap-1.5 transition-all disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${soliqLoading ? "animate-spin" : ""}`} />
              <span>{soliqLoading ? "Kassa sinxronlanmoqda..." : "Kassa Cheklarini Sinxronlash"}</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default IntegrationsSection;
