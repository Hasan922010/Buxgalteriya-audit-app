"use client";

import React, { useState, useRef, useEffect } from "react";
import { Organization, AccountingMode } from "@/types/accounting";
import { ModeToggle } from "./mode-toggle";
import { UserMenu } from "./user-menu";
import { NewOrgModal } from "./new-org-modal";
import { Sparkles, Building2, Lock, ChevronDown, Check, Plus } from "lucide-react";
import { useOrg } from "@/lib/org-context";

interface NavbarProps {
  currentOrg: Organization | null;
  onModeToggle: (newMode: AccountingMode) => void;
  onOpenAI: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentOrg, onModeToggle, onOpenAI }) => {
  const { organizations, switchOrg } = useOrg();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <>
      <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 sticky top-0 z-30 shadow-xs">
        {/* Organization Switcher Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="flex items-center gap-3 p-1.5 -ml-1.5 hover:bg-slate-50 rounded-xl transition cursor-pointer border border-transparent hover:border-slate-200"
          >
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 font-bold shrink-0">
              <Building2 className="w-4 h-4" />
            </div>

            <div className="text-left">
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  {currentOrg ? currentOrg.name : "Tashkilot tanlanmagan"}
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                </h2>
                {currentOrg && (
                  <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    STIR: {currentOrg.inn}
                  </span>
                )}
                {currentOrg?.vat_payer && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                    QQS 12%
                  </span>
                )}
                {currentOrg?.locked_until_date && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 flex items-center gap-1">
                    <Lock className="w-3 h-3 text-amber-600" />
                    <span>Qulflangan: {currentOrg.locked_until_date}</span>
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-400">Tashkilotni almashtirish uchun bosing</p>
            </div>
          </button>

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <div className="absolute left-0 top-full mt-2 w-80 bg-white border border-slate-200 rounded-2xl shadow-xl z-50 overflow-hidden animate-in fade-in zoom-in-95">
              <div className="p-3 border-b border-slate-100 bg-slate-50/60 flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Mavjud Tashkilotlar ({organizations.length})
                </span>
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    setIsModalOpen(true);
                  }}
                  className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-700 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Qo'shish
                </button>
              </div>

              <div className="max-h-64 overflow-y-auto divide-y divide-slate-100 p-1.5">
                {organizations.map((org) => {
                  const isSelected = currentOrg?.id === org.id;
                  return (
                    <button
                      key={org.id}
                      onClick={() => {
                        switchOrg(org.id);
                        setDropdownOpen(false);
                      }}
                      className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition cursor-pointer ${
                        isSelected
                          ? "bg-blue-50/80 text-blue-900 font-semibold"
                          : "hover:bg-slate-50 text-slate-700"
                      }`}
                    >
                      <div>
                        <div className="text-xs font-bold leading-tight">{org.name}</div>
                        <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-500">
                          <span className="font-mono">STIR: {org.inn}</span>
                          <span>•</span>
                          <span className="uppercase text-[9px] px-1 py-0.2 rounded bg-slate-100">
                            {org.mode}
                          </span>
                        </div>
                      </div>
                      {isSelected && <Check className="w-4 h-4 text-blue-600 shrink-0" />}
                    </button>
                  );
                })}
              </div>

              <div className="p-2 border-t border-slate-100 bg-slate-50/40">
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    setIsModalOpen(true);
                  }}
                  className="w-full flex items-center justify-center gap-1.5 py-2 px-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 shadow-2xs transition cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 text-blue-600" />
                  Yangi Tashkilot Qo'shish
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          {/* Signed-in user (role is assigned by the server) */}
          <UserMenu />

          {currentOrg && (
            <ModeToggle
              currentMode={currentOrg.mode}
              onToggle={onModeToggle}
            />
          )}

          <button
            onClick={onOpenAI}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-xs transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Tahlilchi</span>
          </button>
        </div>
      </header>

      {/* New Organization Modal */}
      <NewOrgModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};
export default Navbar;
