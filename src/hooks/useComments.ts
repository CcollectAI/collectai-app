import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

type Comment = { id: string|number; post_id?: string|number|null; body?: string|null; created_at?: string|null; author_id?: string|null };

export default function useComments(postId?: string|number, limit = 100) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string|null>(null);

  useEffect(() => {
    let on = true;
    (async () => {
      try {
        let q = supabase.from("comments").select("id, post_id, body, created_at, author_id")
          .order("created_at", { ascending: true })
          .limit(limit);
        if (postId != null) q = q.eq("post_id", postId);
        const { data, error } = await q;
        if (error) throw error;
        on && setComments((data as Comment[]) ?? []);
      } catch (e: unknown) {
        on && setError(e instanceof Error ? e.message : "Failed to load comments");
        on && setComments([]);
      } finally {
        on && setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [postId, limit]);

  return { comments, loading, error };
}
