/**
 * valuationHistory.ts
 *
 * Helpers for working with per-item valuation history from
 * public.item_valuation_history (Supabase).
 *
 * This module does NOT fetch data by itself; it just transforms
 * rows into useful series for charts (per-item and portfolio).
 */

import type { CurrencyCode } from '@/data/types';

export type RawItemValuationRow = {
  id: string;
  user_id: string;
  item_id: string;
  as_of: string; // ISO timestamp
  estimated_value: number;
  currency: CurrencyCode;
  source: string | null;
  confidence: number | null;
  created_at: string;
};

export type ItemSeriesPoint = {
  asOf: string; // ISO date (YYYY-MM-DD) for daily aggregate
  value: number;
};

export type PortfolioSeriesPoint = {
  date: string; // ISO date (YYYY-MM-DD)
  totalValue: number;
};

function toDateKey(asOf: string): string {
  const d = new Date(asOf);
  if (Number.isNaN(d.getTime())) return '';
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function safeNumber(x: unknown, fallback = 0): number {
  const n = typeof x === 'number' ? x : Number(x);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * Build a per-item daily series from raw valuation rows.
 *
 * Strategy:
 * - Group valuations by item_id + dateKey.
 * - For each (item, date) choose the latest valuation as the daily value.
 */
export function buildItemDailySeries(
  rows: RawItemValuationRow[],
): Record<string, ItemSeriesPoint[]> {
  const buckets: Record<
    string,
    Record<string, { asOf: string; value: number }>
  > = {};

  for (const row of rows) {
    const itemId = row.item_id;
    const dateKey = toDateKey(row.as_of);
    if (!dateKey) continue;

    const value = safeNumber(row.estimated_value, 0);
    if (value <= 0) continue;

    if (!buckets[itemId]) {
      buckets[itemId] = {};
    }

    const existing = buckets[itemId][dateKey];
    if (!existing) {
      buckets[itemId][dateKey] = { asOf: row.as_of, value };
    } else {
      // Keep the latest valuation for that day
      if (row.as_of > existing.asOf) {
        buckets[itemId][dateKey] = { asOf: row.as_of, value };
      }
    }
  }

  const result: Record<string, ItemSeriesPoint[]> = {};

  for (const [itemId, perDate] of Object.entries(buckets)) {
    const points: ItemSeriesPoint[] = Object.entries(perDate)
      .map(([dateKey, info]) => ({
        asOf: dateKey,
        value: info.value,
      }))
      .sort((a, b) => a.asOf.localeCompare(b.asOf));

    result[itemId] = points;
  }

  return result;
}

/**
 * Aggregate per-item daily series into a daily portfolio series.
 *
 * Input: all valuation rows for a user.
 * Output: per-day sum of item values.
 */
export function buildPortfolioDailySeries(
  rows: RawItemValuationRow[],
): PortfolioSeriesPoint[] {
  const perItemSeries = buildItemDailySeries(rows);

  const dateMap: Record<string, number> = {};

  for (const series of Object.values(perItemSeries)) {
    for (const point of series) {
      if (!dateMap[point.asOf]) {
        dateMap[point.asOf] = 0;
      }
      dateMap[point.asOf] += point.value;
    }
  }

  const series: PortfolioSeriesPoint[] = Object.entries(dateMap)
    .map(([date, totalValue]) => ({
      date,
      totalValue,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return series;
}
