"use client";

import React from "react";
import { Sparkles, Scale } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex-1 min-h-[60vh] flex flex-col items-center justify-center p-8 select-none">
      <div className="relative mb-5 flex items-center justify-center">
        {/* Outer glowing pulsing ring */}
        <div className="absolute w-20 h-20 rounded-full border-2 border-blue-500/20 border-t-blue-600 animate-spin" />
        <div className="absolute w-16 h-16 rounded-full border border-indigo-400/20 animate-pulse" />
        
        {/* Center Logo */}
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
          <Scale className="w-6 h-6 animate-pulse" />
        </div>

        {/* Sparkle badge */}
        <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center text-white shadow">
          <Sparkles className="w-2.5 h-2.5 animate-spin-slow" />
        </div>
      </div>

      <h3 className="text-sm font-bold text-slate-800 tracking-wide mb-1">
        Ma&apos;lumotlar yuklanmoqda...
      </h3>
      <p className="text-xs text-slate-500 font-medium animate-pulse">
        Tizim jadvallari va hisobotlari yangilanmoqda
      </p>

      {/* Mini glowing progress line */}
      <div className="w-48 h-1 bg-slate-200 rounded-full mt-4 overflow-hidden">
        <div className="h-full bg-gradient-to-r from-blue-600 to-indigo-600 rounded-full animate-shimmer w-full" />
      </div>
    </div>
  );
}
