/**
 * Portfolio Analytics Store (DB-optional, backend-optional)
 *
 * This provides the "legacy" API expected by the Analytics screen:
 *   - fetchPortfolioPL
 *   - fetchPortfolioSeries
 *   - fetchPortfolioAllocations
 *   - fetchPortfolioWinnersLosers
 *   - fetchPortfolioSnapshot
 *
 * Under the hood it:
 *   - Pulls timeseries + items from collectors-merge / Supabase when possible.
 *   - Falls back to deterministic demo data when offline.
 *   - Uses src/analytics/portfolioMetrics.ts for all computations.
 */

import {
  computeAllocationsFromItems,
  computePLFromSeries,
  computePortfolioSnapshot,
  computeWinnersAndLosers,
  type CategoryAllocation,
  type PortfolioItemSnapshot,
  type PortfolioPLSummary,
  type PortfolioSnapshot,
  type TimeSeriesPoint,
} from '@/analytics/portfolioMetrics';
import { logger } from '@/lib/logger';
import type {
  CollectorsClient,
  RawPortfolioTimeseriesPoint,
  RawPortfolioItem,
  RawPortfolioSet,
} from '@/../types/api';

let cachedSnapshot: PortfolioSnapshot | null = null;

/**
 * DEMO DATA
 * This lets analytics screens render even when the backend or DB are disabled.
 */

const DEMO_SERIES: TimeSeriesPoint[] = [
  { t: '2025-11-01T00:00:00Z', v: 1200 },
  { t: '2025-11-05T00:00:00Z', v: 1350 },
  { t: '2025-11-10T00:00:00Z', v: 1600 },
  { t: '2025-11-15T00:00:00Z', v: 1580 },
  { t: '2025-11-20T00:00:00Z', v: 1725 },
  { t: '2025-11-25T00:00:00Z', v: 1890 },
  { t: '2025-11-30T00:00:00Z', v: 2050 },
];

const DEMO_ITEMS: PortfolioItemSnapshot[] = [
  {
    id: 'demo-1',
    name: 'Black Lotus (Collector Demo)',
    category: 'mtg',
    collection: 'Power 9',
    quantity: 1,
    currentValue: 800,
    costBasis: 500,
    realizedPL: 0,
    unrealizedPL: 300,
    change1dPct: 0.04,
    change7dPct: 0.12,
    liquidityScore: 0.9,
    rarityScore: 0.98,
    completenessScore: 0.9,
    fraudRiskScore: 0.1,
  },
  {
    id: 'demo-2',
    name: 'Funko Pop – Demo Grail',
    category: 'funko',
    collection: 'NYCC Exclusives',
    quantity: 2,
    currentValue: 400,
    costBasis: 280,
    realizedPL: 0,
    unrealizedPL: 120,
    change1dPct: -0.01,
    change7dPct: 0.02,
    liquidityScore: 0.8,
    rarityScore: 0.75,
    completenessScore: 0.6,
    fraudRiskScore: 0.12,
  },
  {
    id: 'demo-3',
    name: 'Gunpla MG RX-78-2 (Ver. Ka)',
    category: 'gunpla',
    collection: 'MG Line',
    quantity: 1,
    currentValue: 280,
    costBasis: 220,
    realizedPL: 0,
    unrealizedPL: 60,
    change1dPct: 0.0,
    change7dPct: 0.03,
    liquidityScore: 0.7,
    rarityScore: 0.65,
    completenessScore: 0.5,
    fraudRiskScore: 0.08,
  },
  {
    id: 'demo-4',
    name: 'Lorcana Enchanted Demo Card',
    category: 'lorcana',
    collection: 'Enchanted',
    quantity: 1,
    currentValue: 570,
    costBasis: 450,
    realizedPL: 0,
    unrealizedPL: 120,
    change1dPct: 0.01,
    change7dPct: 0.07,
    liquidityScore: 0.85,
    rarityScore: 0.9,
    completenessScore: 0.7,
    fraudRiskScore: 0.15,
  },
];

// Set-completion demo: 2 partially completed sets.
const DEMO_SETS = [
  {
    setId: 'mtg-power9',
    setName: 'MTG – Power 9',
    ownedCount: 3,
    totalCount: 9,
  },
  {
    setId: 'lorcana-enchanted',
    setName: 'Disney Lorcana – Enchanted',
    ownedCount: 5,
    totalCount: 12,
  },
];

/**
 * Optional: collectors-merge API client.
 * We only import if the module exists; if not, the fallback will be used.
 */
let client: CollectorsClient | null = null;

try {
  // Dynamic require to avoid bundling issues if the client path changes.
   
  client = require('@/services/collectorsClient');
} catch (_e) {
  // best-effort: optional module. If it is absent every loader below returns
  // null/[] and the UI shows its empty state -- it no longer falls back to
  // fabricated demo data in production, so this is safe to swallow.
  client = null;
}

/**
 * Normalize whatever /portfolio/timeseries returns into TimeSeriesPoint[].
 *
 * Expected backend shapes (examples):
 *  - { points: [{ timestamp: '...', value: 123 }, ...] }
 *  - [{ t: '...', v: 123 }, ...]
 */
async function loadSeriesFromBackend(): Promise<TimeSeriesPoint[] | null> {
  if (!client || typeof client.getPortfolioTimeseries !== 'function') {
    return null;
  }

  try {
    const raw = await client.getPortfolioTimeseries!();

    if (!raw) return null;

    const points: RawPortfolioTimeseriesPoint[] = Array.isArray(raw)
      ? raw
      : Array.isArray((raw as Record<string, unknown>).points)
      ? (raw as Record<string, unknown>).points as RawPortfolioTimeseriesPoint[]
      : [];

    if (!points.length) return null;

    const mapped: TimeSeriesPoint[] = points.map((p: RawPortfolioTimeseriesPoint) => ({
      t: p.t ?? p.timestamp ?? new Date().toISOString(),
      v: Number(p.v ?? p.value ?? 0),
    }));

    return mapped;
  } catch (error) {
    logger.error('[portfolioAnalyticsStore] Timeseries backend error:', error);
    return null;
  }
}

/**
 * Normalize /portfolio/items into PortfolioItemSnapshot[].
 *
 * Expected backend item fields (flexible):
 * - id, name, category, collection
 * - quantity, current_value, cost_basis, realized_pl, unrealized_pl
 * - change_1d_pct, change_7d_pct, liquidity_score, rarity_score, fraud_risk_score
 */
async function loadItemsFromBackend(): Promise<PortfolioItemSnapshot[] | null> {
  if (!client || typeof client.getPortfolioItems !== 'function') {
    return null;
  }

  try {
    const raw = await client.getPortfolioItems!();

    const rawObj = raw as Record<string, unknown> | null;
    const items: RawPortfolioItem[] = Array.isArray(rawObj?.items)
      ? rawObj!.items as RawPortfolioItem[]
      : Array.isArray(raw)
      ? raw as RawPortfolioItem[]
      : [];

    if (!items.length) return null;

    const mapped: PortfolioItemSnapshot[] = items.map((it: RawPortfolioItem) => ({
      id: String(it.id ?? it.item_id ?? Math.random().toString(36).slice(2)),
      name: String(it.name ?? it.title ?? 'Untitled item'),
      category: String(it.category ?? it.category_slug ?? 'unknown'),
      collection: it.collection ?? it.set_name ?? undefined,
      quantity: typeof it.quantity === 'number' ? it.quantity : 1,
      currentValue: Number(
        it.current_value ??
          it.estimated_value ??
          it.value ??
          0,
      ),
      costBasis:
        typeof it.cost_basis === 'number' ? it.cost_basis : undefined,
      estimatedValue:
        typeof it.estimated_value === 'number'
          ? it.estimated_value
          : undefined,
      realizedPL:
        typeof it.realized_pl === 'number' ? it.realized_pl : undefined,
      unrealizedPL:
        typeof it.unrealized_pl === 'number'
          ? it.unrealized_pl
          : undefined,
      change1dPct:
        typeof it.change_1d_pct === 'number'
          ? it.change_1d_pct
          : undefined,
      change7dPct:
        typeof it.change_7d_pct === 'number'
          ? it.change_7d_pct
          : undefined,
      liquidityScore:
        typeof it.liquidity_score === 'number'
          ? it.liquidity_score
          : undefined,
      rarityScore:
        typeof it.rarity_score === 'number'
          ? it.rarity_score
          : undefined,
      completenessScore:
        typeof it.completeness_score === 'number'
          ? it.completeness_score
          : undefined,
      fraudRiskScore:
        typeof it.fraud_risk_score === 'number'
          ? it.fraud_risk_score
          : undefined,
    }));

    return mapped;
  } catch (error) {
    logger.error('[portfolioAnalyticsStore] Items backend error:', error);
    return null;
  }
}

/**
 * Optionally load set completion from backend; falls back to demo.
 */
async function loadSetsFromBackend(): Promise<
  { setId: string; setName: string; ownedCount: number; totalCount: number }[]
> {
  if (!client || typeof client.getPortfolioOverview !== 'function') {
    return __DEV__ ? DEMO_SETS : [];
  }

  try {
    const raw = await client.getPortfolioOverview!();
    const sets: RawPortfolioSet[] = Array.isArray(raw?.sets)
      ? raw.sets
      : Array.isArray(raw?.set_completion)
      ? raw.set_completion
      : [];

    if (!sets.length) return __DEV__ ? DEMO_SETS : [];

    return sets.map((s: RawPortfolioSet) => ({
      setId: String(s.set_id ?? s.id ?? 'unknown-set'),
      setName: String(s.set_name ?? s.name ?? 'Unknown set'),
      ownedCount: Number(s.owned_count ?? s.owned ?? 0),
      totalCount: Number(s.total_count ?? s.total ?? 1),
    }));
  } catch (error) {
    // logger.error, not warn: warn is stripped in release builds, so a backend
    // failure here left no trace at all in exactly the build that matters.
    logger.error('[portfolioAnalyticsStore] Sets backend error:', error);
    return __DEV__ ? DEMO_SETS : [];
  }
}

/**
 * PUBLIC API – used directly by analytics screens.
 */

/**
 * Returns the canonical timeseries used by portfolio charts.
 */
export async function fetchPortfolioSeries(): Promise<TimeSeriesPoint[]> {
  const series = await loadSeriesFromBackend();
  if (!series || !series.length) {
    // __DEV__-gated, matching the DEMO_ITEMS fix in fetchPortfolioSnapshot.
    // Returning DEMO_SERIES unconditionally drew a fabricated 1200 -> 2050
    // curve as the user's real portfolio whenever the backend failed or was
    // empty, with only a stripped logger.warn to show for it. [] renders the
    // empty state, which is the honest answer.
    return __DEV__ ? DEMO_SERIES : [];
  }
  return series;
}

/**
 * Returns the computed P/L summary from the underlying series.
 */
export async function fetchPortfolioPL(): Promise<PortfolioPLSummary> {
  const series = await fetchPortfolioSeries();
  return computePLFromSeries(series);
}

/**
 * Returns category allocations (value and weights) from items.
 */
export async function fetchPortfolioAllocations(): Promise<CategoryAllocation[]> {
  // __DEV__ gate added 2026-05-25: in production, empty backend → empty
  // snapshot. The DEMO_ITEMS fallback was leaking fake Pokemon/LEGO/Hot Toys
  // portfolio data into TestFlight for any user with 0 items.
  const items =
    (await loadItemsFromBackend()) ??
    (__DEV__ ? DEMO_ITEMS : []);

  return computeAllocationsFromItems(items);
}

/**
 * Returns winners/losers buckets based on 1D percentage moves.
 */
export async function fetchPortfolioWinnersLosers(): Promise<{
  winners: PortfolioItemSnapshot[];
  losers: PortfolioItemSnapshot[];
  neutral: PortfolioItemSnapshot[];
}> {
  // __DEV__ gate added 2026-05-25: in production, empty backend → empty
  // snapshot. The DEMO_ITEMS fallback was leaking fake Pokemon/LEGO/Hot Toys
  // portfolio data into TestFlight for any user with 0 items.
  const items =
    (await loadItemsFromBackend()) ??
    (__DEV__ ? DEMO_ITEMS : []);

  return computeWinnersAndLosers(items);
}

/**
 * Returns a full snapshot: PL, series, allocations, winners/losers, tiering, items.
 * This is the richest endpoint; all others can be derived from this.
 */
export async function fetchPortfolioSnapshot(): Promise<PortfolioSnapshot> {
  const [series, items, sets] = await Promise.all([
    fetchPortfolioSeries(),
    (async () => (await loadItemsFromBackend()) ?? (__DEV__ ? DEMO_ITEMS : []))(),
    loadSetsFromBackend(),
  ]);

  const snapshot = computePortfolioSnapshot({
    series,
    items,
    sets,
  });

  cachedSnapshot = snapshot;
  return snapshot;
}

/**
 * Lightweight read-only access to the last computed snapshot.
 * Returns null if fetchPortfolioSnapshot hasn't been called yet.
 */
export function getCachedPortfolioSnapshot(): PortfolioSnapshot | null {
  return cachedSnapshot;
}
