/**
 * Price prediction and evidence API methods.
 */
import { get } from "./httpClient";

// Path fixed 2026-04-19: backend is /predict/trend/{item_id}, not
// /predict/{item_id}/trend. Pre-fix the call 404'd so paid users saw
// a "nothing to show" chart despite Pro unlock.
export const getItemPriceTrend = (itemId: string, days = 90) =>
  get<{
    data_points: { date: string; q50: number; q10: number; q90: number }[];
    direction: 'up' | 'down' | 'flat';
    pct_change: number;
    current_q50: number;
    period_days: number;
  }>(`/predict/trend/${encodeURIComponent(itemId)}?days=${days}`);

export const getPriceEvidence = (itemId: string) =>
  get<{
    explanation: string | null;
    evidence_summary: {
      sources: { source: string; count: number; avg_price: number; date_range?: string }[];
      total_comps: number;
    } | null;
    evidence_hit_ids: string[];
    prediction_at: string | null;
  }>(`/predict/evidence/${encodeURIComponent(itemId)}`);
