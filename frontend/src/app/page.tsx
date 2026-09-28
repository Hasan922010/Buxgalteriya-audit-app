"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { DashboardKPIs } from "@/types/accounting";
import { formatCurrency } from "@/lib/utils";
import { useOrg } from "@/lib/org-context";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Boxes,
  ArrowUpRight,
  UploadCloud,
  Scale,
  FileCheck2,
} from "lucide-react";

export default function DashboardPage() {
  const { currentOrg, setReportContext } = useOrg();
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (currentOrg) {
      setLoading(true);
      apiClient
        .getDashboardKPIs(currentOrg.id)
        .then((res) => {
          setKpis(res);
          setReportContext(res);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [currentOrg, setReportContext]);

  const cards = [
    {
      title: "Oylik Kirim (Inflow)",
      value: kpis ? formatCurrency(kpis.monthly_inflow) : "...",
      desc: "Joriy oyda qabul qilingan tovar va tushumlar",
      icon: TrendingUp,
      color: "text-emerald-600 bg-emerald-50 border-emerald-100",
    },
    {
      title: "Oylik Chiqim (Outflow)",
      value: kpis ? formatCurrency(kpis.monthly_outflow) : "...",
      desc: "Joriy oyda to'langan xarajat va pul mablag'lari",
      icon: TrendingDown,
      color: "text-rose-600 bg-rose-50 border-rose-100",
    },
    {
      title: "Sof Kassa va Bank (Net Cash)",
      value: kpis ? formatCurrency(kpis.net_cash_balance) : "...",
      desc: "5000 va 5110 schotlardagi joriy qoldiq",
      icon: Wallet,
      color: "text-blue-600 bg-blue-50 border-blue-100",
    },
    {
      title: "Ombordagi Tovar Qiymati",
      value: kpis ? formatCurrency(kpis.inventory_valuation) : "...",
      desc: "Moddiy hisobot bo'yicha baholangan qoldiq",
      icon: Boxes,
      color: "text-purple-600 bg-purple-50 border-purple-100",
    },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Welcome header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Moliyaviy Boshqaruv Paneli
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {currentOrg?.name} korxonasining joriy moliyaviy holati va tahlili
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/documents"
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Hujjat yuklash</span>
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {cards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">
                  {card.title}
                </span>
                <div className={`p-2 rounded-xl border ${card.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4">
                <h3 className="text-lg font-bold text-slate-900 tracking-tight">
                  {card.value}
                </h3>
                <p className="text-[11px] text-slate-400 mt-1">{card.desc}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Action Navigation */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Link
          href="/reports/oborotka"
          className="bg-white p-6 rounded-2xl border border-slate-200 hover:border-blue-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Scale className="w-5 h-5" />
            </div>
            <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
          </div>
          <h4 className="text-sm font-bold text-slate-900 mt-4">
            Aylanma Qoldiq Vedomosti (OSV)
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            Barcha schotlar bo'yicha boshlang'ich qoldiq, kirim/chiqim oboroti va oxirgi qoldiq.
          </p>
        </Link>

        <Link
          href="/reports/materials"
          className="bg-white p-6 rounded-2xl border border-slate-200 hover:border-emerald-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Boxes className="w-5 h-5" />
            </div>
            <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 transition-colors" />
          </div>
          <h4 className="text-sm font-bold text-slate-900 mt-4">
            Moddiy Hisobot (Ombor)
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            O'rtacha tannarx asosida tovar va xomashyolarning kirim-chiqim vedomosti.
          </p>
        </Link>

        <Link
          href="/reports/akt-sverka"
          className="bg-white p-6 rounded-2xl border border-slate-200 hover:border-indigo-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <FileCheck2 className="w-5 h-5" />
            </div>
            <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 transition-colors" />
          </div>
          <h4 className="text-sm font-bold text-slate-900 mt-4">
            Akt Sverka (Solishtirma)
          </h4>
          <p className="text-xs text-slate-500 mt-1">
            Yetkazib beruvchi va xaridorlar bilan o'zaro hisob-kitoblar va yakuniy qarz holati.
          </p>
        </Link>
      </div>

      {/* Mode Information Box */}
      <div className="p-5 rounded-2xl bg-slate-900 text-white flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
              Faol Buxgalteriya Rejimi
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-600/30 text-blue-300 border border-blue-500/30">
              {currentOrg?.mode === "BHMS" ? "Professional BHMS" : "Oddiy / Soddalashtirilgan"}
            </span>
          </div>
          <p className="text-xs text-slate-300">
            {currentOrg?.mode === "BHMS"
              ? "O'zbekiston BHMS schotlar rejasi (1000, 2900, 4000, 5110, 6000, 6800) bo'yicha to'liq ikkiyoqlama yozuv faol."
              : "Soddalashtirilgan rejim: Kirim, Chiqim, Boshlang'ich va Oxirgi qoldiq hisoblanmoqda."}
          </p>
        </div>
        <Link
          href="/settings"
          className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition-colors border border-slate-700 shrink-0"
        >
          Rejimni sozlash
        </Link>
      </div>
    </div>
  );
}
