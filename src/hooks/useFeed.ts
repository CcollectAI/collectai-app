import { useCallback, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { RealtimePostgresChangesPayload } from '@supabase/supabase-js';

export type Post = { id:string; user_id:string; content:string|null; image_url:string|null; created_at:string; };
export type FeedItem = Post & { like_count:number; liked:boolean };

export default function useFeed(){
  const [rows,setRows]=useState<FeedItem[]>([]);
  const [loading,setLoading]=useState(true);
  const [refreshing,setRefreshing]=useState(false);
  const [page,setPage]=useState(0);
  const pageSize = 10;

  const load = useCallback(async (reset:boolean)=>{
    const from = (reset?0:page)*pageSize;
    const to = from + pageSize - 1;

    if(reset) setLoading(true); else setRefreshing(true);

    const { data:{ session } } = await supabase.auth.getSession();
    const uid = session?.user?.id;

    const { data: posts, error } = await supabase
      .from('posts')
      .select('*')
      .order('created_at', { ascending:false })
      .range(from,to);

    if(error){ setLoading(false); setRefreshing(false); return; }

    const postIds = posts?.map(p=>p.id) || [];
    let likesMap: Record<string, number> = {};
    if(postIds.length){
      const { data: likesAgg } = await supabase
        .from('post_likes')
        .select('post_id, count:user_id')
        .in('post_id', postIds)
        .group('post_id');
      (likesAgg||[]).forEach((r:any)=>{ likesMap[r.post_id] = Number(r.count)||0; });
    }

    let likedMap: Record<string, boolean> = {};
    if(uid && postIds.length){
      const { data: myLikes } = await supabase
        .from('post_likes')
        .select('post_id')
        .eq('user_id', uid)
        .in('post_id', postIds);
      (myLikes||[]).forEach((r:any)=>{ likedMap[r.post_id] = true; });
    }

    const enriched: FeedItem[] = (posts||[]).map(p=>({
      ...p,
      like_count: likesMap[p.id]||0,
      liked: !!likedMap[p.id],
    }));

    setRows(reset? enriched : [...rows, ...enriched]);
    setLoading(false); setRefreshing(false);
    if(!reset) setPage(p=>p+1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, rows]);

  useEffect(()=>{ load(true); },[]);

  const refresh = ()=> load(true);
  const loadMore = ()=> load(false);

  const toggleLike = async (post_id:string)=>{
    const { data:{ session } } = await supabase.auth.getSession();
    const uid = session?.user?.id; if(!uid) return;
    const idx = rows.findIndex(r=>r.id===post_id);
    if(idx<0) return;
    const item = rows[idx];
    // optimistic
    const next = [...rows];
    if(item.liked){ next[idx] = { ...item, liked:false, like_count:Math.max(0,item.like_count-1) }; }
    else { next[idx] = { ...item, liked:true, like_count:item.like_count+1 }; }
    setRows(next);

    if(item.liked){
      await supabase.from('post_likes').delete().eq('post_id', post_id).eq('user_id', uid);
    }else{
      await supabase.from('post_likes').insert({ post_id, user_id: uid });
    }
  };
  return { rows, loading, refreshing, refresh, loadMore, toggleLike };
useEffect(()=>{
  const chan = supabase.channel('feed-changes')
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'posts' }, (p: RealtimePostgresChangesPayload<any>)=>{
      const row = p.new;
      setRows(prev=> [{ ...row, like_count:0, liked:false }, ...prev]);
    })
    .on('postgres_changes', { event: 'DELETE', schema: 'public', table: 'posts' }, (p)=>{
      const id = (p.old as any).id;
      setRows(prev=> prev.filter(r=>r.id!==id));
    })
    .on('postgres_changes', { event: '*', schema: 'public', table: 'post_likes' }, (_p)=>{
      // simple strategy: reload first page to refresh counts
      load(true);
    })
    .subscribe();

  return ()=> { supabase.removeChannel(chan); };
}, [load]);
}
