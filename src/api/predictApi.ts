/**
 * Price prediction and evidence API methods.
 */
import { get, post } from "./httpClient";

export const predictV2 = (payload: {
  item_id: string;
  category?: string;
  attributes?: Record<string, unknown>;
}) => post<{
  q10: number;
  q50: number;
  q90: number;
  asof: string;
}>("/predict_v2", payload);

export const getItemPriceTrend = (itemId: string, days = 90) =>
  get<{
    data_points: Array<{ date: string; q50: number; q10: number; q90: number }>;
    direction: 'up' | 'down' | 'flat';
    pct_change: number;
    current_q50: number;
    period_days: number;
  }>(`/predict/${encodeURIComponent(itemId)}/trend?days=${days}`);

export const getPriceEvidence = (itemId: string) =>
  get<{
    explanation: string | null;
    evidence_summary: {
      sources: Array<{ source: string; count: number; avg_price: number; date_range?: string }>;
      total_comps: number;
    } | null;
    evidence_hit_ids: string[];
    prediction_at: string | null;
  }>(`/predict/evidence/${encodeURIComponent(itemId)}`);
