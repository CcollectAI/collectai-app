import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

type Offer = { id: string|number; listing_id?: string|number|null; price?: number|null; created_at?: string|null; from_user?: string|null };

export default function useOffers(listingId?: string|number, limit = 100) {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        let q = supabase.from("offers").select("id, listing_id, price, created_at, from_user")
          .order("created_at", { ascending: false })
          .limit(limit);
        if (listingId != null) q = q.eq("listing_id", listingId);
        const { data, error } = await q;
        if (error) throw error;
        on && setOffers((data as Offer[]) ?? []);
      } catch (e:any) {
        on && setError(e?.message ?? "Failed to load offers");
        on && setOffers([]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [listingId, limit]);

  return { offers, loading, error };
}
