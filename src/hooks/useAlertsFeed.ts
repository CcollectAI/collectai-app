/**
 * useAlertsFeed Hook
 * Fetches pending alerts from the backend RPC.
 */

import { useState, useEffect, useCallback } from 'react';
import { Alert } from '@/types/insights';
import { featureFlags } from '@/config/featureFlags';

// Mock data for development
const MOCK_ALERTS: Alert[] = [
  {
    id: 'a1',
    type: 'price_drop',
    itemId: '1',
    itemName: 'Charizard #4 PSA 10',
    itemCategory: 'Pokémon',
    description: 'Price dropped 10% below your target',
    condition: 'Price fell below €400 threshold',
    value: 380,
    previousValue: 420,
    triggeredAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    isRead: false,
  },
  {
    id: 'a2',
    type: 'new_listing',
    itemId: '2',
    itemName: 'Funko Pop – Goku Ultra Instinct',
    itemCategory: 'Funko Pop',
    description: 'New listing found on eBay',
    condition: 'Matching item listed at €85',
    value: 85,
    triggeredAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    isRead: false,
  },
  {
    id: 'a3',
    type: 'milestone',
    itemId: '3',
    itemName: 'Your Pokémon Collection',
    itemCategory: 'Pokémon',
    description: 'Collection reached €5,000 milestone!',
    condition: 'Total value exceeded €5,000',
    value: 5120,
    triggeredAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    isRead: true,
  },
];

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
      // TODO: Replace with actual RPC call
      // const { data, error } = await supabase.rpc('rpc_get_alerts_feed_v1', { limit, unread_only: unreadOnly });

      // Simulate API delay
      await new Promise((r) => setTimeout(r, 300));

      let result = [...MOCK_ALERTS];
      if (unreadOnly) {
        result = result.filter((a) => !a.isRead);
      }
      setAlerts(result.slice(0, limit));
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
    // TODO: Call RPC to persist
  }, []);

  const markAllAsRead = useCallback(async () => {
    setAlerts((prev) => prev.map((a) => ({ ...a, isRead: true })));
    // TODO: Call RPC to persist
  }, []);

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
