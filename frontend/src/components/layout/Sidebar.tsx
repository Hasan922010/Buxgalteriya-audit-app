"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  UploadCloud,
  FileScan,
  Scale,
  Boxes,
  FileCheck2,
  Settings,
  Sparkles,
  ToggleLeft,
  ToggleRight
} from "lucide-react";
import { useOrg } from "@/lib/org-context";

interface SidebarProps {
  onOpenAI?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenAI }) => {
  const pathname = usePathname();
  const { currentOrg, toggleMode } = useOrg();

  const isBHMS = currentOrg?.mode === "BHMS";

  const navigation = [
    { name: "Bosh sahifa (Dashboard)", href: "/", icon: LayoutDashboard },
    { name: "Hujjat yuklash (Upload)", href: "/documents", icon: UploadCloud },
    { name: "Xira hujjatlar (OCR Review)", href: "/ocr-verify", icon: FileScan },
    { name: "Oborotka (OSV)", href: "/reports/oborotka", icon: Scale },
    { name: "Moddiy hisobot (Stock)", href: "/reports/materials", icon: Boxes },
    { name: "Akt sverka", href: "/reports/akt-sverka", icon: FileCheck2 },
    { name: "Sozlamalar", href: "/settings", icon: Settings },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-200 flex flex-col justify-between shrink-0 min-h-screen border-r border-slate-800">
      <div>
        {/* Brand Header */}
        <div className="p-6 border-b border-slate-800 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20">
            YB
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">Yordamchi Buxgalter</h1>
            <p className="text-[11px] text-blue-400 font-medium">Uzbekistan Fintech AI</p>
          </div>
        </div>

        {/* Dual Mode Switcher */}
        <div className="p-4 mx-3 my-3 bg-slate-800/80 rounded-xl border border-slate-700/50">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Hisob Rejimi
          </div>
          <button
            onClick={() => toggleMode(isBHMS ? "SIMPLE" : "BHMS")}
            className="w-full flex items-center justify-between px-3 py-2 bg-slate-900 rounded-lg text-xs font-medium text-slate-300 hover:text-white transition"
          >
            <span>{isBHMS ? "BHMS Professional" : "Soddalashtirilgan"}</span>
            {isBHMS ? (
              <ToggleRight className="w-5 h-5 text-blue-400" />
            ) : (
              <ToggleLeft className="w-5 h-5 text-amber-400" />
            )}
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-1.5">
          {navigation.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/30"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-white" : "text-slate-400"}`} />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* AI Assistant Button */}
      {onOpenAI && (
        <div className="p-4 border-t border-slate-800">
          <button
            onClick={onOpenAI}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-500/20 transition-all cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-amber-300" />
            AI Moliyaviy Tahlilchi
          </button>
        </div>
      )}
    </aside>
  );
};
export default Sidebar;
