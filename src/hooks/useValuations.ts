import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type Val = { id: string|number; item_id?: string|number|null; value?: number|null; ts?: string|null };

export default function useValuations(itemId?: string|number, limit = 100) {
  const [rows, setRows] = useState<Val[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        let q = supabase.from("valuations").select("id, item_id, value, ts")
          .order("ts", { ascending: true }).limit(limit);
        if (itemId != null) q = q.eq("item_id", itemId);
        const { data, error } = await q;
        if (error) throw error;
        on && setRows((data as Val[]) ?? []);
      } catch (e:any) {
        on && setError(e?.message ?? "Failed to load valuations");
        on && setRows([]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [itemId, limit]);

  return { rows, loading, error };
}
