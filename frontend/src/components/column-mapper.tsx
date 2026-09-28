"use client";

import React, { useState } from "react";
import { ColumnMapping } from "@/types/accounting";
import { X, Check, Table, Sparkles, HelpCircle, Layers, ArrowRight, CheckCircle2 } from "lucide-react";

interface ColumnMapperProps {
  isOpen: boolean;
  onClose: () => void;
  availableColumns: string[];
  initialMapping: ColumnMapping;
  sampleRows: Record<string, any>[];
  onConfirm: (mapping: ColumnMapping, docType: string) => void;
  loading?: boolean;
  initialDocType?: string;
}

export const ColumnMapper: React.FC<ColumnMapperProps> = ({
  isOpen,
  onClose,
  availableColumns,
  initialMapping,
  sampleRows,
  onConfirm,
  loading,
  initialDocType = "SOLIQ_SALES",
}) => {
  const [mapping, setMapping] = useState<ColumnMapping>(initialMapping);
  const [docType, setDocType] = useState<string>(initialDocType);
  const [activeTab, setActiveTab] = useState<"goods" | "sales" | "general">("goods");

  if (!isOpen) return null;

  // Groups of fields tailored for Uzbekistan accounting, Soliq.uz and Didox
  const fieldGroups = {
    goods: {
      title: "Tovar va Nomenklatura",
      description: "Mahsulot nomi, Shtrix (GTIN) kod, MXIK va tannarx",
      fields: [
        {
          key: "item_name_col" as keyof ColumnMapping,
          label: "Маҳсулот (хизмат) номи",
          sublabel: "Tovar yoki xizmat nomi",
          required: true,
          example: "Ликер: Узбекистон, Коньяк 3 юлдуз...",
        },
        {
          key: "barcode_col" as keyof ColumnMapping,
          label: "Штрих (GTIN) код",
          sublabel: "Xalqaro tovar shtrix kodi (GTIN)",
          required: false,
          example: "4780145006230",
        },
        {
          key: "ikpu_col" as keyof ColumnMapping,
          label: "МХИК идентификацион коди",
          sublabel: "17 xonali MXIK / IKPU tasniflagich kodi",
          required: false,
          example: "02208006001076003",
        },
        {
          key: "price_col" as keyof ColumnMapping,
          label: "Ўртача маҳсулот (хизмат) қиймати",
          sublabel: "Birlik narxi yoki o'rtacha qiymati",
          required: false,
          example: "57,492.00 so'm",
        },
      ],
    },
    sales: {
      title: "Savdo va Qaytarish (Realizatsiya)",
      description: "Sotilgan va qaytarilgan tovarlar soni hamda summalari",
      fields: [
        {
          key: "outflow_qty_col" as keyof ColumnMapping,
          label: "Сотилган маҳсулот сони (дона/кг)",
          sublabel: "Realizatsiya / sotuv miqdori",
          required: true,
          example: "615 dona",
        },
        {
          key: "total_col" as keyof ColumnMapping,
          label: "Сотилган маҳсулот суммаси (Жами)",
          sublabel: "Jami realizatsiya / tushum summasi",
          required: true,
          example: "35,357,592.00 so'm",
        },
        {
          key: "return_qty_col" as keyof ColumnMapping,
          label: "Қайтарилган маҳсулот сони (дона/кг)",
          sublabel: "Xaridorlar tomonidan qaytarilgan tovar soni",
          required: false,
          example: "0 dona",
        },
        {
          key: "return_sum_col" as keyof ColumnMapping,
          label: "Қайтарилган маҳсулот суммаси",
          sublabel: "Qaytarilgan tovarlar umumiy summasi",
          required: false,
          example: "0.00 so'm",
        },
      ],
    },
    general: {
      title: "Sana, Hujjat va Kontragent",
      description: "Operatsiya vaqti, tartib raqami va hamkor ma'lumotlari",
      fields: [
        {
          key: "date_col" as keyof ColumnMapping,
          label: "Маҳсулотнинг охирги сотилган вақти",
          sublabel: "Operatsiya / sotuv sanasi",
          required: true,
          example: "2023-01-31",
        },
        {
          key: "doc_num_col" as keyof ColumnMapping,
          label: "№ (Тартиб рақами / Ҳужжат)",
          sublabel: "Qator yoki hujjat raqami",
          required: false,
          example: "1",
        },
        {
          key: "counterparty_col" as keyof ColumnMapping,
          label: "Контрагент / Харидор номи",
          sublabel: "Hamkor yoki xaridor tashkilot nomi",
          required: false,
          example: "Aholi (Chakana savdo)",
        },
        {
          key: "counterparty_inn_col" as keyof ColumnMapping,
          label: "Контрагент СТИР (ИНН)",
          sublabel: "Kontragentning 9 xonali STIR raqami",
          required: false,
          example: "301234567",
        },
      ],
    },
  };

  // Count assigned columns
  const allFieldKeys = [
    "item_name_col", "barcode_col", "ikpu_col", "price_col",
    "outflow_qty_col", "total_col", "return_qty_col", "return_sum_col",
    "date_col", "doc_num_col", "counterparty_col", "counterparty_inn_col"
  ] as (keyof ColumnMapping)[];

  const assignedCount = allFieldKeys.filter(k => !!mapping[k]).length;

  // Reverse mapping for highlighting in sample table
  const columnToFieldBadge: Record<string, string> = {};
  if (mapping.item_name_col) columnToFieldBadge[mapping.item_name_col] = "Nomi";
  if (mapping.barcode_col) columnToFieldBadge[mapping.barcode_col] = "GTIN";
  if (mapping.ikpu_col) columnToFieldBadge[mapping.ikpu_col] = "MXIK";
  if (mapping.price_col) columnToFieldBadge[mapping.price_col] = "Narx";
  if (mapping.outflow_qty_col) columnToFieldBadge[mapping.outflow_qty_col] = "Sotilgan soni";
  if (mapping.total_col) columnToFieldBadge[mapping.total_col] = "Sotilgan summa";
  if (mapping.return_qty_col) columnToFieldBadge[mapping.return_qty_col] = "Qaytarilgan soni";
  if (mapping.return_sum_col) columnToFieldBadge[mapping.return_sum_col] = "Qaytarilgan summa";
  if (mapping.date_col) columnToFieldBadge[mapping.date_col] = "Sana";
  if (mapping.doc_num_col) columnToFieldBadge[mapping.doc_num_col] = "№";

  const handleFieldChange = (key: keyof ColumnMapping, val: string) => {
    const updated = { ...mapping, [key]: val || undefined };
    // Synchronize qty_col with outflow_qty_col if needed
    if (key === "outflow_qty_col") updated.qty_col = val || undefined;
    setMapping(updated);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 md:p-6">
      <div className="bg-white rounded-3xl max-w-5xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-gradient-to-r from-slate-50 to-blue-50/40">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-blue-600 text-white flex items-center justify-center shadow-md shadow-blue-500/20">
              <Table className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900">
                  Aqlli Ustunlar Tahlilchisi (Smart Column Mapper)
                </h3>
                <span className="flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{assignedCount} ta ustun aniqlandi</span>
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Jadval ustunlarini aniqlab, buxgalteriya maydonlariga biriktiring va tasdiqlang
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-slate-200/80 text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Operation Type / Document Type Banner */}
        <div className="px-6 py-3.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-700">Amal turi va provodka:</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="bg-white border border-slate-300 rounded-xl px-3 py-1.5 text-xs font-semibold text-blue-700 focus:outline-hidden focus:border-blue-500 shadow-2xs"
            >
              <option value="SOLIQ_SALES">Soliq.uz / Kassa Realizatsiyasi (Dt 5000 Kassa / Kt 9000 Sotish)</option>
              <option value="EHF">Didox EHF Faktura (Dt 2900 Tovarlar / Kt 6000 Ta'minotchi)</option>
              <option value="BANK">Bank Ko'chirmasi (Dt 5110 Bank / Kt 4000 Xaridorlar)</option>
              <option value="MANUAL">Umumiy kiritish (Oddiy / Moslashuvchan)</option>
            </select>
          </div>
          <div className="text-[11px] text-slate-500 flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>AI va lingvistik qoidalar yordamida ustun nomlari avtomatik tanildi</span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-200 px-6 bg-white gap-2 pt-2">
          {(["goods", "sales", "general"] as const).map((tabKey) => (
            <button
              key={tabKey}
              onClick={() => setActiveTab(tabKey)}
              className={`pb-3 px-4 text-xs font-semibold border-b-2 transition-all flex items-center gap-2 ${
                activeTab === tabKey
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <span>{fieldGroups[tabKey].title}</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-mono">
                {fieldGroups[tabKey].fields.filter(f => !!mapping[f.key]).length} / {fieldGroups[tabKey].fields.length}
              </span>
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 bg-slate-50/30">
          {/* Active Tab Form Grid */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs space-y-4">
            <div className="border-b border-slate-100 pb-3">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                {fieldGroups[activeTab].title}
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {fieldGroups[activeTab].description}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {fieldGroups[activeTab].fields.map((field) => {
                const assignedValue = mapping[field.key];
                const isAutoMatched = !!assignedValue;

                return (
                  <div key={field.key} className="space-y-1.5 bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                        <span>{field.label}</span>
                        {field.required && <span className="text-rose-500">*</span>}
                      </label>
                      {isAutoMatched && (
                        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200 flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          <span>Biriktirildi</span>
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-500">
                      {field.sublabel} {field.example && <span className="text-slate-400 font-mono">(Masalan: {field.example})</span>}
                    </p>
                    <select
                      value={assignedValue || ""}
                      onChange={(e) => handleFieldChange(field.key, e.target.value)}
                      className={`w-full bg-white border rounded-xl px-3 py-2 text-xs focus:outline-hidden transition-all shadow-2xs ${
                        assignedValue
                          ? "border-blue-400 text-slate-900 font-semibold"
                          : "border-slate-300 text-slate-500"
                      }`}
                    >
                      <option value="">-- Ustun tanlanmagan --</option>
                      {availableColumns.map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sample Table Preview with Highlighted Badges */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-800 flex items-center gap-2">
                <Table className="w-4 h-4 text-blue-600" />
                <span>Yuklangan Fayl Ma'lumotlari Ko'rinishi (Namunaviy dastlabki qatorlar):</span>
              </h4>
              <span className="text-[11px] text-slate-500">
                Jami {availableColumns.length} ta ustun topildi
              </span>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-2xl bg-white shadow-2xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-100/90 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    {availableColumns.map((col) => {
                      const badgeText = columnToFieldBadge[col];
                      return (
                        <th key={col} className="p-3 whitespace-nowrap border-r border-slate-200 last:border-r-0">
                          <div className="space-y-1">
                            <div className="text-slate-800 font-bold">{col}</div>
                            {badgeText ? (
                              <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 border border-blue-200">
                                → {badgeText}
                              </span>
                            ) : (
                              <span className="inline-block text-[10px] text-slate-400 font-normal">
                                (kiritilmaydi)
                              </span>
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-600 font-mono text-[11px]">
                  {sampleRows.slice(0, 5).map((row, idx) => (
                    <tr key={idx} className="hover:bg-blue-50/30 transition-colors">
                      {availableColumns.map((col) => (
                        <td key={col} className="p-2.5 whitespace-nowrap border-r border-slate-100 last:border-r-0">
                          {String(row[col] ?? "-")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-slate-200 bg-white flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-slate-500">
            Tanlangan ustunlar asosida <span className="font-semibold text-slate-800">{assignedCount} ta maydon</span> shakllantirildi.
          </div>
          <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors"
            >
              Bekor qilish
            </button>
            <button
              disabled={loading}
              onClick={() => onConfirm(mapping, docType)}
              className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 active:scale-98 text-white text-xs font-bold flex items-center gap-2 shadow-lg shadow-blue-600/25 transition-all"
            >
              <Check className="w-4 h-4" />
              <span>Tasdiqlash va Buxgalteriyaga Kiritish</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
