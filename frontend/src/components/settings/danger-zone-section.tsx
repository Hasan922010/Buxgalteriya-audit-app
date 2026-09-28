"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Trash2,
  AlertTriangle,
  AlertOctagon,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useOrg } from "@/lib/org-context";

type Props = {
  /** Called after an action that writes to the audit log, so the page can refresh it. */
  onActivity: () => Promise<void> | void;
};

/** Organization data reset and full factory reset (with confirmation modal). */
export function DangerZoneSection({ onActivity }: Props) {
  const { currentOrg, currentRole, resetOrgData, factoryReset } = useOrg();
  const isChief = currentRole === "CHIEF_ACCOUNTANT";

  // Danger Zone state
  const [orgResetLoading, setOrgResetLoading] = useState(false);
  const [showFactoryModal, setShowFactoryModal] = useState(false);
  const [factoryConfirmText, setFactoryConfirmText] = useState("");
  const [factoryResetLoading, setFactoryResetLoading] = useState(false);
  const [dangerMessage, setDangerMessage] = useState<string | null>(null);

  const handleResetCurrentOrg = async () => {
    if (!currentOrg || !isChief) return;
    const confirmed = window.confirm(
      `DIQQAT! "${currentOrg.name}" tashkilotining barcha tranzaksiyalari, tovarlari, kontragentlari va hujjatlari butunlay o'chiriladi!\n\nTashkilot hisobini noldan tozalashni tasdiqlaysizmi?`
    );
    if (!confirmed) return;
    setOrgResetLoading(true);
    setDangerMessage(null);
    try {
      await resetOrgData(currentOrg.id);
      setDangerMessage(`"${currentOrg.name}" hisob ma'lumotlari muvaffaqiyatli tozalandi (0 ga tushirildi).`);
      await onActivity();
    } catch (err: any) {
      alert(err.message || "Tashkilot ma'lumotlarini tozalashda xatolik yuz berdi");
    } finally {
      setOrgResetLoading(false);
    }
  };

  const handleFactoryReset = async () => {
    if (!isChief) return;
    if (factoryConfirmText.trim() !== "TOZALASH") {
      alert("Iltimos, tasdiqlash uchun 'TOZALASH' so'zini to'g'ri kiriting!");
      return;
    }
    setFactoryResetLoading(true);
    try {
      await factoryReset("TOZALASH");
      setShowFactoryModal(false);
      setFactoryConfirmText("");
      alert("Tizim to'liq nollashtirildi va standart BHMS hisoblar rejasi qayta tiklandi!");
      window.location.reload();
    } catch (err: any) {
      alert(err.message || "Tizimni tozalashda xatolik yuz berdi");
    } finally {
      setFactoryResetLoading(false);
    }
  };

  return (
    <>
      {/* STAGE 3 FEATURE: Danger Zone (Data reset & Factory Reset) */}
      <div className="bg-rose-50/40 rounded-3xl border-2 border-rose-200 p-6 shadow-xs space-y-5">
        <div className="flex items-center gap-3 border-b border-rose-200/60 pb-4">
          <div className="w-10 h-10 rounded-2xl bg-rose-100 text-rose-700 flex items-center justify-center font-bold shrink-0">
            <AlertOctagon className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-rose-950">
              Xavfli Hudud: Ma&apos;lumotlarni Tozalash (Danger Zone)
            </h3>
            <p className="text-xs text-rose-700/80 mt-0.5">
              Bazani noldan tozalash va alohida tashkilot hisob-kitoblarini qayta nollashtirish
            </p>
          </div>
        </div>

        {dangerMessage && (
          <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{dangerMessage}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card 1: Reset active org data */}
          <div className="p-5 rounded-2xl bg-white border border-rose-200 shadow-2xs space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-rose-700 font-bold text-xs">
                <Trash2 className="w-4 h-4" />
                <span>Tanlangan Tashkilotni Tozalash</span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Faqat hozirda tanlangan <strong className="text-slate-900">&quot;{currentOrg?.name}&quot;</strong> tashkilotining barcha operatsiyalari, tovarlari, kontragentlari va hujjatlarini o&apos;chiradi. Tashkilotning o&apos;zi va boshqa korxonalar ma&apos;lumotlariga tegilmaydi.
              </p>
            </div>

            <button
              onClick={handleResetCurrentOrg}
              disabled={orgResetLoading || !isChief || !currentOrg}
              title={!isChief ? "Faqat Bosh buxgalter ma'lumotlarni tozalay oladi" : ""}
              className={`w-full py-2.5 px-3 rounded-xl text-xs font-bold shadow-xs flex items-center justify-center gap-1.5 transition-all ${
                !isChief || !currentOrg
                  ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                  : "bg-rose-600 hover:bg-rose-700 text-white cursor-pointer shadow-rose-600/20"
              }`}
            >
              <Trash2 className={`w-3.5 h-3.5 ${orgResetLoading ? "animate-spin" : ""}`} />
              <span>
                {orgResetLoading ? "Tozalanmoqda..." : `"${currentOrg?.name?.slice(0, 15)}..." ni nollashtirish`}
              </span>
            </button>
          </div>

          {/* Card 2: System Factory Reset */}
          <div className="p-5 rounded-2xl bg-white border border-rose-200 shadow-2xs space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-rose-800 font-bold text-xs">
                <AlertTriangle className="w-4 h-4" />
                <span>Tizimni Noldan Tozalash (Factory Reset)</span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Butun tizim bazasini to&apos;liq nollashtiradi: barcha tashkilotlar, operatsiyalar va jurnallar o&apos;chiriladi. BHMS standart schotlar rejasi va bitta toza boshlang&apos;ich korxona qayta yaratiladi.
              </p>
            </div>

            <button
              onClick={() => setShowFactoryModal(true)}
              disabled={!isChief}
              title={!isChief ? "Faqat Bosh buxgalter tizimni tozalay oladi" : ""}
              className={`w-full py-2.5 px-3 rounded-xl text-xs font-bold shadow-xs flex items-center justify-center gap-1.5 transition-all ${
                !isChief
                  ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                  : "bg-slate-900 hover:bg-black text-rose-400 cursor-pointer"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
              <span>Butun Bazani Noldan Tozalash</span>
            </button>
          </div>
        </div>
      </div>

      {/* Factory Reset Confirmation Modal */}
      {showFactoryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-xs p-4">
          <div className="bg-slate-900 border border-rose-500/50 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl p-6 space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center gap-3 text-rose-500">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center font-bold shrink-0">
                <AlertOctagon className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">
                  Tizimni To&apos;liq Nollashtirish (Factory Reset)
                </h3>
                <p className="text-[11px] text-rose-300">
                  Ushbu amalni ortga qaytarib bo&apos;lmaydi!
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/60 text-xs text-rose-200 leading-relaxed space-y-2">
              <p>
                Barcha tashkilotlar, bank ko&apos;chirmalari, tovarlar, kontragentlar va audit jurnallari o&apos;chiriladi.
              </p>
              <p className="font-semibold text-rose-100">
                Tasdiqlash uchun quyidagi maydonga katta harflar bilan <span className="underline font-mono text-yellow-400">TOZALASH</span> so&apos;zini yozing:
              </p>
            </div>

            <input
              type="text"
              placeholder="TOZALASH"
              value={factoryConfirmText}
              onChange={(e) => setFactoryConfirmText(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-rose-500/40 rounded-xl text-center font-mono font-bold tracking-widest text-sm text-yellow-400 outline-none focus:border-rose-400 focus:ring-1 focus:ring-rose-400"
            />

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => {
                  setShowFactoryModal(false);
                  setFactoryConfirmText("");
                }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition cursor-pointer"
              >
                Bekor qilish
              </button>
              <button
                type="button"
                onClick={handleFactoryReset}
                disabled={factoryConfirmText.trim() !== "TOZALASH" || factoryResetLoading}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold rounded-xl shadow-lg shadow-rose-600/30 transition cursor-pointer"
              >
                {factoryResetLoading ? "Tozalanmoqda..." : "Ha, butunlay tozalansin"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default DangerZoneSection;
