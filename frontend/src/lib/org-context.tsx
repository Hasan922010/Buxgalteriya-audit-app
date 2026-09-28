"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { Organization, AccountingMode, UserRole } from "@/types/accounting";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

interface OrgContextType {
  organizations: Organization[];
  currentOrg: Organization | null;
  setCurrentOrg: (org: Organization | null) => void;
  switchOrg: (orgId: string) => void;
  refreshOrganizations: () => Promise<void>;
  createOrganization: (data: { name: string; inn: string; mode?: AccountingMode; vat_payer?: boolean }) => Promise<Organization>;
  resetOrgData: (orgId: string) => Promise<void>;
  factoryReset: (confirmation: string) => Promise<void>;
  // Role of the authenticated user (read-only: it comes from the server, not the UI)
  currentRole: UserRole;
  reportContext: Record<string, any>;
  setReportContext: (ctx: Record<string, any>) => void;
  toggleMode: (newMode: AccountingMode) => Promise<void>;
  lockPeriod: (lockedUntilDate: string | null) => Promise<void>;
}

const OrgContext = createContext<OrgContextType>({
  organizations: [],
  currentOrg: null,
  setCurrentOrg: () => {},
  switchOrg: () => {},
  refreshOrganizations: async () => {},
  createOrganization: async () => ({} as Organization),
  resetOrgData: async () => {},
  factoryReset: async () => {},
  currentRole: "AUDITOR",
  reportContext: {},
  setReportContext: () => {},
  toggleMode: async () => {},
  lockPeriod: async () => {},
});

export const OrgProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null);
  const { user } = useAuth();
  const currentRole: UserRole = user?.role ?? "AUDITOR";
  const [reportContext, setReportContext] = useState<Record<string, any>>({});

  const refreshOrganizations = async () => {
    try {
      const orgs = await apiClient.getOrganizations();
      setOrganizations(orgs);

      // Check saved org ID from localStorage
      const savedOrgId = typeof window !== "undefined" ? localStorage.getItem("selected_org_id") : null;
      if (savedOrgId) {
        const found = orgs.find((o) => o.id === savedOrgId);
        if (found) {
          setCurrentOrg(found);
          return;
        }
      }

      if (orgs.length > 0 && !currentOrg) {
        setCurrentOrg(orgs[0]);
        if (typeof window !== "undefined") {
          localStorage.setItem("selected_org_id", orgs[0].id);
        }
      }
    } catch (err) {
      console.error("Tashkilotlar yuklanmadi:", err);
    }
  };

  useEffect(() => {
    refreshOrganizations();
  }, []);

  const switchOrg = (orgId: string) => {
    const found = organizations.find((o) => o.id === orgId);
    if (found) {
      setCurrentOrg(found);
      if (typeof window !== "undefined") {
        localStorage.setItem("selected_org_id", found.id);
      }
    }
  };

  const createOrganization = async (data: { name: string; inn: string; mode?: AccountingMode; vat_payer?: boolean }) => {
    const newOrg = await apiClient.createOrganization(data);
    await refreshOrganizations();
    switchOrg(newOrg.id);
    return newOrg;
  };

  const resetOrgData = async (orgId: string) => {
    await apiClient.resetOrganizationData(orgId);
    await refreshOrganizations();
    const found = organizations.find((o) => o.id === orgId);
    if (found) setCurrentOrg(found);
  };

  const factoryReset = async (confirmation: string) => {
    await apiClient.factoryResetSystem(confirmation);
    localStorage.removeItem("selected_org_id");
    await refreshOrganizations();
  };

  const toggleMode = async (newMode: AccountingMode) => {
    if (!currentOrg) return;
    try {
      const updated = await apiClient.toggleOrganizationMode(currentOrg.id, newMode);
      setCurrentOrg(updated);
      await refreshOrganizations();
    } catch (err: any) {
      alert(err.message || "Rejimni o'zgartirishda xato yuz berdi");
    }
  };

  const lockPeriod = async (lockedUntilDate: string | null) => {
    if (!currentOrg) return;
    try {
      const updated = await apiClient.lockOrganizationPeriod(currentOrg.id, lockedUntilDate);
      setCurrentOrg(updated);
      await refreshOrganizations();
    } catch (err: any) {
      alert(err.message || "Davrni qulflashda xato yuz berdi");
    }
  };

  return (
    <OrgContext.Provider
      value={{
        organizations,
        currentOrg,
        setCurrentOrg,
        switchOrg,
        refreshOrganizations,
        createOrganization,
        resetOrgData,
        factoryReset,
        currentRole,
        reportContext,
        setReportContext,
        toggleMode,
        lockPeriod,
      }}
    >
      {children}
    </OrgContext.Provider>
  );
};

export const useOrg = () => useContext(OrgContext);
