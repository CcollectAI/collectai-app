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
import {
  getPortfolioItems,
  getPortfolioTimeseries,
} from '@/api/portfolioApi';
import type {
  RawPortfolioTimeseriesPoint,
  RawPortfolioItem,
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

/**
 * Portfolio reads go through the app's ONE authenticated client.
 *
 * They used to go through `src/services/collectorsClient.ts`, reached by a
 * guarded `require`. That module is a second HTTP client: it sends `X-API-Key`
 * (which is `EXPO_PUBLIC_API_KEY ?? ''`, i.e. empty) and **no Authorization
 * header at all**, and its bare `fetch` has no timeout and no AbortController.
 *
 * Every `/portfolio/*` route requires a bearer token, so those calls 401'd —
 * always, for every user. Prod bake.log: `/portfolio/items` had 4 requests and
 * 4 × 401 with not one 200, while `/portfolio/overview` showed 193 × 200 from
 * the httpClient callers on the very same endpoint. Each loader below catches
 * and returns null, so the failure was silent and analytics simply computed an
 * empty portfolio for everyone.
 *
 * `httpClient` supplies the bearer, the single-flight 401 refresh and
 * REQUEST_TIMEOUT_MS — the three things the duplicate lacked. ARCHITECTURE.md
 * names `src/api/` as the API client; `collectorsClient` is documented nowhere.
 */
/**
 * Normalize whatever /portfolio/timeseries returns into TimeSeriesPoint[].
 *
 * Expected backend shapes (examples):
 *  - { points: [{ timestamp: '...', value: 123 }, ...] }
 *  - [{ t: '...', v: 123 }, ...]
 */
async function loadSeriesFromBackend(): Promise<TimeSeriesPoint[] | null> {
  try {
    // A range is REQUIRED: the old call passed none, so the duplicate client
    // built `?range=undefined`.
    const raw = await getPortfolioTimeseries('30d');

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
    // THROW. null here fell to [] in fetchPortfolioSeries, and analytics
    // computed an empty portfolio from a failed read — the silence the header
    // above describes. fetchPortfolioSnapshot's callers catch (analytics via
    // useAsync → its error state; Home's mock branch).
    throw error instanceof Error ? error : new Error('Could not load portfolio history');
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
  try {
    const raw = await getPortfolioItems();

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
      // `collection_name`, which is what /portfolio/items sends. This read
      // used to be `it.collection ?? it.set_name` — the endpoint has never
      // sent either, so `collection` was undefined for every item on every
      // account, set completion computed over an empty list, and the Portfolio
      // Tier could not leave "Unranked". Gate: check:phantom-response-fields.
      collection: it.collection_name ?? undefined,
      // `sets.total_items`. Nullable on purpose: null is "we hold no catalogue
      // row for this set", NOT a set of size 0 (see `hasKnownSetSize`).
      setSize: typeof it.set_size === 'number' ? it.set_size : null,
      // phantom-ok: /portfolio/items does not SELECT items.quantity, though the
      // column exists — so every analytics item counts as 1. Reading it here is
      // harmless and correct the day the endpoint sends it; inventing a
      // multiplier would not be.
      quantity: typeof it.quantity === 'number' ? it.quantity : 1,
      currentValue: Number(
        it.current_value ??
          it.estimated_value ??
          it.value ??
          0,
      ),
      costBasis:
        typeof it.cost_basis === 'number' ? it.cost_basis : undefined,
      // phantom-ok: /portfolio/items sends `current_value`, already resolved through the value chain; `estimated_value` is another caller's shape.
      estimatedValue:
        typeof it.estimated_value === 'number'
          ? it.estimated_value
          : undefined,
      // phantom-ok: realised P/L is its own endpoint (/portfolio/realised-pl), never a field on an item row.
      realizedPL:
        typeof it.realized_pl === 'number' ? it.realized_pl : undefined,
      unrealizedPL:
        typeof it.unrealized_pl === 'number'
          ? it.unrealized_pl
          : undefined,
      // The server COALESCEs a missing band to 0, so 0 has to mean "no band"
      // here or every unpriced item would claim a EUR 0 floor.
      q10: typeof it.q10 === 'number' && it.q10 > 0 ? it.q10 : undefined,
      q90: typeof it.q90 === 'number' && it.q90 > 0 ? it.q90 : undefined,
      // FALSE means `unrealizedPL` is model drift, not profit — the server
      // falls back to the earliest prediction as cost basis when no purchase
      // price is on file. Anything summing P/L into a headline must exclude
      // these, or it reports a number the member never earned.
      hasPurchasePrice: it.has_purchase_price === true,
      valueSource:
        typeof it.value_source === 'string' ? it.value_source : undefined,
      // WHICH MARKET the comps behind this item came from: 'US' | 'EU' |
      // 'mixed', or undefined when we cannot tell. EU and US price the same
      // card ~31% apart and we blend them, converting to EUR at ingest -- so
      // the currency column reads 'EUR' for all of it and the provider names
      // are the only surviving signal. Server-side map:
      // server/app/lib/comp_market.py, pinned to src/lib/compProvenance.ts.
      market: typeof it.market === 'string' ? it.market : undefined,
      change1dPct:
        typeof it.change_1d_pct === 'number'
          ? it.change_1d_pct
          : undefined,
      change7dPct:
        typeof it.change_7d_pct === 'number'
          ? it.change_7d_pct
          : undefined,
      // phantom-ok: never sent by any server build; kept for the Signals proxy shape.
      liquidityScore:
        typeof it.liquidity_score === 'number'
          ? it.liquidity_score
          : undefined,
      // UNDEFINED, never 0, when the server omits it: `computeAverageRarityScore`
      // skips a non-number, so an unknown item is left out of the average
      // instead of dragging it to zero. The server omits the key precisely so
      // this stays possible.
      rarityScore:
        typeof it.rarity_score === 'number'
          ? it.rarity_score
          : undefined,
      raritySource:
        it.rarity_source === 'catalog' || it.rarity_source === 'item'
          ? it.rarity_source
          : undefined,
      // phantom-ok: per-ITEM completeness is not a thing the server computes; set completion is per-collection, derived below.
      completenessScore:
        typeof it.completeness_score === 'number'
          ? it.completeness_score
          : undefined,
      // phantom-ok: never sent by any server build; kept for the Signals proxy shape.
      fraudRiskScore:
        typeof it.fraud_risk_score === 'number'
          ? it.fraud_risk_score
          : undefined,
    }));

    return mapped;
  } catch (error) {
    logger.error('[portfolioAnalyticsStore] Items backend error:', error);
    // THROW, same reason: `?? []` in every caller turned a failure into "you own nothing".
    throw error instanceof Error ? error : new Error('Could not load portfolio items');
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
  const [series, items] = await Promise.all([
    fetchPortfolioSeries(),
    (async () => (await loadItemsFromBackend()) ?? (__DEV__ ? DEMO_ITEMS : []))(),
  ]);

  // Set completion is DERIVED from these items inside computePortfolioSnapshot
  // — nothing to fetch and nothing a caller can forget to pass.
  const snapshot = computePortfolioSnapshot({
    series,
    items,
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
