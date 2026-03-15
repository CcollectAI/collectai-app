/**
 * Alerts and trigger history API methods.
 */
import { get, post, del } from "./httpClient";

export const getAlertTriggerHistory = () =>
  get<{
    triggers: Array<{
      id: string;
      alert_id: string | null;
      item_id: string | null;
      trigger_type: string;
      trigger_value: Record<string, unknown>;
      message: string;
      read: boolean;
      created_at: string;
    }>;
    unread_count: number;
  }>("/alerts/trigger-history");

export const markTriggerRead = (triggerId: string) =>
  post(`/alerts/trigger-history/${encodeURIComponent(triggerId)}/read`);

export const getMyAlerts = () =>
  get<{
    alerts: Array<{
      id: string;
      user_id: string;
      item_id: string | null;
      category: string | null;
      trigger_type: string;
      threshold_value: number | null;
      direction: string | null;
      active: boolean;
      created_at: string;
    }>;
  }>("/alerts/mine");

export const createAlert = (payload: {
  item_id?: string;
  category?: string;
  trigger_type: string;
  threshold_value?: number;
  direction?: string;
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
