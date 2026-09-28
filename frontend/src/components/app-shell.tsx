"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Navbar } from "@/components/navbar";
import { AIAnalystPanel } from "@/components/ai-analyst-panel";
import { OrgProvider, useOrg } from "@/lib/org-context";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { AppLoader } from "@/components/app-loader";

const PUBLIC_ROUTES = ["/login"];

function ShellInner({ children }: { children: React.ReactNode }) {
  const { currentOrg, toggleMode, reportContext } = useOrg();
  const [isAIOpen, setIsAIOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 w-full">
      {/* Navigation Sidebar */}
      <Sidebar onOpenAI={() => setIsAIOpen(true)} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Navbar
          currentOrg={currentOrg}
          onModeToggle={toggleMode}
          onOpenAI={() => setIsAIOpen(true)}
        />

        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>

      {/* Global AI Assistant Drawer */}
      <AIAnalystPanel
        isOpen={isAIOpen}
        onClose={() => setIsAIOpen(false)}
        reportContext={reportContext}
      />
    </div>
  );
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_ROUTES.includes(pathname);

  useEffect(() => {
    if (!loading && !user && !isPublic) router.replace("/login");
  }, [loading, user, isPublic, router]);

  if (isPublic) return <>{children}</>;
  if (loading || !user) {
    return <div className="flex h-screen items-center justify-center text-sm text-slate-500">Yuklanmoqda...</div>;
  }

  // Organization data is only fetched once a user is authenticated
  return (
    <OrgProvider>
      <AppLoader />
      <ShellInner>{children}</ShellInner>
    </OrgProvider>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGate>{children}</AuthGate>
    </AuthProvider>
  );
}

export default AppShell;
