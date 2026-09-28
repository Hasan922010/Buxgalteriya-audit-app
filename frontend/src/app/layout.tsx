import type { Metadata } from "next";
import React from "react";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "Yordamchi Buxgalter AI - Fintech & Audit Platform",
  description: "O'zbekiston BHMS va Soliq standartlari uchun aqlli moliyaviy audit platformasi",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="uz">
      <body className="antialiased font-sans">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
