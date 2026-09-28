"use client";

import React, { useEffect, useState } from "react";
import {
  Sparkles,
  ShieldCheck,
  Scale,
  Database,
  CheckCircle2,
  Cpu,
  ChevronRight,
  Server,
  Zap,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface StepItem {
  id: number;
  label: string;
  sub: string;
  icon: React.ElementType;
}

const STEPS: StepItem[] = [
  {
    id: 1,
    label: "Tizim yadrosi & Xavfsizlik",
    sub: "Kriptografik himoya va muhit",
    icon: ShieldCheck,
  },
  {
    id: 2,
    label: "BHMS & Soliq Qoidalari",
    sub: "21-hisoblar rejasi, QQS 12%",
    icon: Scale,
  },
  {
    id: 3,
    label: "FastAPI & Ma'lumotlar Bazasi",
    sub: "Kassa, bank va balans jadvallari",
    icon: Database,
  },
  {
    id: 4,
    label: "AI Tahlilchi & Audit Tizimi",
    sub: "DeepSeek / Gemini intellektual tahlil",
    icon: Sparkles,
  },
];

export const AppLoader: React.FC = () => {
  const [isVisible, setIsVisible] = useState(true);
  const [isExiting, setIsExiting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeStep, setActiveStep] = useState(0);
  const [statusMessage, setStatusMessage] = useState("Tizim ishga tushirilmoqda...");
  const [runId, setRunId] = useState(1);
  const backendReadyRef = React.useRef(false);

  useEffect(() => {
    const handleReplay = () => {
      setIsExiting(false);
      setIsVisible(true);
      setProgress(0);
      setActiveStep(0);
      setRunId((prev) => prev + 1);
    };
    window.addEventListener("replay-app-loader", handleReplay);
    return () => window.removeEventListener("replay-app-loader", handleReplay);
  }, []);

  useEffect(() => {
    let isCancelled = false;
    backendReadyRef.current = false;

    // Async backend health ping
    apiClient
      .getOrganizations()
      .then(() => {
        if (!isCancelled) backendReadyRef.current = true;
      })
      .catch(() => {
        // Backend might still be starting or offline; proceed gracefully
        if (!isCancelled) backendReadyRef.current = true;
      });

    // Animate progress smoothly
    let current = 0;
    const interval = setInterval(() => {
      if (isCancelled) return;

      if (current < 80) {
        current += Math.floor(Math.random() * 6) + 4;
        if (current > 80) current = 80;
      } else if (current >= 80 && current < 98) {
        if (backendReadyRef.current) {
          current += 6;
        } else {
          current += 1;
        }
      } else if (current >= 98) {
        current = 100;
      }

      setProgress(Math.min(current, 100));

      // Determine active step based on progress
      if (current < 25) {
        setActiveStep(0);
        setStatusMessage("Tizim yadrosi va xavfsizlik protokollari ishga tushirilmoqda...");
      } else if (current < 55) {
        setActiveStep(1);
        setStatusMessage("BHMS va O'zbekiston soliq standartlari yuklanmoqda...");
      } else if (current < 80) {
        setActiveStep(2);
        setStatusMessage("FastAPI serveri va ma'lumotlar bazasi sinxronlanmoqda...");
      } else if (current < 100) {
        setActiveStep(3);
        setStatusMessage("AI Tahlilchi va moliyaviy audit moduli tayyorlanmoqda...");
      } else {
        setActiveStep(4);
        setStatusMessage("Tizim to'liq tayyor! Boshqaruv paneli ochilmoqda...");
      }

      if (current >= 100) {
        clearInterval(interval);
        // Graceful exit transition
        setTimeout(() => {
          if (!isCancelled) {
            setIsExiting(true);
            setTimeout(() => {
              if (!isCancelled) setIsVisible(false);
            }, 600);
          }
        }, 400);
      }
    }, 70);

    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [runId]);

  const handleSkip = () => {
    setIsExiting(true);
    setTimeout(() => setIsVisible(false), 500);
  };

  if (!isVisible) return null;

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col justify-between bg-slate-950 text-white select-none transition-all duration-700 ease-out overflow-hidden ${
        isExiting ? "opacity-0 scale-105 pointer-events-none" : "opacity-100 scale-100"
      }`}
    >
      {/* Dynamic Background Glows */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-600/20 rounded-full blur-[120px] pointer-events-none animate-pulse-glow" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-[420px] h-[420px] bg-indigo-600/20 rounded-full blur-[140px] pointer-events-none animate-pulse-glow" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-emerald-500/10 rounded-full blur-[100px] pointer-events-none" />

      {/* Cybernetic Grid Overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, #ffffff 1px, transparent 0)`,
          backgroundSize: "28px 28px",
        }}
      />

      {/* Top Bar with Brand and Quick Skip */}
      <div className="relative z-10 w-full px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-xs font-mono font-medium tracking-wider text-slate-400 uppercase">
            Fintech Engine v1.0.0
          </span>
        </div>

        <button
          onClick={handleSkip}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-medium border border-slate-800/80 transition-all shadow-sm group"
        >
          <span>Darhol o&apos;tish</span>
          <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
        </button>
      </div>

      {/* Center Branding & Progress Section */}
      <div className="relative z-10 flex flex-col items-center justify-center max-w-xl mx-auto w-full px-6 text-center my-auto py-2">
        {/* Animated Central Emblem */}
        <div className="relative mb-5 flex items-center justify-center">
          {/* Outer Rotating Dashed Ring */}
          <div className="absolute w-28 h-28 rounded-full border border-dashed border-blue-500/30 animate-spin-slow" />
          {/* Counter Rotating Ring */}
          <div className="absolute w-24 h-24 rounded-full border border-indigo-400/40 animate-spin-slow-reverse" />
          
          {/* Glowing Aura */}
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-500 to-sky-400 blur-xl opacity-60 animate-pulse-glow" />

          {/* Core Logo Container */}
          <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-0.5 shadow-2xl border border-blue-500/40 flex items-center justify-center animate-float-slow">
            <div className="w-full h-full rounded-2xl bg-gradient-to-br from-blue-600 via-indigo-600 to-blue-700 flex flex-col items-center justify-center text-white relative overflow-hidden">
              {/* Shimmer Light across logo */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
              <span className="text-2xl font-black tracking-wider drop-shadow-md">YB</span>
              <span className="text-[9px] font-bold text-blue-200 uppercase tracking-widest -mt-1">AUDIT</span>
            </div>
            {/* Sparkle badge */}
            <div className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-blue-500 border-2 border-slate-950 flex items-center justify-center text-white shadow-lg shadow-blue-500/50">
              <Sparkles className="w-3 h-3 animate-spin-slow" />
            </div>
          </div>
        </div>

        {/* Title & Description */}
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-blue-100 to-slate-300 bg-clip-text text-transparent mb-1.5">
          Yordamchi Buxgalter AI
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 font-medium mb-3 max-w-md">
          O&apos;zbekiston hisob standartlari (BHMS) va Soliq.uz uchun aqlli moliyaviy audit platformasi
        </p>

        {/* Status Pill Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-950/80 border border-blue-800/50 text-blue-300 text-[11px] font-mono mb-5 shadow-inner">
          <Zap className="w-3 h-3 text-blue-400 animate-pulse" />
          <span>{statusMessage}</span>
        </div>

        {/* Progress Bar Container */}
        <div className="w-full mb-5">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2 px-1">
            <span className="flex items-center gap-1.5 text-blue-400 font-semibold">
              <Cpu className="w-3.5 h-3.5" />
              <span>Yuklanish holati</span>
            </span>
            <span className="font-bold text-slate-200">{progress}%</span>
          </div>

          <div className="relative w-full h-2.5 bg-slate-900/90 rounded-full overflow-hidden p-0.5 border border-slate-800 shadow-inner">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-600 via-indigo-500 to-emerald-400 transition-all duration-200 ease-out relative"
              style={{ width: `${progress}%` }}
            >
              {/* Moving shine bar */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer" />
            </div>
          </div>
        </div>

        {/* Step-by-Step Status Cards */}
        <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            const isCompleted = activeStep > idx;
            const isCurrent = activeStep === idx;

            return (
              <div
                key={step.id}
                className={`p-2.5 rounded-xl border transition-all duration-300 flex items-start gap-2.5 ${
                  isCompleted
                    ? "bg-slate-900/70 border-emerald-500/40 text-slate-300"
                    : isCurrent
                    ? "bg-blue-950/40 border-blue-500/50 text-white shadow-lg shadow-blue-500/10 ring-1 ring-blue-500/30"
                    : "bg-slate-900/30 border-slate-800/60 text-slate-500 opacity-60"
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-lg shrink-0 flex items-center justify-center transition-colors mt-0.5 ${
                    isCompleted
                      ? "bg-emerald-500/20 text-emerald-400"
                      : isCurrent
                      ? "bg-blue-500/20 text-blue-400 animate-pulse"
                      : "bg-slate-800/50 text-slate-600"
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Icon className="w-3.5 h-3.5" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-xs font-semibold leading-tight text-slate-200">
                      {step.label}
                    </p>
                    <span
                      className={`text-[9px] font-mono font-medium px-1.5 py-0.2 rounded shrink-0 ${
                        isCompleted
                          ? "bg-emerald-500/20 text-emerald-400"
                          : isCurrent
                          ? "bg-blue-500/20 text-blue-300"
                          : "text-slate-600"
                      }`}
                    >
                      {isCompleted ? "Tayyor ✓" : isCurrent ? "Yuklanmoqda..." : "Kutilmoqda"}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-0.5 leading-snug">
                    {step.sub}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Footer Info */}
      <div className="relative z-10 w-full px-6 py-4 flex flex-col sm:flex-row items-center justify-between border-t border-slate-900/80 text-[11px] text-slate-500 gap-2">
        <div className="flex items-center gap-2">
          <Server className="w-3.5 h-3.5 text-slate-400" />
          <span>Server: FastAPI Microservice (Port 8000)</span>
          <span className="text-slate-700">•</span>
          <span className="text-emerald-400 font-medium">Ulanish: SSL/TLS Himoyalangan</span>
        </div>

        <div className="flex items-center gap-3">
          <span>O&apos;zbekiston Soliq & BHMS Standartlari</span>
          <span className="text-slate-700">•</span>
          <span className="text-blue-400">© 2026 Yordamchi Buxgalter</span>
        </div>
      </div>
    </div>
  );
};
