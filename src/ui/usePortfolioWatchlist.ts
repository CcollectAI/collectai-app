import { useMemo } from "react";

export type WatchlistItem = {
  id: string;
  name: string;
  value_eur: number;
  change_7d_pct?: number;
};

export function usePortfolioWatchlist() {
  // Expo-Go-safe mock hook (no IO). Replace later with Supabase/services.
  const items = useMemo<WatchlistItem[]>(
    () => [
      { id: "w1", name: "Charizard Holo (PSA 9)", value_eur: 1250, change_7d_pct: 2.2 },
      { id: "w2", name: "Funko — Grail", value_eur: 420, change_7d_pct: -1.1 },
    ],
    []
  );

  return { items };
}
