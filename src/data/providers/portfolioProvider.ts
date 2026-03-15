/**
 * Portfolio domain provider — portfolio summary queries.
 */

import { API_LIMITS } from '@/constants/apiLimits';
import type { PortfolioSummary } from '../types';
import { supabase } from '../../lib/supabase';
import logger from '../../utils/logger';

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  // Fetch portfolio values series
  const { data: valuesData, error: valuesError } = await supabase
    .from('portfolio_values')
    .select('at,value')
    .order('at', { ascending: true })
    .limit(API_LIMITS.PORTFOLIO_VALUES_DAYS);

  if (valuesError) {
    logger.warn('[SupabaseDataProvider] getPortfolioSummary error:', valuesError);
    return { total: 0, deltaPct: 0, itemCount: 0 };
  }

  const rows = (valuesData ?? []) as { at: string; value: number }[];

  let total = 0;
  let deltaPct = 0;

  if (rows.length > 0) {
    const first = Number(rows[0].value || 0);
    const last = Number(rows[rows.length - 1].value || 0);
    total = last;
    deltaPct = first ? ((last - first) / first) * 100 : 0;
  }

  // Get item count
  const { count, error: countError } = await supabase
    .from('items')
    .select('id', { count: 'exact', head: true });

  if (countError) {
    logger.warn('[SupabaseDataProvider] item count error:', countError);
  }

  return {
    total,
    deltaPct,
    itemCount: count ?? 0,
  };
}
