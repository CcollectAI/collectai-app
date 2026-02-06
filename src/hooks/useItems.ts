import { supabase } from "../../lib/supabase";
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
  const { data, error } = await supabase
    .from("items")
    .select("id,title,image_url,category,value,updated_at")
    .order("updated_at", { ascending: false })
    .limit(200);
  if (error) throw error;
  return (data ?? []) as ItemRow[];
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
