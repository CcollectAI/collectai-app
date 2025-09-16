import { useEffect, useMemo, useState } from 'react';
import { getJSON, setJSON } from '@/lib/storage';

export type Item = { id: string; category: string; name: string; price: number; pct?: number; tier?: 'silver'|'gold'|'platinum'; };
const KEY = 'items.v1';

export async function addItem(it: Omit<Item,'id'>): Promise<Item[]> {
  const curr = await getJSON<Item[]>(KEY, []);
  const next: Item[] = [...curr, { ...it, id: String(Date.now()) }];
  await setJSON(KEY, next);
  return next;
}
export async function listItems(): Promise<Item[]> { return getJSON<Item[]>(KEY, []); }

export function useItems(): Item[] {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => { listItems().then(setItems); }, []);
  return items;
}
export function useItemsWithSeed(seed: Item[]): Item[] {
  const user = useItems();
  return useMemo(() => [...seed, ...user], [user, seed]);
}
export function groupByCategory(items: Item[]) {
  const map = new Map<string, Item[]>();
  for (const it of items) map.set(it.category, [...(map.get(it.category)||[]), it]);
  return Array.from(map.entries()).map(([category, items]) => {
    const tier: Item['tier'] = (items.some(i => i.price > 1500) ? 'platinum'
                         : items.some(i => i.price > 400) ? 'gold' : 'silver');
    return { category, items, tier };
  });
}
