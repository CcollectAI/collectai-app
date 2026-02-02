import supabase from "../lib/supabaseClient";
import { storeLogger } from "@/lib/logger";

export type CollectionItem = {
  id: string;
  name: string;
  category: string;
  collectionName?: string;
  value: number;
  condition?: string;
  notes?: string;
};

/**
 * Fetch collection items from Supabase.
 * Reuses the same schema as the old useItems hook:
 *   table "items" with columns id,title,image_url,category,value,updated_at
 */
export async function fetchCollectionItems(): Promise<CollectionItem[]> {
  if (!supabase) {
    // Fallback: small demo list if client isn't configured
    return [
      {
        id: "demo-1",
        name: "Demo Charizard",
        category: "Pokémon",
        collectionName: "Demo Collection",
        value: 120,
      },
      {
        id: "demo-2",
        name: "Demo Funko",
        category: "Funko Pop",
        collectionName: "Demo Collection",
        value: 80,
      },
    ];
  }

  const { data, error } = await supabase
    .from("items")
    .select("id,title,image_url,category,value,updated_at")
    .order("updated_at", { ascending: false })
    .limit(200);

  if (error) {
    storeLogger.error("fetchCollectionItems error", error);
    // return empty so the UI can fall back to its own mocks if needed
    return [];
  }

  const rows =
    (data ?? []) as {
      id: string;
      title: string;
      image_url?: string | null;
      category?: string | null;
      value?: number | null;
      updated_at?: string | null;
    }[];

  return rows.map((r) => ({
    id: r.id,
    name: r.title,
    category: r.category || "Uncategorized",
    collectionName: undefined, // can be extended later
    value: typeof r.value === "number" ? r.value : 0,
    // condition/notes can be extended later (e.g. from another table or JSON)
    condition: undefined,
    notes: r.updated_at
      ? `Last updated: ${new Date(r.updated_at).toLocaleString()}`
      : undefined,
  }));
}

export type PortfolioTotals = {
  total: number;
  deltaPct: number;
};

/**
 * Fetch portfolio value series from Supabase and compute:
 *   - total = last value in series
 *   - deltaPct = percentage change from first to last
 *
 * Reuses the same schema as the old usePortfolioSeries hook:
 *   table "portfolio_values" with columns at (timestamptz), value (numeric)
 */
export async function fetchPortfolioTotals(): Promise<PortfolioTotals> {
  if (!supabase) {
    return demoTotals();
  }

  const { data, error } = await supabase
    .from("portfolio_values")
    .select("at,value")
    .order("at", { ascending: true })
    .limit(365);

  if (error) {
    storeLogger.error("fetchPortfolioTotals error", error);
    return demoTotals();
  }

  const rows = (data ?? []) as { at: string; value: number }[];
  if (!rows.length) return demoTotals();

  const first = Number(rows[0].value || 0);
  const last = Number(rows[rows.length - 1].value || 0);

  const total = last;
  const deltaPct = first ? ((last - first) / first) * 100 : 0;

  return { total, deltaPct };
}

function demoTotals(): PortfolioTotals {
  // Same spirit as demoSeries: gentle uptrend
  const base = 1000;
  const last = base * 1.12;
  return {
    total: last,
    deltaPct: 12,
  };
}

// Fallback hook for callers expecting useCollectionStore.
// This avoids runtime "useCollectionStore is not a function" while
// keeping existing store logic intact.
export function useCollectionStore() {
  return {
    items: [],
    loading: false,
    refresh: async () => {},
  };
}
