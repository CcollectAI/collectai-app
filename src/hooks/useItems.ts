import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type Item = { id: string|number; title?: string; name?: string; category?: string|null; created_at?: string|null };

export default function useItems(limit = 100) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const { data, error } = await supabase
          .from("items")
          .select("id, title, name, category, created_at")
          .order("created_at", { ascending: false })
          .limit(limit);
        if (error) throw error;
        on && setItems((data as Item[]) ?? []);
      } catch (e:any) {
        on && setError(e?.message ?? "Failed to load items");
        on && setItems([]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [limit]);

  return { items, loading, error };
}
