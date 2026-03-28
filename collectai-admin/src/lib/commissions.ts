// ---------------------------------------------------------------------------
// Commission Tracker — calculates creator payouts from revenue data
// ---------------------------------------------------------------------------

import type { CreatorRow } from "./kpi";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface CommissionEntry {
  creatorName: string;
  handle: string;
  language: string;
  affiliateCode: string;
  grossRevenue: number;
  commissionRate: number;     // percentage (e.g., 15)
  commissionAmount: number;   // EUR
  kitsSentCost: number;       // seed kit COGS
  netToCreator: number;       // commission amount
  netToCompany: number;       // revenue - commission - COGS
  roi: number;                // netToCompany / (kitsSentCost + commissionAmount)
  orders: number;
  status: "pending" | "approved" | "paid";
}

export interface CommissionSummary {
  entries: CommissionEntry[];
  totalRevenue: number;
  totalCommissions: number;
  totalCOGS: number;
  totalNetProfit: number;
  avgCommissionRate: number;
  avgROI: number;
  periodLabel: string;
}

// ─── Calculator ─────────────────────────────────────────────────────────────

export function calculateCommissions(
  creators: CreatorRow[],
  periodLabel: string,
): CommissionSummary {
  const entries: CommissionEntry[] = creators
    .filter((c) => c.revenue > 0 || c.kitsSent > 0)
    .map((c) => {
      const commissionAmount = Math.round(c.revenue * (c.affiliatePayoutPct / 100) * 100) / 100;
      const kitsCost = c.kitsSent * c.cogsPerKit;
      const netToCompany = Math.round((c.revenue - commissionAmount - kitsCost) * 100) / 100;
      const totalInvestment = kitsCost + commissionAmount;
      return {
        creatorName: c.name,
        handle: c.handle,
        language: c.language,
        affiliateCode: c.affiliateCode,
        grossRevenue: c.revenue,
        commissionRate: c.affiliatePayoutPct,
        commissionAmount,
        kitsSentCost: kitsCost,
        netToCreator: commissionAmount,
        netToCompany,
        roi: totalInvestment > 0 ? Math.round((netToCompany / totalInvestment) * 100) / 100 : 0,
        orders: c.purchases,
        status: "pending" as const,
      };
    })
    .sort((a, b) => b.grossRevenue - a.grossRevenue);

  const totalRevenue = entries.reduce((s, e) => s + e.grossRevenue, 0);
  const totalCommissions = entries.reduce((s, e) => s + e.commissionAmount, 0);
  const totalCOGS = entries.reduce((s, e) => s + e.kitsSentCost, 0);

  return {
    entries,
    totalRevenue,
    totalCommissions,
    totalCOGS,
    totalNetProfit: Math.round((totalRevenue - totalCommissions - totalCOGS) * 100) / 100,
    avgCommissionRate: entries.length > 0
      ? Math.round((entries.reduce((s, e) => s + e.commissionRate, 0) / entries.length) * 10) / 10
      : 0,
    avgROI: entries.length > 0
      ? Math.round((entries.reduce((s, e) => s + e.roi, 0) / entries.length) * 100) / 100
      : 0,
    periodLabel,
  };
}

export function exportCommissionsCSV(summary: CommissionSummary): string {
  const headers = [
    "Creator", "Handle", "Language", "Code", "Orders",
    "Revenue (EUR)", "Commission %", "Commission (EUR)",
    "Kits COGS (EUR)", "Net to Company (EUR)", "ROI", "Status",
  ];
  const rows = summary.entries.map((e) => [
    e.creatorName, e.handle, e.language, e.affiliateCode, e.orders,
    e.grossRevenue.toFixed(2), e.commissionRate, e.commissionAmount.toFixed(2),
    e.kitsSentCost.toFixed(2), e.netToCompany.toFixed(2),
    `${e.roi}x`, e.status,
  ]);
  return [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
}
