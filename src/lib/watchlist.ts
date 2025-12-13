import { useEffect, useState } from 'react';
import { getJSON, setJSON } from '@/lib/storage';

export type WatchItem = {
  id: string;
  name: string;
  targetEUR?: number;
  priceEUR?: number;
  changePct?: number;
  notes?: string;
};

const KEY='@watchlist';

export function useWatchlist(){
  const [items,setItems] = useState<WatchItem[]>([]);
  useEffect(()=>{ (async()=> setItems(await getJSON<WatchItem[]>(KEY,[])))() },[]);
  const add = async (w: Omit<WatchItem,'id'>)=>{
    const cur = await getJSON<WatchItem[]>(KEY,[]);
    const next = [...cur, { id:String(Date.now()), ...w }];
    await setJSON(KEY,next); setItems(next);
  };
  const remove = async (id:string)=>{
    const cur = await getJSON<WatchItem[]>(KEY,[]);
    const next = cur.filter(x=>x.id!==id);
    await setJSON(KEY,next); setItems(next);
  };
  return { items, add, remove, setItems };
}
