"use client";

import React, { useState } from "react";
import { X, Building2, Plus, Check } from "lucide-react";
import { useOrg } from "@/lib/org-context";
import { AccountingMode } from "@/types/accounting";

interface NewOrgModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NewOrgModal: React.FC<NewOrgModalProps> = ({ isOpen, onClose }) => {
  const { createOrganization } = useOrg();
  const [name, setName] = useState("");
  const [inn, setInn] = useState("");
  const [mode, setMode] = useState<AccountingMode>("BHMS");
  const [vatPayer, setVatPayer] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanInn = inn.trim();
    if (!/^\d{9}$/.test(cleanInn)) {
      setError("STIR aniq 9 ta raqamdan iborat bo'lishi kerak!");
      return;
    }

    if (!name.trim()) {
      setError("Tashkilot nomini kiriting!");
      return;
    }

    setLoading(true);
    try {
      await createOrganization({
        name: name.trim(),
        inn: cleanInn,
        mode,
        vat_payer: vatPayer,
      });
      setName("");
      setInn("");
      onClose();
    } catch (err: any) {
      setError(err.message || "Tashkilotni yaratishda xatolik yuz berdi");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-xs p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl animate-in fade-in zoom-in-95">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold">
              <Building2 className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-bold text-white">Yangi Tashkilot Qo'shish</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Tashkilot Nomi <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="Masalan: 'Toshkent Agro Savdo' MCHJ"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              STIR (INN - 9 ta raqam) <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              maxLength={9}
              placeholder="301234567"
              value={inn}
              onChange={(e) => setInn(e.target.value.replace(/\D/g, ""))}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Buxgalteriya Rejimi
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setMode("BHMS")}
                className={`p-2.5 rounded-lg border text-left text-xs transition ${
                  mode === "BHMS"
                    ? "bg-blue-600/20 border-blue-500 text-white font-bold"
                    : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                <div className="font-semibold">BHMS Rejimi</div>
                <div className="text-[10px] text-slate-400 font-normal mt-0.5">Professional schotlar (2900, 6000...)</div>
              </button>

              <button
                type="button"
                onClick={() => setMode("SIMPLE")}
                className={`p-2.5 rounded-lg border text-left text-xs transition ${
                  mode === "SIMPLE"
                    ? "bg-amber-600/20 border-amber-500 text-white font-bold"
                    : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                <div className="font-semibold">Oddiy Rejim</div>
                <div className="text-[10px] text-slate-400 font-normal mt-0.5">Soddalashtirilgan daromad/xarajat</div>
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="vat_payer"
              checked={vatPayer}
              onChange={(e) => setVatPayer(e.target.checked)}
              className="w-4 h-4 rounded bg-slate-950 border-slate-700 text-blue-600 focus:ring-0"
            />
            <label htmlFor="vat_payer" className="text-xs text-slate-300 font-medium cursor-pointer">
              Qo'shilgan qiymat solig'i (QQS 12%) to'lovchisi
            </label>
          </div>

          <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
            >
              Bekor qilish
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow-md shadow-blue-500/20 transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              {loading ? "Qo'shilmoqda..." : "Tashkilotni yaratish"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
export default NewOrgModal;
