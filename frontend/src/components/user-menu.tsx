"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, ShieldCheck } from "lucide-react";
import { UserRole } from "@/types/accounting";
import { useAuth } from "@/lib/auth-context";

const ROLE_INFO: Record<UserRole, { label: string; badge: string; color: string }> = {
  CHIEF_ACCOUNTANT: { label: "Bosh buxgalter", badge: "Bosh", color: "text-blue-700 bg-blue-50 border-blue-200" },
  OPERATOR: { label: "Kassir / Operator", badge: "Operator", color: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  AUDITOR: { label: "Auditor / Nazoratchi", badge: "Auditor", color: "text-purple-700 bg-purple-50 border-purple-200" },
  DIRECTOR: { label: "Rahbar / Direktor", badge: "Direktor", color: "text-amber-700 bg-amber-50 border-amber-200" },
};

/** Shows the signed-in user and their (server-assigned) role, with a logout action. */
export function UserMenu() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!user) return null;
  const role = ROLE_INFO[user.role];
  const displayName = user.full_name || user.username;

  const handleLogout = () => {
    setIsOpen(false);
    logout();
    router.replace("/login");
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-all text-xs font-medium text-slate-700 shadow-2xs cursor-pointer"
      >
        <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
        <span className="font-semibold text-slate-800 max-w-[140px] truncate">{displayName}</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${role.color}`}>{role.badge}</span>
        <ChevronDown className="w-3 h-3 text-slate-400" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-64 rounded-2xl bg-white border border-slate-200 shadow-xl py-1 z-50">
          <div className="px-3 py-2 border-b border-slate-100 space-y-0.5">
            <p className="text-xs font-bold text-slate-800 truncate">{displayName}</p>
            <p className="text-[11px] text-slate-500">
              @{user.username} · {role.label}
              {user.is_superuser && " · Administrator"}
            </p>
          </div>
          <div className="p-1">
            <button
              type="button"
              onClick={handleLogout}
              className="w-full text-left px-3 py-2 rounded-xl text-xs flex items-center gap-2 text-rose-700 hover:bg-rose-50 transition-colors cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              Chiqish
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserMenu;
