import { useEffect, useState, useCallback, useRef } from 'react';
import { supabase } from '../lib/supabase';
import type { Category } from '../types/category';
import { get, put } from '../lib/store';

type Page = { items: any[]; nextOffset: number | null };
type SortKey = 'created_at' | 'latest_price' | 'title';

export default function useItems({
  search, category, pageSize=20, sortBy='created_at', sortDir='desc'
}: { search?: string; category?: Category | 'all'; pageSize?: number; sortBy?: SortKey; sortDir?: 'asc'|'desc' }) {
  const [items, setItems] = useState<any[]>([]);
  const cacheKey = `items:${search ?? ''}:${category ?? 'all'}:${pageSize}:${sortBy}:${sortDir}`;
  useEffect(()=>{ (async()=>{ setItems(await get<any[]>(`cache:${cacheKey}`, [])); })(); }, [cacheKey]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const reachedEnd = useRef(false);

  const buildQuery = () => {
    let q = supabase
     .from('items_card')
     .select('id,title,category,acquisition_price,latest_price,created_at,tag_names,thumb_path', { count: 'exact' });
    if (search && search.trim()) q = q.ilike('title', `%${search.trim()}%`);
    if (category && category !== 'all') q = q.eq('category', category);
    q = q.order(sortBy, { ascending: sortDir === 'asc' });
    return q;
  };

  const fetchPage = useCallback(async (start: number): Promise<Page> => {
    const q = buildQuery();
    const { data, error, count } = await q.range(start, start + pageSize - 1);
    if (error) throw error;
    const next = data && data.length === pageSize ? start + pageSize : null;
    if (count !== null && start + pageSize >= count) reachedEnd.current = true;
    return { items: data || [], nextOffset: next };
  }, [search, category, pageSize, sortBy, sortDir]);

  const reload = useCallback(async () => {
    setLoading(true); setError(null); reachedEnd.current = false;
    try {
      const page = await fetchPage(0);
      setItems(page.items);
      put(`cache:${cacheKey}`, page.items).catch(()=>{});
      setOffset(page.nextOffset ?? 0);
    } catch(e:any){ setError(e.message ?? String(e)); }
    finally { setLoading(false); }
  }, [fetchPage]);

  const loadMore = useCallback(async () => {
    if (reachedEnd.current || loading) return;
    if (offset === null) return;
    try {
      const page = await fetchPage(offset);
      setItems(prev => [...prev, ...page.items]);
      setOffset(page.nextOffset ?? 0);
      if (page.nextOffset === null) reachedEnd.current = true;
    } catch(e:any){ setError(e.message ?? String(e)); }
  }, [offset, fetchPage, loading])
      put(`cache:${cacheKey}`, [...items, ...page.items]).catch(()=>{});

  useEffect(() => { reload(); }, [reload]);

  const refresh = async () => { setRefreshing(true); await reload(); setRefreshing(false); };

  return { items, loading, error, refreshing, refresh, loadMore, reachedEnd: reachedEnd.current };
}
