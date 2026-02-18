import client from '@/services/collectorsClient';

export type AlertType =
  | 'completeness'
  | 'rarity'
  | 'price'; // price kept for future use

export interface AlertConfig {
  id?: string;
  type: AlertType;
  /**
   * For completeness alerts:
   *   - collection_key identifies which set/collection to watch
   *   - threshold_pct is the completion percentage to trigger at
   */
  collection_key?: string | null;
  threshold_pct?: number | null;

  /**
   * For rarity alerts:
   *   - category or collection_key define scope
   *   - rarity_min_pct defines minimum rarity score to trigger
   */
  category?: string | null;
  rarity_min_pct?: number | null;

  // Future: price alerts
  item_id?: string | null;
  price_threshold?: number | null;

  // Common fields
  enabled: boolean;
}

/**
 * Fetch alerts for the current user.
 * Backend route to implement: GET /alerts
 */
export async function getAlerts(): Promise<AlertConfig[]> {
  const res = await client.get('/alerts');
  const data = (res.data ?? []) as Record<string, unknown>;
  const raw =
    (data && (data.alerts || data.items || data.rows || data)) ?? [];
  return raw as AlertConfig[];
}

/**
 * Upsert (create or update) an alert.
 * Backend route to implement: POST /alerts
 */
export async function upsertAlert(
  alert: AlertConfig,
): Promise<AlertConfig> {
  const res = await client.post('/alerts', alert);
  return (res.data ?? alert) as AlertConfig;
}

/**
 * Disable an alert by id.
 * Backend route to implement: DELETE /alerts/:id
 */
export async function disableAlert(id: string): Promise<void> {
  await client.delete(`/alerts/${id}`);
}
