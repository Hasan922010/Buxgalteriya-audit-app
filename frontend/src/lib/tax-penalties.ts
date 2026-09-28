import { TaxAuditItemRow, TaxPenaltySummary } from "@/types/accounting";

// Penalty calculation helper matching backend TaxAuditExtractor
export function calculatePenalties(items: TaxAuditItemRow[]): TaxPenaltySummary {
  const total_discrepancy_amount = items.reduce(
    (acc, it) => acc + (Number(it.diff_amount) || 0),
    0
  );
  const vat_amount =
    Math.round(((total_discrepancy_amount * 0.12) / 1.12) * 100) / 100;
  const net_tax_base = Math.round((total_discrepancy_amount - vat_amount) * 100) / 100;
  const profit_tax_addition = Math.round(net_tax_base * 0.15 * 100) / 100;
  const financial_penalty = Math.round(total_discrepancy_amount * 0.2 * 100) / 100;
  const total_budget_liability =
    Math.round((vat_amount + profit_tax_addition + financial_penalty) * 100) / 100;

  return {
    total_discrepancy_amount,
    vat_amount,
    net_tax_base,
    profit_tax_addition,
    financial_penalty,
    total_budget_liability,
  };
}
