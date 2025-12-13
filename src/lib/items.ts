import { useEffect, useState } from 'react';
import { getJSON, setJSON } from '@/lib/storage';

export type Item = {
  id: string;
  title: string;
  category: string;
  priceEUR: number;
  changePct?: number;
  notes?: string;
  imageUri?: string;
  year?: string;
  condition?: string;
  grade?: string;
  grader?: string;
};

const KEY='@items';

export const SEED: Item[] = [
  { id: 'itm-1001', title: 'Charizard PSA 9', category: 'Pokémon', priceEUR: 1250, changePct: 2.5, notes: 'Base Set' },
  { id: 'itm-1002', title: 'LEGO Millennium Falcon (75192)', category: 'LEGO', priceEUR: 780, changePct: -1.2 },
  { id: 'itm-1003', title: 'Funko Pop! Grogu #369', category: 'Funko', priceEUR: 42, changePct: 5.1 },
  { id: 'itm-1004', title: 'Pokémon Pikachu PSA 10', category: 'Pokémon', priceEUR: 890, changePct: 1.1 },
  { id: 'itm-1005', title: 'LEGO Modular – Boutique Hotel (10297)', category: 'LEGO', priceEUR: 220, changePct: 0.6 },
];

export async function getItems(): Promise<Item[]> { return await getJSON<Item[]>(KEY, []); }
export async function setItems(next: Item[]): Promise<void> { await setJSON<Item[]>(KEY, next); }

export async function addItem(partial: Omit<Item,'id'>): Promise<Item> {
  const cur = await getItems();
  const item: Item = { id: 'itm-'+Date.now(), ...partial };
  const next = [item, ...cur];
  await setItems(next);
  return item;
}

export async function updateItem(id: string, patch: Partial<Item>): Promise<Item | undefined> {
  const cur = await getItems();
  const idx = cur.findIndex(i=>i.id===id);
  if (idx<0) return;
  const upd = { ...cur[idx], ...patch };
  const next = [...cur]; next[idx] = upd; await setItems(next);
  return upd;
}

export async function removeItem(id: string): Promise<void> {
  const cur = await getItems();
  await setItems(cur.filter(i=>i.id!==id));
}

export function useItems(){
  const [items,setItemsState] = useState<Item[]>([]);
  useEffect(()=>{ (async()=>{
    let cur = await getItems();
    if (!cur || cur.length===0) { cur = SEED; await setItems(cur); }
    setItemsState(cur);
  })() },[]);
  return { items, setItems: setItemsState };
}

export function groupByCategory(items: Item[]){
  const map: Record<string, Item[]> = {};
  items.forEach(i => { (map[i.category] ||= []).push(i); });
  return Object.keys(map).sort().map(cat => ({ category: cat, items: map[cat] }));
}

export async function reloadInto(setter:(it:Item[])=>void){ setter(await getItems()); }
