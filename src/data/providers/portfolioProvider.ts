/**
 * Portfolio domain provider — portfolio summary queries.
 */

import type { PortfolioSummary } from '../types';
import { getPortfolioOverview } from '../../api/portfolioApi';
import { supabase } from '../../lib/supabase';
import logger from '../../utils/logger';

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  // Reads /portfolio/overview, NOT the `portfolio_values` table.
  //
  // Fixed 2026-07-24: `portfolio_values` has no writer anywhere — not in the
  // server, the app, a migration, a DB function or pg_cron — so it is empty in
  // prod. The old implementation selected from it, found 0 rows, and returned
  // `{total: 0, deltaPct: 0}`. Home's insights card (usePortfolioInsights →
  // app/(tabs)/index.tsx) derives its change figure from `deltaPct`, so the
  // portfolio change was structurally pinned at EUR 0 / +0.00% regardless of
  // what the collection did. The 2026-07-24 portfolio pass (f9195fe) repaired
  // the timeseries path, not this summary path.
  //
  // The overview endpoint values items with
  // COALESCE(q50, predicted_price_eur, estimated_value, 0) — the same
  // valuation the Items tab and category breakdown use — so the number here
  // now agrees with the rest of the app instead of being independently wrong.
  try {
    const snapshot = await getPortfolioOverview();

    // change_1d_pct is a FRACTION on the wire; PortfolioSummary.deltaPct is a
    // PERCENT (the hook divides by 100 again). Convert exactly once here.
    const deltaPct = (snapshot.change_1d_pct ?? 0) * 100;

    return {
      total: snapshot.total_value ?? 0,
      deltaPct,
      itemCount: snapshot.item_count ?? 0,
    };
  } catch (err) {
    logger.warn('[SupabaseDataProvider] getPortfolioSummary overview error:', err);

    // Fall back to a Supabase item count so the card can still show a total
    // rather than collapsing to an empty-collection state on a transient 401.
    const { count } = await supabase
      .from('items')
      .select('id', { count: 'exact', head: true });

    return { total: 0, deltaPct: 0, itemCount: count ?? 0 };
  }
}
