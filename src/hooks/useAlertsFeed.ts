/**
 * useAlertsFeed Hook
 * Fetches alerts from backend + derives price alerts from item priceBand data.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Alert, AlertType } from '@/types/insights';
import { featureFlags } from '@/config/featureFlags';
import { dataProvider } from '@/data';
import { collectorsApi } from '@/api/collectorsApi';
import { logger } from '@/lib/logger';
import { clearAlertsFeedCache } from '@/data/CachedDataProvider';

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

/**
 * A client-side alert with no row behind it. Built below as
 * `derived-drop-<itemId>` / `derived-spike-<itemId>` from an item's price
 * band, so its id is not a trigger-history uuid and must never be sent to
 * POST /alerts/trigger-history/{id}/read.
 */
const isDerived = (id: string) => id.startsWith('derived-');

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

        // `fi.title` is the whole alert SENTENCE — the provider maps it from
        // alert_trigger_history.message, e.g.
        //   "Charizard — €195 on eBay (30% below your target of €280)"
        //
        // It was being used for BOTH itemName and description, so the Home card
        // printed that sentence twice, one line above the other, with a
        // hardcoded €0 beside it. Reported 2026-08-08 as "full item names with a
        // price in the title ... stuck on zero. this is messy" — accurately.
        //
        // The worker builds the message as "<item> — <offer>", so splitting on
        // the em dash recovers the two halves. Falls back to the whole string
        // when a future message does not use that shape: a long title is untidy,
        // an EMPTY one is a broken row.
        const [namePart, ...restParts] = fi.title.split(' — ');
        const rest = restParts.join(' — ');

        return {
          id: fi.id,
          type: alertType,
          itemId: fi.itemId ?? fi.watchlistItemId ?? '',
          itemName: namePart || fi.title,
          itemCategory: '',
          description: rest || fi.body || '',
          condition: fi.body ?? '',
          // The real price the alert fired on. Was hardcoded 0.
          value: fi.price ?? 0,
          triggeredAt: fi.createdAt,
          // The SERVER's flag (2026-09-17). This was hardcoded `false`, so every
          // alert the member had already handled came back as new on the next
          // fetch, `unreadOnly` filtered nothing, and the mark-read write was
          // invisible — the row was written and then ignored.
          isRead: fi.read,
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
    // A DERIVED alert (`derived-drop-<itemId>`) has no trigger-history row, so
    // there is nothing to persist: the id is not a uuid and the endpoint
    // answered 400 for every one of them. It is recomputed unread on the next
    // fetch either way — that is a known limit of derived alerts, not a write
    // to retry.
    if (isDerived(alertId)) return;
    try {
      await collectorsApi.markTriggerRead(alertId);
      // The feed is cached TTL_MEDIUM; without this the next read returns the
      // list that still says unread.
      await clearAlertsFeedCache();
    } catch (e) {
      // ROLL BACK (2026-09-17). The optimistic flip used to stand whatever
      // happened, so a failed write showed the alert as handled until the cache
      // expired and it silently came back. The screen now keeps saying what the
      // server actually holds.
      logger.error('[alertsFeed] markTriggerRead failed; rolling the row back:', e);
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, isRead: false } : a))
      );
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    const unread = alerts.filter((a) => !a.isRead);
    const persistable = unread.filter((a) => !isDerived(a.id));
    setAlerts((prev) => prev.map((a) => ({ ...a, isRead: true })));
    const results = await Promise.allSettled(
      persistable.map((a) => collectorsApi.markTriggerRead(a.id))
    );
    // Same rollback, per row: "mark all read" that half-failed used to clear the
    // whole list and let the failed half reappear later with no explanation.
    const failed = persistable
      .filter((_, i) => results[i].status === 'rejected')
      .map((a) => a.id);
    if (failed.length) {
      logger.error(
        `[alertsFeed] markAllAsRead: ${failed.length}/${persistable.length} did not persist`
      );
      setAlerts((prev) =>
        prev.map((a) => (failed.includes(a.id) ? { ...a, isRead: false } : a))
      );
    }
    if (failed.length < persistable.length) await clearAlertsFeedCache();
  }, [alerts]);

  const unreadCount = useMemo(() => alerts.filter((a) => !a.isRead).length, [alerts]);

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
