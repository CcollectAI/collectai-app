import { supabase } from "../../lib/supabase";
import { useMemo } from "react";
import { useSWR } from "../cache/useSWR";

export type ListingRow = {
  id: string;
  title: string;
  price: number;
  image_url?: string;
  status?: "active" | "sold" | "draft";
  category?: string;
  created_at?: string;
};

async function fetchAll(): Promise<ListingRow[]> {
  if (!supabase) return demo();
  const { data, error } = await supabase
    .from("listings")
    .select("id,title,price,image_url,status,category,created_at")
    .order("created_at", { ascending: false })
    .limit(200);
  if (error) throw error;
  return (data ?? []) as ListingRow[];
}

export default function useListings(filter?: { status?: string; q?: string }) {
  const { data, loading, refresh } = useSWR<ListingRow[]>("listings:list", fetchAll, { staleMs: 120_000 });

  const rows = useMemo(() => {
    let r = (data ?? demo());
    if (filter?.status) r = r.filter(x => x.status === filter.status);
    if (filter?.q) {
      const q = filter.q.toLowerCase();
      r = r.filter(x => x.title.toLowerCase().includes(q));
    }
    return r;
  }, [data, filter?.status, filter?.q]);

  return { rows, loading, refresh };
}

function demo(): ListingRow[] {
  return Array.from({ length: 16 }).map((_, i) => ({
    id: `listing-${i}`,
    title: `Demo Listing #${i + 1}`,
    price: 120 + i * 7,
    status: (i % 3 ? "active" : "sold") as "active" | "sold",
    category: i % 2 ? "pokemon" : "funko",
  }));
}
