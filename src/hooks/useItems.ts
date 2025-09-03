import { useCallback, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export type Item = {
  id: string; user_id: string; title: string; category: string;
  image_url?: string | null; purchase_price?: number | null; created_at?: string;
};

export type ItemsQuery = { category?: string; search?: string; order?: 'new'|'old'|'title'; limit?: number; };

export default function useItems(q: ItemsQuery){
  const [items,setItems]=useState<Item[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<string|null>(null);
  const [refreshing,setRefreshing]=useState(false);
  const [page,setPage]=useState(0);

  const load = useCallback(async (reset=false)=>{
    if(reset){ setPage(0); }
    const pageSize = q.limit ?? 24;
    const from = (reset?0:page)*pageSize;
    const to = from + pageSize - 1;

    setLoading(reset ? true : false);
    setRefreshing(!reset);

    const { data:{ session } } = await supabase.auth.getSession();
    const uid = session?.user?.id;
    if(!uid){ setItems([]); setLoading(false); setRefreshing(false); return; }

    let query = supabase.from('items').select('*').eq('user_id', uid);

    if(q.category && q.category !== 'all') query = query.eq('category', q.category);
    if(q.search && q.search.trim()){
      const s = q.search.trim();
      query = query.ilike('title', `%${s}%`);
    }

    if(q.order==='title') query = query.order('title', { ascending:true });
    else if(q.order==='old') query = query.order('created_at', { ascending:true });
    else query = query.order('created_at', { ascending:false });

    query = query.range(from, to);

    const { data, error } = await query;
    if(error){ setError(error.message); setLoading(false); setRefreshing(false); return; }

    setItems(reset ? (data||[]) : [...items, ...(data||[])]);
    setLoading(false); setRefreshing(false);
    if(!reset) setPage(p=>p+1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.category, q.search, q.order, q.limit, page, items]);

  useEffect(()=>{ load(true); }, [q.category, q.search, q.order]);

  const refresh = ()=> load(true);
  const loadMore = ()=> load(false);

  return { items, loading, error, refreshing, refresh, loadMore };
}
