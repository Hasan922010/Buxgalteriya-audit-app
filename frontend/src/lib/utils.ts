import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number | string | undefined | null): string {
  if (amount === undefined || amount === null) return "0,00 so'm";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return "0,00 so'm";
  return new Intl.NumberFormat("uz-UZ", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num) + " so'm";
}

export function formatQuantity(qty: number | string | undefined | null, unit: string = "dona"): string {
  if (qty === undefined || qty === null) return `0 ${unit}`;
  const num = typeof qty === "string" ? parseFloat(qty) : qty;
  if (isNaN(num)) return `0 ${unit}`;
  return new Intl.NumberFormat("uz-UZ", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(num) + ` ${unit}`;
}

export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("uz-UZ", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return dateStr;
  }
}
