"use client";

import React from "react";
import {
  FileSpreadsheet,
  ShieldAlert,
  X,
  DollarSign,
  Scale,
} from "lucide-react";
import { TaxPenaltySummary } from "@/types/accounting";

type Props = {
  companyName: string;
  companyInn: string;
  penalty: TaxPenaltySummary;
  onClose: () => void;
  onDownloadExcel: () => void;
};

/** Cameral tax audit: discrepancy-based VAT / profit tax / penalty breakdown. */
export function TaxPenaltyModal({ companyName, companyInn, penalty, onClose, onDownloadExcel }: Props) {
  return (
      <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative text-slate-100 animate-in fade-in zoom-in-95">
          <button
            onClick={onClose}
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
                &quot;{companyName}&quot; (СТИР: {companyInn}) • Камерал солиқ текшируви
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
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition"
            >
              Yopish
            </button>

            <button
              onClick={() => {
                onClose();
                onDownloadExcel();
              }}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold shadow-md shadow-emerald-600/20 transition cursor-pointer"
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>Excel (.xlsx) yuklab olish</span>
            </button>
          </div>
        </div>
      </div>
  );
}

export default TaxPenaltyModal;
