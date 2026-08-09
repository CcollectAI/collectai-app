import { supabase } from "@/lib/supabase";
import { useSWR } from "../cache/useSWR";

export type ItemRow = {
  id: string;
  title: string;
  image_url?: string;
  category?: string;
  value?: number;
  updated_at?: string;
};

async function fetchItems(): Promise<ItemRow[]> {
  if (!supabase) return demo();
  // items has no `value` column — estimated_value is the user's manual
  // figure; the q50 prediction lives on price_predictions and is joined
  // by SupabaseDataProvider.listItems where needed. This hook is a thin
  // SWR wrapper for ItemCard, so estimated_value alone is enough.
  const { data, error } = await supabase
    .from("items")
    .select("id,title,image_url,category,estimated_value,updated_at")
    .eq("archived", false)
    .order("updated_at", { ascending: false })
    .limit(200);
  if (error) throw error;
  return ((data ?? []) as Array<Record<string, unknown>>).map((r) => ({
    id: r.id as string,
    title: (r.title as string) ?? '',
    image_url: (r.image_url as string | undefined) ?? undefined,
    category: (r.category as string | undefined) ?? undefined,
    value: (r.estimated_value as number | undefined) ?? undefined,
    updated_at: (r.updated_at as string | undefined) ?? undefined,
  }));
}

export default function useItems() {
  const { data, loading, refresh } = useSWR<ItemRow[]>("items:list", fetchItems, { staleMs: 120_000 });
  return { items: data ?? demo(), loading, refresh };
}

function demo(): ItemRow[] {
  return Array.from({ length: 24 }).map((_, i) => ({
    id: `demo-${i}`,
    title: `Demo Item #${i + 1}`,
    image_url: undefined,
    category: i % 2 ? "pokemon" : "funko",
    value: 80 + i * 4,
    updated_at: new Date().toISOString(),
  }));
}
