/**
 * useAlertsFeed Hook
 * Fetches alerts from backend + derives price alerts from item priceBand data.
 */

import { useState, useEffect, useCallback } from 'react';
import { Alert, AlertType } from '@/types/insights';
import { featureFlags } from '@/config/featureFlags';
import { dataProvider } from '@/data';
import { collectorsApi } from '@/api/collectorsApi';

export type UseAlertsFeedOptions = {
  limit?: number;
  unreadOnly?: boolean;
  enabled?: boolean;
};

export type UseAlertsFeedReturn = {
  alerts: Alert[];
  unreadCount: number;
  isLoading: boolean;
  error: Error | null;
  markAsRead: (alertId: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  refetch: () => Promise<void>;
};

export function useAlertsFeed(
  options: UseAlertsFeedOptions = {}
): UseAlertsFeedReturn {
  const { limit = 10, unreadOnly = false, enabled = true } = options;
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchAlerts = useCallback(async () => {
    if (!enabled || !featureFlags.FEATURE_DATA_INSIGHTS_ALERTS) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [feedItems, items] = await Promise.all([
        dataProvider.listAlertsFeed(),
        dataProvider.listItems({ limit: 25 }),  // Only top items for derived alerts
      ]);

      // Map backend AlertFeedItems to UI Alert type
      const backendAlerts: Alert[] = feedItems.map((fi) => {
        const alertType: AlertType =
          fi.type === 'price_drop' ? 'price_drop'
            : fi.type === 'price_spike' ? 'price_increase'
            : fi.type === 'restock' ? 'new_listing'
            : 'milestone';

        return {
          id: fi.id,
          type: alertType,
          itemId: fi.itemId ?? fi.watchlistItemId ?? '',
          itemName: fi.title,
          itemCategory: '',
          description: fi.title,
          condition: fi.body ?? '',
          value: 0,
          triggeredAt: fi.createdAt,
          isRead: false,
        };
      });

      // Derive price alerts from items with priceBand data
      const derivedAlerts: Alert[] = [];
      for (const item of items) {
        if (!item.priceBand) continue;

        if (item.price < item.priceBand.q10) {
          derivedAlerts.push({
            id: `derived-drop-${item.id}`,
            type: 'price_drop',
            itemId: item.id,
            itemName: item.name,
            itemCategory: item.category,
            itemImageUrl: item.imageUrl,
            description: `${item.name} price below Q10 threshold`,
            condition: `Price \u20AC${item.price} < Q10 \u20AC${item.priceBand.q10}`,
            value: item.price,
            previousValue: item.priceBand.q10,
            triggeredAt: item.updatedAt ?? new Date().toISOString(),
            isRead: false,
          });
        } else if (item.price > item.priceBand.q90) {
          derivedAlerts.push({
            id: `derived-spike-${item.id}`,
            type: 'price_increase',
            itemId: item.id,
            itemName: item.name,
            itemCategory: item.category,
            itemImageUrl: item.imageUrl,
            description: `${item.name} price above Q90 threshold`,
            condition: `Price \u20AC${item.price} > Q90 \u20AC${item.priceBand.q90}`,
            value: item.price,
            previousValue: item.priceBand.q90,
            triggeredAt: item.updatedAt ?? new Date().toISOString(),
            isRead: false,
          });
        }
      }

      let combined = [...backendAlerts, ...derivedAlerts];

      // Sort by triggeredAt descending (most recent first)
      combined.sort(
        (a, b) => new Date(b.triggeredAt).getTime() - new Date(a.triggeredAt).getTime()
      );

      if (unreadOnly) {
        combined = combined.filter((a) => !a.isRead);
      }

      setAlerts(combined.slice(0, limit));
    } catch (e) {
      setError(e instanceof Error ? e : new Error('Failed to fetch alerts'));
    } finally {
      setIsLoading(false);
    }
  }, [limit, unreadOnly, enabled]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const markAsRead = useCallback(async (alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, isRead: true } : a))
    );
    // Persist to backend (fire-and-forget)
    try {
      await collectorsApi.markTriggerRead(alertId);
    } catch {
      // Best-effort — UI already updated optimistically
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    const unread = alerts.filter((a) => !a.isRead);
    setAlerts((prev) => prev.map((a) => ({ ...a, isRead: true })));
    // Persist each to backend (fire-and-forget, don't block on failures)
    await Promise.allSettled(
      unread.map((a) => collectorsApi.markTriggerRead(a.id))
    );
  }, [alerts]);

  const unreadCount = alerts.filter((a) => !a.isRead).length;

  return {
    alerts,
    unreadCount,
    isLoading,
    error,
    markAsRead,
    markAllAsRead,
    refetch: fetchAlerts,
  };
}
