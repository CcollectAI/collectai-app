import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { RealtimePostgresChangesPayload } from '@supabase/supabase-js';

export type Comment = { id:string; post_id:string; user_id:string; content:string; created_at:string };

export default function useComments(postId:string){
  const [rows,setRows]=useState<Comment[]>([]);
  const [loading,setLoading]=useState(true);

  const load = async ()=>{
    if(!postId) return;
    setLoading(true);
    const { data, error } = await supabase
      .from('post_comments')
      .select('*')
      .eq('post_id', postId)
      .order('created_at', { ascending:true });
    if(!error) setRows(data||[]);
    setLoading(false);
  };

  useEffect(()=>{ load(); },[postId]);

  const add = async (content:string)=>{
    const { data:{ session } } = await supabase.auth.getSession();
    const uid = session?.user?.id;
    if(!uid) return;
    const { error } = await supabase.from('post_comments').insert({ post_id:postId, user_id:uid, content });
    if(!error) load();
  };

  return { rows, loading, add };
useEffect(()=>{
  if(!postId) return;
  const chan = supabase.channel(`comments-${postId}`)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'post_comments', filter:`post_id=eq.${postId}` }, (p:RealtimePostgresChangesPayload<any>)=>{
      setRows(prev=> [...prev, p.new as any]);
    })
    .on('postgres_changes', { event:'DELETE', schema:'public', table:'post_comments', filter:`post_id=eq.${postId}` }, (p)=>{
      setRows(prev=> prev.filter(r=> r.id !== (p.old as any).id));
    })
    .subscribe();
  return ()=> { supabase.removeChannel(chan); };
}, [postId]);
}
