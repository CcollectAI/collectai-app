/**
 * useWatchlistRealtime — Subscribes to Supabase realtime changes on the
 * watchlist table so market price/trend updates appear without manual refresh.
 */
import { useEffect, useRef } from 'react';
import { supabase } from '@/lib/supabase';
import type { WatchlistItem } from '@/data/types';

type WatchlistUpdate = {
  id: string;
  last_market_price: number | null;
  last_checked_at: string | null;
  price_trend: 'up' | 'down' | 'stable' | null;
  market_hit_count: number;
};

/**
 * Subscribes to realtime UPDATE events on the watchlist table for a given user.
 * Calls `onUpdate` whenever a row's market data changes.
 */
export function useWatchlistRealtime(
  userId: string | null,
  onUpdate: (id: string, patch: Partial<WatchlistItem>) => void,
) {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    if (!userId) return;

    const channel = supabase
      .channel(`watchlist:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'watchlist_items',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          const row = payload.new as WatchlistUpdate;
          if (!row?.id) return;

          onUpdateRef.current(row.id, {
            lastMarketPrice: row.last_market_price,
            lastCheckedAt: row.last_checked_at,
            priceTrend: row.price_trend,
            marketHitCount: row.market_hit_count ?? 0,
          });
        },
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [userId]);
}
