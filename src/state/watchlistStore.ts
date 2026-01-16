import { useMemo, useState } from "react";

export type WatchlistItem = {
  id: string;
  name?: string | null;
  category?: string | null;
  value?: number | null;
};

export type WatchlistState = {
  items: Record<string, WatchlistItem>;
  alerts: Record<string, any>;
  addItem: (item: WatchlistItem) => void;
  removeItem: (id: string) => void;
  clear: () => void;
};

/**
 * Mock-safe watchlist store.
 * This is intentionally local-state-only to keep Expo Go stable.
 * Later we can replace with Zustand / Supabase-backed state behind feature flags.
 */
export function useWatchlist(): WatchlistState {
  const [items, setItems] = useState<Record<string, WatchlistItem>>({});
  const [alerts] = useState<Record<string, any>>({});

  return useMemo(
    () => ({
      items,
      alerts,
      addItem: (item) => {
        if (!item?.id) return;
        setItems((prev) => ({ ...prev, [item.id]: item }));
      },
      removeItem: (id) => {
        if (!id) return;
        setItems((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      },
      clear: () => setItems({}),
    }),
    [items, alerts]
  );
}

export default useWatchlist;
