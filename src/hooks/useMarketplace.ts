import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type Listing = { id: string|number; title?: string; price?: number|null; created_at?: string|null };

export default function useMarketplace(limit = 100) {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const { data, error } = await supabase
          .from("listings")
          .select("id, title, price, created_at")
          .order("created_at", { ascending: false })
          .limit(limit);
        if (error) throw error;
        on && setListings((data as Listing[]) ?? []);
      } catch (e:any) {
        on && setError(e?.message ?? "Failed to load marketplace");
        on && setListings([]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [limit]);

  return { listings, loading, error };
}
