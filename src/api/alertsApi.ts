/**
 * Alerts and trigger history API methods.
 */
import { get, post, del } from "./httpClient";

export const getAlertTriggerHistory = () =>
  get<{
    triggers: {
      id: string;
      alert_id: string | null;
      item_id: string | null;
      trigger_type: string;
      trigger_value: Record<string, unknown>;
      message: string;
      read: boolean;
      created_at: string;
    }[];
    unread_count: number;
  }>("/alerts/trigger-history");

export const markTriggerRead = (triggerId: string) =>
  post(`/alerts/trigger-history/${encodeURIComponent(triggerId)}/read`);

export const getMyAlerts = () =>
  get<{
    alerts: {
      id: string;
      user_id: string;
      item_id: string | null;
      category: string | null;
      trigger_type: string;
      threshold_value: number | null;
      direction: string | null;
      active: boolean;
      created_at: string;
    }[];
  }>("/alerts/mine");

/**
 * Mirrors `PriceAlertCreate` in server/app/features/alerts_feature_router.py
 * AND the `user_price_alerts_direction_check` / `_trigger_type_check` CHECK
 * constraints — all three agree on these literals.
 *
 * These were `string` until 2026-07-30, and that looseness cost the whole
 * feature: app/(tabs)/wishlist.tsx sent `direction: 'below'` (not a legal
 * value) on both of its auto-alert call sites, so every wishlist target-price
 * alert 422'd. The failure was caught and only logged, so the user saw no
 * error — just an alert that never existed. Keep these as literal unions;
 * widening them back to `string` re-opens the hole silently.
 */
export type AlertDirection = "up" | "down";
export type AlertTriggerType =
  | "below_threshold"
  | "category_trend"
  | "high_prediction";

export const createAlert = (payload: {
  item_id?: string;
  category?: string;
  trigger_type: AlertTriggerType;
  threshold_value?: number;
  direction?: AlertDirection;
  metadata?: Record<string, unknown>;
}) =>
  post<{
    id: string;
    trigger_type: string;
    threshold_value: number | null;
    active: boolean;
  }>("/alerts/mine", payload);

export const deleteAlert = (alertId: string) =>
  del(`/alerts/mine/${encodeURIComponent(alertId)}`);
