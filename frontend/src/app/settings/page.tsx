"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { AccountingMode, AuditLog } from "@/types/accounting";
import { useOrg } from "@/lib/org-context";
import { NewOrgModal } from "@/components/new-org-modal";
import { IntegrationsSection } from "@/components/settings/integrations-section";
import { BackupSection } from "@/components/settings/backup-section";
import { DangerZoneSection } from "@/components/settings/danger-zone-section";
import {
  Building2,
  Layers,
  BookOpen,
  CheckCircle2,
  ShieldCheck,
  Percent,
  Play,
  Sparkles,
  Lock,
  Unlock,
  History,
  Calendar,
  ShieldAlert,
  Plus,
  ArrowRightLeft,
} from "lucide-react";

export default function SettingsPage() {
  const {
    currentOrg,
    organizations,
    switchOrg,
    toggleMode,
    lockPeriod,
    currentRole,
  } = useOrg();
  const isChief = currentRole === "CHIEF_ACCOUNTANT";
  const [mode, setMode] = useState<AccountingMode>(currentOrg?.mode || "SIMPLE");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  // Organization modal state
  const [isNewOrgModalOpen, setIsNewOrgModalOpen] = useState(false);


  // Period locking state
  const [lockDate, setLockDate] = useState<string>(currentOrg?.locked_until_date || "");
  const [locking, setLocking] = useState(false);

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);



  useEffect(() => {
    if (currentOrg) {
      setMode(currentOrg.mode);
      if (currentOrg.locked_until_date) {
        setLockDate(currentOrg.locked_until_date);
      }
      fetchAuditLogs();
    }
  }, [currentOrg]);

  const fetchAuditLogs = async () => {
    if (!currentOrg) return;
    try {
      const logs = await apiClient.getAuditLogs(currentOrg.id, 25);
      setAuditLogs(logs);
    } catch (err) {
      console.error("Audit log yuklanmadi:", err);
    }
  };


  const handleSaveLock = async () => {
    if (!currentOrg || !lockDate) return;
    setLocking(true);
    try {
      await lockPeriod(lockDate);
      await fetchAuditLogs();
    } catch (err: any) {
      alert(err.message || "Davrni qulflashda xatolik yuz berdi");
    } finally {
      setLocking(false);
    }
  };

  const handleUnlock = async () => {
    if (!currentOrg) return;
    if (!confirm("Hisobot davri qulfini ochishni tasdiqlaysizmi?")) return;
    setLocking(true);
    try {
      await lockPeriod(null);
      setLockDate("");
      await fetchAuditLogs();
    } catch (err: any) {
      alert(err.message || "Qulfni ochishda xatolik yuz berdi");
    } finally {
      setLocking(false);
    }
  };

  const handleSave = async () => {
    if (!currentOrg) return;
    setSaving(true);
    setSuccess(false);
    try {
      await toggleMode(mode);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      alert("Sozlamalarni saqlashda xato yuz berdi");
    } finally {
      setSaving(false);
    }
  };




  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Title */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">
          Tizim va Korxona Sozlamalari
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Buxgalteriya rejimi, soliq matritsasi, tashqi API integratsiyalari va zaxira nusxalarini boshqaring
        </p>
      </div>

      {/* RBAC Info Banner if not Chief Accountant */}
      {!isChief && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-center gap-3 text-xs text-amber-800 shadow-2xs">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0" />
          <div>
            <span className="font-bold">Xavfsizlik Cheklovi (RBAC): </span>
            Siz hozirda <span className="font-semibold uppercase tracking-wider text-slate-800">{currentRole}</span> rolidasiz. 
            Davrni qulflash, ochish, rejimni almashtirish va yangi zaxira yaratish huquqi faqat <strong className="text-blue-700">&quot;Bosh buxgalter&quot;</strong> roliga berilgan. 
            Amallarni to&apos;liq boshqarish uchun yuqori o&apos;ng burchakdagi rol tanlagichdan foydalaning.
          </div>
        </div>
      )}

      {/* Multi-Tenancy & Organization Management Section */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold shrink-0">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">
                  Tashkilotlar Boshqaruvi (Multi-Tenant Arxitekturasi)
                </h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                  {organizations.length} ta korxona
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Har bir korxonaning schotlar rejasi, operatsiyalari, tovarlari va hisobotlari to&apos;liq alohida yuritiladi
              </p>
            </div>
          </div>

          <button
            onClick={() => setIsNewOrgModalOpen(true)}
            className="flex items-center justify-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-xs transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Yangi Tashkilot Qo&apos;shish</span>
          </button>
        </div>

        {/* Current Active Org Highlight */}
        {currentOrg && (
          <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-50/60 to-slate-50 border border-blue-200/80 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-100/70 px-2 py-0.5 rounded-md">
                  Hozirda Faol Tashkilot
                </span>
                <h4 className="text-base font-bold text-slate-900 mt-1">
                  {currentOrg.name}
                </h4>
                <p className="text-xs text-slate-500 font-mono">
                  STIR (INN): {currentOrg.inn} | Rejim: {currentOrg.mode} | {currentOrg.vat_payer ? "12% QQS to'lovchisi" : "Aylanma soliq (4%)"}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Faol holatda
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Registered Organizations List */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-700 block">
            Tizimdagi Barcha Tashkilotlar Ro&apos;yxati
          </label>
          <div className="grid grid-cols-1 gap-2.5 max-h-56 overflow-y-auto pr-1">
            {organizations.map((org) => {
              const isActive = currentOrg?.id === org.id;
              return (
                <div
                  key={org.id}
                  className={`p-3.5 rounded-2xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                    isActive
                      ? "bg-blue-50/30 border-blue-400 shadow-xs"
                      : "bg-slate-50 border-slate-200/80 hover:border-slate-300"
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{org.name}</span>
                      <span className="font-mono text-[10px] px-2 py-0.2 rounded bg-slate-200 text-slate-700 font-semibold">
                        STIR: {org.inn}
                      </span>
                      <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 border border-slate-200">
                        {org.mode}
                      </span>
                      {org.vat_payer ? (
                        <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800">
                          QQS 12%
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-slate-100 text-slate-600">
                          Aylanma
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 font-mono">
                      ID: {org.id} | Yaratilgan: {new Date(org.created_at).toLocaleDateString("uz-UZ")}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {isActive ? (
                      <span className="text-[11px] font-bold text-blue-700 bg-blue-100/80 px-3 py-1 rounded-lg">
                        Tanlangan
                      </span>
                    ) : (
                      <button
                        onClick={() => switchOrg(org.id)}
                        className="flex items-center gap-1.5 px-3 py-1 bg-white border border-slate-300 hover:border-blue-500 hover:text-blue-600 text-slate-700 font-medium rounded-lg transition-colors cursor-pointer"
                      >
                        <ArrowRightLeft className="w-3 h-3" />
                        <span>O&apos;tish</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-3 rounded-xl bg-blue-50/50 border border-blue-100 text-[11px] text-blue-900 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0" />
          <span>
            <strong>Izolyatsiya kafolati:</strong> Yuqoridan qaysi tashkilot tanlansa, OSV, Tovar-moddiy zaxiralar, Fakturalar va Soliq hisobotlari faqat o&apos;sha tashkilot ma&apos;lumotlari bo&apos;yicha yuritiladi va ko&apos;rsatiladi. Boshqa korxonalar hisob-kitobiga mutlaqo aralashmaydi.
          </span>
        </div>
      </div>

      {/* Dual Mode Switcher Configuration */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-5">
        <div>
          <h3 className="text-sm font-bold text-slate-900">
            Buxgalteriya Hisobi Rejimi (Dual-Mode)
          </h3>
          <p className="text-xs text-slate-500 mt-1">
            Korxona ehtiyojidan kelib chiqib, soddalashtirilgan yoki professional schotlar rejasini tanlang.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            onClick={() => setMode("SIMPLE")}
            className={`p-5 rounded-2xl border-2 cursor-pointer transition-all space-y-2.5 ${
              mode === "SIMPLE"
                ? "border-blue-600 bg-blue-50/40 shadow-xs"
                : "border-slate-200 hover:border-slate-300 bg-white"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className={`w-4 h-4 ${mode === "SIMPLE" ? "text-blue-600" : "text-slate-500"}`} />
                <h4 className="text-xs font-bold text-slate-900">
                  Mode A: Oddiy / Soddalashtirilgan rejim
                </h4>
              </div>
              {mode === "SIMPLE" && <CheckCircle2 className="w-4 h-4 text-blue-600" />}
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              Kichik biznes, yakka tartibdagi tadbirkorlar va savdo shoxobchalari uchun. Kirim, Chiqim, Boshlang&apos;ich va Oxirgi qoldiq hisoblanadi. Schotlar ko&apos;rsatish shart emas.
            </p>
          </div>

          <div
            onClick={() => setMode("BHMS")}
            className={`p-5 rounded-2xl border-2 cursor-pointer transition-all space-y-2.5 ${
              mode === "BHMS"
                ? "border-blue-600 bg-blue-50/40 shadow-xs"
                : "border-slate-200 hover:border-slate-300 bg-white"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className={`w-4 h-4 ${mode === "BHMS" ? "text-blue-600" : "text-slate-500"}`} />
                <h4 className="text-xs font-bold text-slate-900">
                  Mode B: BHMS (Schotlar rejasi bilan)
                </h4>
              </div>
              {mode === "BHMS" && <CheckCircle2 className="w-4 h-4 text-blue-600" />}
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              O&apos;zbekiston 21-son BHMS standarti. To&apos;liq ikkiyoqlama yozuv, balans, 4 xonali schotlar (1000, 2900, 4000, 5000, 5110, 6000, 9000). Audit va professional buxgalterlar uchun.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          {success ? (
            <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />
              Rejim muvaffaqiyatli yangilandi!
            </span>
          ) : (
            <div></div>
          )}

          <button
            onClick={handleSave}
            disabled={saving || !isChief}
            title={!isChief ? "Faqat Bosh buxgalter rejimni o'zgartira oladi" : ""}
            className={`px-5 py-2.5 rounded-xl text-xs font-semibold shadow-md transition-all ${
              !isChief
                ? "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/20 cursor-pointer"
            }`}
          >
            {saving ? "Saqlanmoqda..." : "O'zgarishlarni saqlash"}
          </button>
        </div>
      </div>

      {/* Period Locking Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-2xl flex items-center justify-center font-bold shrink-0 ${
              currentOrg?.locked_until_date ? "bg-amber-50 text-amber-600" : "bg-blue-50 text-blue-600"
            }`}>
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">
                  Hisobot Davrini Qulflash (Period Locking)
                </h3>
                {currentOrg?.locked_until_date ? (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                    Qulflangan: {currentOrg.locked_until_date} gacha
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Ochiq (Barcha davrlar faol)
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Bosh buxgalter tomonidan yopilgan hisobot davriga o&apos;tmishdagi hujjatlarni qo&apos;shish yoki o&apos;zgartirishni bloklash
              </p>
            </div>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-3">
          <p className="text-xs text-slate-600 leading-relaxed">
            <strong className="text-slate-800">Qoida:</strong> Belgilangan sanagacha bo&apos;lgan barcha buxgalteriya amallari, fakturalar va bank ko&apos;chirmalari o&apos;zgarmas holatga o&apos;tkaziladi. Bu soliq auditida hisobotlarning buzilmasligini kafolatlaydi.
          </p>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-1">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-400" />
              <input
                type="date"
                value={lockDate}
                disabled={!isChief}
                onChange={(e) => setLockDate(e.target.value)}
                className={`px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 font-medium focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none ${
                  !isChief ? "opacity-60 cursor-not-allowed bg-slate-100" : ""
                }`}
              />
            </div>

            <button
              onClick={handleSaveLock}
              disabled={locking || !lockDate || !isChief}
              title={!isChief ? "Faqat Bosh buxgalter davrni qulflay oladi" : ""}
              className={`px-4 py-2 rounded-xl text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-1.5 ${
                !isChief
                  ? "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
                  : "bg-amber-600 hover:bg-amber-500 text-white cursor-pointer"
              }`}
            >
              <Lock className="w-3.5 h-3.5" />
              <span>{locking ? "Saqlanmoqda..." : "Davrni qulflash"}</span>
            </button>

            {currentOrg?.locked_until_date && (
              <button
                onClick={handleUnlock}
                disabled={locking || !isChief}
                title={!isChief ? "Faqat Bosh buxgalter qulfni ocha oladi" : ""}
                className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                  !isChief
                    ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                    : "bg-slate-200 hover:bg-slate-300 text-slate-700 cursor-pointer"
                }`}
              >
                <Unlock className="w-3.5 h-3.5" />
                <span>Qulfni ochish</span>
              </button>
            )}
          </div>
        </div>
      </div>

      <IntegrationsSection onActivity={fetchAuditLogs} />


      <BackupSection onActivity={fetchAuditLogs} />


      {/* Versioned Tax Rules Engine Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
          <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold shrink-0">
            <Percent className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              O&apos;zbekiston Soliq Matritsasi (Versioned Tax Engine)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Qonunchilik o&apos;zgarishlariga mos ravishda sanalar bo&apos;yicha versiyalangan QQS qoidalari
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">QQS 15% (Eski stavka)</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 text-slate-600">Arxiv</span>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              2019-yil 1-oktyabrdan 2022-yil 31-dekabrgacha bo&apos;lgan hujjatlar uchun avtomatik 15% hisoblanadi.
            </p>
          </div>

          <div className="p-4 rounded-2xl border border-emerald-300 bg-emerald-50/40 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-900">QQS 12% (Amaldagi stavka)</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-200 text-emerald-800 font-semibold">Faol</span>
            </div>
            <p className="text-[11px] text-emerald-700 leading-snug">
              2023-yil 1-yanvardan boshlab barcha hisob-fakturalar uchun Soliq Kodeksi 258-moddasi bo&apos;yicha qo&apos;llaniladi.
            </p>
          </div>
        </div>
      </div>

      {/* Audit Trail & Activity Log Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold shrink-0">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Tizim Audit Jurnali (Audit Trail & Activity Log)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Barcha buxgalteriya amallari, stornolar va davr qulflari bo&apos;yicha o&apos;zgarmas xavfsizlik jurnali
              </p>
            </div>
          </div>

          <button
            onClick={fetchAuditLogs}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors cursor-pointer"
          >
            Yangilash
          </button>
        </div>

        {auditLogs.length === 0 ? (
          <p className="text-xs text-slate-400 py-3 text-center">Hali audit qaydlari mavjud emas</p>
        ) : (
          <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
            {auditLogs.map((log) => (
              <div
                key={log.id}
                className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 flex items-start justify-between gap-3 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono font-bold text-[10px] px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                      {log.action}
                    </span>
                    <span className="text-[11px] font-semibold text-slate-700">
                      {log.performed_by}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600">{log.details}</p>
                </div>
                <span className="text-[10px] font-mono text-slate-400 shrink-0">
                  {new Date(log.created_at).toLocaleDateString("uz-UZ")} {new Date(log.created_at).toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <DangerZoneSection onActivity={fetchAuditLogs} />


      {/* System Launch Animation Showcase Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Loyiha Ishga Tushish Animatsiyasi (Launch Loading Page)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Loyiha ishga tushayotganda va qayta yuklanganda namoyish etiladigan chiroyli animatsiyali Loading sahifasini sinab ko&apos;rish
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              if (typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("replay-app-loader"));
              }
            }}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-md shadow-slate-900/10 transition-all shrink-0 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Animatsiyani sinash</span>
          </button>
        </div>
      </div>


      {/* New Organization Modal */}
      <NewOrgModal
        isOpen={isNewOrgModalOpen}
        onClose={() => setIsNewOrgModalOpen(false)}
      />
    </div>
  );
}
