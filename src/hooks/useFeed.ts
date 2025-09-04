import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type Post = { id: string|number; title?: string; body?: string; created_at?: string|null; author_id?: string|null };

export default function useFeed(limit = 50) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        const { data, error } = await supabase
          .from("posts")
          .select("id, title, body, created_at, author_id")
          .order("created_at", { ascending: false })
          .limit(limit);
        if (error) throw error;
        on && setPosts((data as Post[]) ?? []);
      } catch (e:any) {
        on && setError(e?.message ?? "Failed to load feed");
        on && setPosts([]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [limit]);

  return { posts, loading, error };
}
