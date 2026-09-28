"use client";

import React, { useState } from "react";
import { AccountingMode } from "@/types/accounting";
import { BookOpen, Layers } from "lucide-react";

interface ModeToggleProps {
  currentMode: AccountingMode;
  onToggle: (newMode: AccountingMode) => void;
  disabled?: boolean;
}

export const ModeToggle: React.FC<ModeToggleProps> = ({ currentMode, onToggle, disabled }) => {
  const isBHMS = currentMode === "BHMS";

  return (
    <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onToggle("SIMPLE")}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
          !isBHMS
            ? "bg-white text-blue-700 shadow-sm"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        <Layers className="w-3.5 h-3.5" />
        <span>Oddiy rejim</span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onToggle("BHMS")}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
          isBHMS
            ? "bg-blue-700 text-white shadow-sm"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        <BookOpen className="w-3.5 h-3.5" />
        <span>BHMS Schotlar</span>
      </button>
    </div>
  );
};
