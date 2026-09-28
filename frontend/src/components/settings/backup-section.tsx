"use client";

import React, { useEffect, useState } from "react";
import {
  Database,
  Download,
  FileCheck,
  Server,
  RotateCcw,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useOrg } from "@/lib/org-context";
import { AuthDownloadLink } from "@/components/auth-download-link";
import { BackupItem } from "@/types/accounting";

type Props = {
  /** Called after an action that writes to the audit log, so the page can refresh it. */
  onActivity: () => Promise<void> | void;
};

/** Backup list with create / verify / download / restore actions. */
export function BackupSection({ onActivity }: Props) {
  const { currentOrg, currentRole, refreshOrganizations } = useOrg();
  const isChief = currentRole === "CHIEF_ACCOUNTANT";

  // Backup Engine state
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupMessage, setBackupMessage] = useState<string | null>(null);

  useEffect(() => {
    if (currentOrg) fetchBackups();
  }, [currentOrg]);

  const fetchBackups = async () => {
    try {
      const list = await apiClient.listBackups();
      setBackups(list);
    } catch (err) {
      console.error("Backuplarni yuklab bo'lmadi:", err);
    }
  };

  // Stage 3 Handlers: Backup Engine
  const handleCreateBackup = async () => {
    if (!currentOrg || !isChief) return;
    setBackupLoading(true);
    setBackupMessage(null);
    try {
      const res = await apiClient.createBackup(currentOrg.id);
      setBackupMessage(`Muvaffaqiyatli: ${res.filename} (${res.size_kb} KB, ${res.transactions_count} ta tranzaksiya) saqlandi.`);
      await fetchBackups();
      await onActivity();
    } catch (err: any) {
      setBackupMessage(`Xatolik: ${err.message}`);
    } finally {
      setBackupLoading(false);
    }
  };

  const handleVerifyBackup = async (filename: string) => {
    try {
      const res = await apiClient.verifyBackup(filename);
      alert(`✅ Zaxira butunligi tasdiqlandi!\n\nFayl: ${res.filename}\nSHA256: ${res.actual_checksum}\nTranzaksiyalar soni: ${res.stats?.transactions || 0}`);
    } catch (err: any) {
      alert(`❌ Xatolik: ${err.message}`);
    }
  };

  const handleRestoreBackup = async (filename: string) => {
    if (!isChief) return;
    const confirmation = window.prompt(
      `DIQQAT! "${filename}" zaxirasidagi tashkilot(lar)ning joriy ma'lumotlari zaxira holati bilan almashtiriladi.\n` +
        "Joriy holat avval avtomatik zaxiralanadi.\n\nDavom etish uchun TIKLASH deb yozing:"
    );
    if (!confirmation) return;
    setBackupMessage(null);
    try {
      const res = await apiClient.restoreBackup(filename, confirmation);
      setBackupMessage(`${res.message} Oldingi holat saqlandi: ${res.pre_restore_backup}`);
      await refreshOrganizations();
      await fetchBackups();
      await onActivity();
    } catch (err: any) {
      setBackupMessage(`Xatolik: ${err.message}`);
    }
  };

  return (
    <>
      {/* STAGE 3 FEATURE: Automated Database Backup & Disaster Recovery */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold shrink-0">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Avtomatlashtirilgan Zaxira Nusxalar (Automated Backup & Recovery)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Barcha buxgalteriya yozuvlarining kriptografik SHA256 nazorat summasi bilan himoyalangan zaxira nusxalari
              </p>
            </div>
          </div>

          <button
            onClick={handleCreateBackup}
            disabled={backupLoading || !isChief}
            title={!isChief ? "Faqat Bosh buxgalter zaxira nusxa yarata oladi" : ""}
            className={`px-4 py-2 rounded-xl text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-1.5 ${
              !isChief
                ? "bg-slate-200 text-slate-400 cursor-not-allowed shadow-none"
                : "bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer"
            }`}
          >
            <Server className={`w-3.5 h-3.5 ${backupLoading ? "animate-spin" : ""}`} />
            <span>{backupLoading ? "Nusxalanmoqda..." : "Yangi zaxira yaratish (SHA256)"}</span>
          </button>
        </div>

        {backupMessage && (
          <div className="p-3.5 rounded-2xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-900 font-semibold">
            {backupMessage}
          </div>
        )}

        {backups.length === 0 ? (
          <p className="text-xs text-slate-400 py-3 text-center">Hali zaxira nusxalar mavjud emas</p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {backups.map((b) => (
              <div
                key={b.filename}
                className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-800 text-[11px]">{b.filename}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-200 text-slate-600">
                      {b.size_kb} KB
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800">
                      {b.stats?.transactions || 0} ta tranzaksiya
                    </span>
                  </div>
                  <p className="text-[10px] font-mono text-slate-500 truncate max-w-md">
                    SHA256: {b.checksum_sha256}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleVerifyBackup(b.filename)}
                    className="px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 text-[11px] font-medium flex items-center gap-1 transition-colors cursor-pointer"
                  >
                    <FileCheck className="w-3.5 h-3.5 text-blue-600" />
                    <span>Tekshirish</span>
                  </button>

                  <AuthDownloadLink
                    href={apiClient.getBackupDownloadUrl(b.filename)}
                    className="px-2.5 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 text-[11px] font-medium flex items-center gap-1 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Yuklab olish</span>
                  </AuthDownloadLink>

                  <button
                    onClick={() => handleRestoreBackup(b.filename)}
                    disabled={!isChief}
                    title={!isChief ? "Faqat Bosh buxgalter zaxiradan tiklay oladi" : "Ma'lumotlarni shu zaxira holatiga qaytarish"}
                    className="px-2.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed text-amber-800 text-[11px] font-medium flex items-center gap-1 transition-colors cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Tiklash</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

export default BackupSection;
